import datetime
import json
import os
import shutil
import tempfile
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Tuple

from flask import current_app

from .adata import (
    _build_export_fadata,
    _dataset_meta,
    _detect_prior_information,
    _extract_milestone_color_mappings,
    _extract_obs_color_mappings,
    _get_live_adata,
    _load_effective_fadata,
    _load_effective_trajectory_history,
    _source_info,
    _trajectory_layout_union
)

from .common import (
    _dataset_shape,
    _get_cafe_container,
    _matrix_meta,
    _safe_dict,
    _sorted_keys,
    _to_json_value,
    _trajectory_entry_summary
)


def _build_debug_source_payload() -> Dict[str, Any]:
    adata = _get_live_adata()
    live_uns = getattr(adata, "uns", {}) if adata is not None else {}
    live_uns_dict = _safe_dict(live_uns)
    live_cafe = _get_cafe_container(live_uns_dict)
    effective_uns, effective_history = _load_effective_trajectory_history()
    effective_cafe = _get_cafe_container(effective_uns)

    return {
        "dataset": _dataset_meta(),
        "source": _source_info(effective_uns),
        "live": {
            "shape": _dataset_shape(adata),
            "unsKeys": _sorted_keys(live_uns),
            "cafeKeys": _sorted_keys(live_cafe),
            "trajectoryKeys": sorted(str(key) for key in _safe_dict(live_cafe.get("trajectory_history_dict", {})).keys()),
            "modelName": str(live_cafe.get("model_name", "")),
            "priorInformation": _to_json_value(_safe_dict(live_cafe.get("prior_information", {}))),
        },
        "effective": {
            "unsKeys": _sorted_keys(effective_uns),
            "cafeKeys": _sorted_keys(effective_cafe),
            "trajectoryKeys": sorted(str(key) for key in effective_history.keys()),
            "modelName": str(effective_cafe.get("model_name", "")),
            "priorInformation": _to_json_value(_safe_dict(effective_cafe.get("prior_information", {}))),
        },
    }

def _empty_data_summary(dataset_meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dataset": {
            **dataset_meta,
            "shape": {"nObs": 0, "nVars": 0},
            "matrix": {"dtype": "", "sparse": False},
        },
        "fateAnnData": {
            "id": "",
            "modelName": "",
            "priorInformation": {},
            "structure": {
                "obsColumns": [],
                "varColumns": [],
                "layers": [],
                "obsm": [],
                "obsp": [],
                "varm": [],
                "unsKeys": [],
                "cafeKeys": [],
            },
        },
        "trajectories": [],
        "embeddings": {"default": "", "available": [], "trajectoryLayouts": []},
        "colorMappings": [],
        "source": _source_info({}),
        "exports": {
            "h5adUrl": "/api/cafe/data/export/h5ad",
            "trajectoryPackageUrl": "/api/cafe/data/export/trajectory-package",
        },
    }

def _build_data_summary() -> Dict[str, Any]:
    dataset_meta = _dataset_meta()
    summary = _empty_data_summary(dataset_meta)
    adata = _get_live_adata()
    if adata is None:
        return summary

    uns, trajectory_history = _load_effective_trajectory_history()
    cafe_container = _get_cafe_container(uns)
    prior_information = _safe_dict(cafe_container.get("prior_information", {}))
    fate_id = str(uns.get("id", ""))
    model_name = str(cafe_container.get("model_name", ""))

    fadata, fadata_error = _load_effective_fadata()
    if fadata is not None:
        fate_id = str(getattr(fadata, "id", fate_id or ""))
        model_name = str(getattr(fadata, "model_name", model_name or ""))
        prior_information = _safe_dict(getattr(fadata, "prior_information", prior_information))
    elif not prior_information:
        prior_information = _detect_prior_information(adata)

    summary["dataset"] = {
        **dataset_meta,
        "shape": _dataset_shape(adata),
        "matrix": _matrix_meta(adata),
    }
    summary["fateAnnData"] = {
        "id": fate_id,
        "modelName": model_name,
        "priorInformation": _to_json_value(prior_information),
        "structure": {
            "obsColumns": [str(column) for column in getattr(getattr(adata, "obs", None), "columns", [])],
            "varColumns": [str(column) for column in getattr(getattr(adata, "var", None), "columns", [])],
            "layers": _sorted_keys(getattr(adata, "layers", {})),
            "obsm": _sorted_keys(getattr(adata, "obsm", {})),
            "obsp": _sorted_keys(getattr(adata, "obsp", {})),
            "varm": _sorted_keys(getattr(adata, "varm", {})),
            "unsKeys": _sorted_keys(getattr(adata, "uns", {})),
            "cafeKeys": _sorted_keys(cafe_container),
        },
    }
    summary["trajectories"] = [
        _trajectory_entry_summary(str(name), payload) for name, payload in sorted(trajectory_history.items())
    ]
    default_embedding = ""
    if prior_information.get("basis"):
        default_embedding = str(prior_information["basis"])
    elif summary["fateAnnData"]["structure"]["obsm"]:
        default_embedding = summary["fateAnnData"]["structure"]["obsm"][0]
    summary["embeddings"] = {
        "default": default_embedding,
        "available": summary["fateAnnData"]["structure"]["obsm"],
        "trajectoryLayouts": _trajectory_layout_union(trajectory_history),
    }
    summary["colorMappings"] = _extract_obs_color_mappings(adata, uns) + _extract_milestone_color_mappings(trajectory_history)
    summary["source"] = _source_info(uns)
    if fadata_error:
        current_app.logger.warning("Failed to build effective FateAnnData summary object: %s", fadata_error)
    return summary

def _safe_export_basename(dataset_id: str, suffix: str) -> str:
    safe_chars = []
    for char in dataset_id or "dataset":
        safe_chars.append(char if char.isalnum() or char in {"-", "_", "."} else "-")
    stem = "".join(safe_chars).strip("-") or "dataset"
    return f"{stem}-{suffix}"

def _build_data_h5ad_export() -> Tuple[str, str, str, str]:
    dataset_id = _dataset_meta()["id"]
    download_name = _safe_export_basename(dataset_id, "cafe-export.h5ad")
    tempdir = tempfile.mkdtemp(prefix="cafe-h5ad-export-")
    export_path = os.path.join(tempdir, download_name)
    fadata = _build_export_fadata()
    trajectory_history = _safe_dict(_get_cafe_container(fadata.uns).get("trajectory_history_dict", {}))
    if trajectory_history:
        fadata.write_h5ad(export_path)
    else:
        # Fall back to plain AnnData write when no trajectory state exists.
        fadata.to_anndata(delete_trajectory=False).write_h5ad(export_path)
    return export_path, download_name, "application/x-hdf5", tempdir

def _build_trajectory_package_manifest(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dataset": summary["dataset"],
        "source": summary["source"],
        "priorInformation": summary["fateAnnData"]["priorInformation"],
        "trajectories": summary["trajectories"],
        "layoutNames": summary["embeddings"]["trajectoryLayouts"],
        "exportedAt": "",
    }

def _build_data_trajectory_package_export() -> Tuple[str, str, str, str]:
    summary = _build_data_summary()
    dataset_id = summary["dataset"]["id"]
    download_name = _safe_export_basename(dataset_id, "trajectory-package.zip")
    tempdir = tempfile.mkdtemp(prefix="cafe-trajectory-export-")
    trajectories_dir = os.path.join(tempdir, "trajectories")
    os.makedirs(trajectories_dir, exist_ok=True)

    fadata = _build_export_fadata()
    trajectory_history = _safe_dict(_get_cafe_container(fadata.uns).get("trajectory_history_dict", {}))
    fadata.write_trajectory_dict(dirname=trajectories_dir, model_name_list=sorted(trajectory_history.keys()))

    manifest = _build_trajectory_package_manifest(summary)
    manifest["exportedAt"] = datetime.utcnow().isoformat() + "Z"
    manifest_path = os.path.join(tempdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    zip_path = os.path.join(tempdir, download_name)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_path, arcname="manifest.json")
        for filename in sorted(os.listdir(trajectories_dir)):
            archive.write(os.path.join(trajectories_dir, filename), arcname=f"trajectories/{filename}")

    return zip_path, download_name, "application/zip", tempdir

def _cleanup_export_dir(dirname: str) -> None:
    shutil.rmtree(dirname, ignore_errors=True)

