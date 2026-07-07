import json
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

from .common import (
    _as_float,
    _as_sequence,
    _best_default,
    _dataset_shape,
    _get_cafe_container,
    _get_item_attr,
    _normalize_color,
    _restore_serialized_trajectory_wrappers,
    _safe_dict,
    _sample_items,
    _series_labels_for_colors,
    _to_json_value,
    _try_numeric
)

from .compat import (
    _ensure_headless_matplotlib,
    _patch_fate_anndata_velocity_category_compat,
    _patch_plot_trajectory_title_compat
)

_WRAPPED_FADATA_LOCK = threading.Lock()
_WRAPPED_FADATA_CACHE: Dict[str, Any] = {}


def _parse_positional_cell_id(text: str) -> Optional[int]:
    """Parse a positional cell reference. Supports '0', '42', 'cell_000', 'cell_999' etc."""
    t = str(text).strip()
    if t.isdigit():
        return int(t)
    if t.lower().startswith("cell_") or t.lower().startswith("cell-"):
        suffix = t[5:]
        if suffix.isdigit():
            return int(suffix)
    return None


def _align_cell_id_table_to_obs(value: Any, obs_names: List[str]) -> Tuple[Any, bool]:
    try:
        import pandas as pd
    except Exception:
        return value, False

    if value is None:
        return value, False
    try:
        df = pd.DataFrame(value).copy()
    except Exception:
        return value, False
    if "cell_id" not in df.columns or df.empty:
        return value, False

    ids = df["cell_id"].astype(str)
    obs_set = set(str(name) for name in obs_names)
    if set(ids.dropna().unique()).issubset(obs_set):
        return df, False

    mapped_values = []
    for cell_id in ids:
        pos = _parse_positional_cell_id(cell_id)
        if pos is None or pos < 0 or pos >= len(obs_names):
            return value, False
        mapped_values.append(obs_names[pos])

    df["cell_id"] = mapped_values
    return df, True


def _align_cell_id_list_to_obs(value: Any, obs_names: List[str]) -> Tuple[Any, bool]:
    values = _as_sequence(value)
    if not values:
        return value, False

    obs_set = set(str(name) for name in obs_names)
    as_text = [str(item) for item in values]
    if set(as_text).issubset(obs_set):
        return value, False

    mapped_values = []
    for cell_id in as_text:
        pos = _parse_positional_cell_id(cell_id)
        if pos is None or pos < 0 or pos >= len(obs_names):
            return value, False
        mapped_values.append(obs_names[pos])
    return mapped_values, True


def _align_positional_trajectory_cell_ids(fadata: Any) -> int:
    obs = getattr(fadata, "obs", None)
    if obs is None or not hasattr(obs, "index"):
        return 0

    obs_names = [str(name) for name in obs.index.tolist()]
    aligned_count = 0
    for model_name in getattr(fadata, "get_all_model_name", lambda parse=False: [])(parse=False):
        trajectory_dict = getattr(fadata, "get_trajectory_dict", lambda *_: None)(model_name)
        if not isinstance(trajectory_dict, dict):
            continue

        milestone_wrapper = trajectory_dict.get("milestone_wrapper")
        if milestone_wrapper is None:
            continue

        changed = False
        for attr_name in ("milestone_percentages", "progressions"):
            table = _get_item_attr(milestone_wrapper, attr_name)
            aligned_table, table_changed = _align_cell_id_table_to_obs(table, obs_names)
            if table_changed:
                try:
                    setattr(milestone_wrapper, attr_name, aligned_table)
                    changed = True
                except Exception:
                    pass

        cell_id_list, list_changed = _align_cell_id_list_to_obs(
            _get_item_attr(milestone_wrapper, "cell_id_list"), obs_names
        )
        if list_changed:
            try:
                setattr(milestone_wrapper, "cell_id_list", cell_id_list)
                changed = True
            except Exception:
                pass

        if changed:
            try:
                setattr(milestone_wrapper, "_cell_color_dict", None)
            except Exception:
                pass
            trajectory_dict["milestone_wrapper"] = milestone_wrapper
            try:
                getattr(fadata, "set_trajectory_dict")(trajectory_dict, model_name)
                aligned_count += 1
            except Exception:
                pass

    return aligned_count


def _load_uns_dict() -> Dict[str, Any]:
    data_adaptor = current_app.data_adaptor

    if hasattr(data_adaptor, "get_uns"):
        uns_raw = data_adaptor.get_uns()
    elif hasattr(data_adaptor, "data") and hasattr(data_adaptor.data, "uns"):
        uns_raw = data_adaptor.data.uns
    else:
        return {}

    if isinstance(uns_raw, bytes):
        uns_raw = uns_raw.decode("utf-8")

    if isinstance(uns_raw, str):
        try:
            parsed = json.loads(uns_raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    if isinstance(uns_raw, dict):
        if "uns" in uns_raw and isinstance(uns_raw.get("uns"), dict):
            return uns_raw["uns"]
        return uns_raw

    if hasattr(uns_raw, "keys"):
        try:
            as_dict = dict(uns_raw)
            if "uns" in as_dict and isinstance(as_dict.get("uns"), dict):
                return as_dict["uns"]
            return as_dict
        except Exception:
            return {}

    try:
        parsed = json.loads(str(uns_raw))
        if isinstance(parsed, dict):
            if "uns" in parsed and isinstance(parsed.get("uns"), dict):
                return parsed["uns"]
            return parsed
    except Exception:
        pass
    return {}

def _trajectory_history_dict(uns: Dict[str, Any]) -> Dict[str, Any]:
    cafe_obj = uns.get("cafe") or uns.get("cfe") or {}
    trajectory_history_dict = cafe_obj.get("trajectory_history_dict", {})
    if not isinstance(trajectory_history_dict, dict):
        return {}
    return trajectory_history_dict

def _merge_uns_sources(*sources: Tuple[Dict[str, Any], Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    merged_uns: Dict[str, Any] = {}
    merged_cafe: Dict[str, Any] = {}
    merged_history: Dict[str, Any] = {}

    for uns, history in sources:
        uns_dict = _safe_dict(uns)
        if not uns_dict:
            continue
        merged_uns.update(uns_dict)

        cafe_container = _get_cafe_container(uns_dict)
        if cafe_container:
            merged_cafe.update(_safe_dict(cafe_container))

        if history:
            merged_history.update(_safe_dict(history))

    if merged_cafe or merged_history:
        merged_cafe = dict(merged_cafe)
        if merged_history:
            merged_cafe["trajectory_history_dict"] = merged_history
        merged_uns["cafe"] = merged_cafe

    return merged_uns, merged_history

def _load_uns_from_dataset_file() -> Dict[str, Any]:
    datapath = current_app.app_config.server_config.single_dataset__datapath
    if not datapath or not os.path.exists(datapath):
        return {}

    try:
        import anndata as ad

        adata = ad.read_h5ad(datapath, backed="r")
        uns_raw = adata.uns
        uns_dict = dict(uns_raw) if hasattr(uns_raw, "keys") else {}

        try:
            if getattr(adata, "file", None) is not None:
                adata.file.close()
        except Exception:
            pass

        return uns_dict if isinstance(uns_dict, dict) else {}
    except Exception:
        return {}

def _load_effective_trajectory_history() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    uns = _load_uns_dict()
    trajectory_history = _trajectory_history_dict(uns)

    uns_from_file = _load_uns_from_dataset_file()
    trajectory_history_from_file = _trajectory_history_dict(uns_from_file)

    bridged_uns = _load_bridged_uns_from_cafe_dataset()
    bridged_trajectory_history = _trajectory_history_dict(bridged_uns)
    merged_uns, merged_history = _merge_uns_sources(
        (bridged_uns, bridged_trajectory_history),
        (uns_from_file, trajectory_history_from_file),
        (uns, trajectory_history),
    )
    if merged_history:
        return merged_uns, merged_history

    return uns, trajectory_history

def _layout_names(entry: Dict[str, Any]) -> List[str]:
    trajectory_embedding = entry.get("trajectory_embedding", {})
    if not isinstance(trajectory_embedding, dict):
        return []
    return sorted(trajectory_embedding.keys())

def _preview_basis_candidates(layout_name: str, fadata: Any) -> List[str]:
    candidates: List[str] = []
    if layout_name:
        candidates.append(str(layout_name))
    if fadata is not None:
        prior_information = getattr(fadata, "prior_information", None)
        if isinstance(prior_information, dict) and prior_information.get("basis"):
            candidates.append(str(prior_information.get("basis")))
    normalized: List[str] = []
    seen = set()
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        for candidate in (text, text[2:] if text.startswith("X_") else f"X_{text}"):
            candidate_text = str(candidate).strip()
            if candidate_text and candidate_text not in seen:
                normalized.append(candidate_text)
                seen.add(candidate_text)
    return normalized

def _build_benchmark_rows(trajectory_history: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    rows: List[Dict[str, Any]] = []
    metric_keys = set()

    for trajectory_name, payload in trajectory_history.items():
        metric_dict = payload.get("metric_dict", {}) if isinstance(payload, dict) else {}
        resource_metric_keys = _available_resource_metric_keys(payload)
        row: Dict[str, Any] = {"id": trajectory_name}
        if isinstance(metric_dict, dict):
            for key, value in metric_dict.items():
                if key in {"time", "memory"} and key not in resource_metric_keys:
                    continue
                metric_keys.add(key)
                if isinstance(value, (int, float)):
                    row[key] = _as_float(value, default=0.0)
                else:
                    row[key] = _to_json_value(value)
        rows.append(row)

    return rows, sorted(metric_keys)

def _available_resource_metric_keys(payload: Any) -> set:
    resource_usage = _safe_dict(_get_item_attr(payload, "resource_usage", {}))
    available = set()
    for key in ("time", "memory"):
        ok, number = _try_numeric(resource_usage.get(key))
        if ok and number >= 0:
            available.add(key)
    return available

def _has_numeric_metric_dict(payload: Any) -> bool:
    metric_dict = payload.get("metric_dict", {}) if isinstance(payload, dict) else {}
    if not isinstance(metric_dict, dict):
        return False
    resource_metric_keys = _available_resource_metric_keys(payload)
    for key, value in metric_dict.items():
        key = str(key)
        if key in {"time", "memory"} and key not in resource_metric_keys:
            continue
        ok, number = _try_numeric(value)
        if ok:
            try:
                import math

                if math.isfinite(number):
                    return True
            except Exception:
                return True
    return False

def _row_to_numeric_metric_dict(row: Any) -> Dict[str, Any]:
    metric_dict: Dict[str, Any] = {}
    if row is None:
        return metric_dict
    for key, value in getattr(row, "items", lambda: [])():
        ok, number = _try_numeric(value)
        if not ok:
            continue
        try:
            import math

            if not math.isfinite(number):
                continue
        except Exception:
            pass
        metric_dict[str(key)] = _to_json_value(number)
    return metric_dict

def _drop_missing_resource_metrics(payload: Any, metric_dict: Dict[str, Any]) -> Dict[str, Any]:
    available = _available_resource_metric_keys(payload)
    cleaned = dict(metric_dict)
    for key in ("time", "memory"):
        if key not in available:
            cleaned.pop(key, None)
    return cleaned

def _dataset_meta() -> Dict[str, Any]:
    data_adaptor = current_app.data_adaptor
    app_config = current_app.app_config
    server_cfg = app_config.server_config

    dataset_id = os.path.basename(server_cfg.single_dataset__datapath or "")
    dataset_name = app_config.get_title(data_adaptor)

    return {
        "id": dataset_id or "dataset",
        "name": dataset_name or dataset_id or "dataset",
    }


def _data_model_meta() -> Dict[str, Any]:
    adata = _get_live_adata()
    if adata is None:
        return {"kind": "unknown", "isFateAnnData": False, "requiresFateConversion": False}

    uns = _safe_dict(getattr(adata, "uns", {}))
    class_name = type(adata).__name__
    has_cafe_state = "cafe" in uns
    is_fate = class_name == "FateAnnData" or has_cafe_state
    return {
        "kind": "FateAnnData" if is_fate else "AnnData",
        "isFateAnnData": is_fate,
        "requiresFateConversion": not is_fate,
    }

def _get_live_adata() -> Any:
    data_adaptor = current_app.data_adaptor
    return getattr(data_adaptor, "data", None)

def _trajectory_layout_union(trajectory_history: Dict[str, Any]) -> List[str]:
    layout_names = set()
    for payload in trajectory_history.values():
        trajectory_embedding = _safe_dict(_get_item_attr(payload, "trajectory_embedding", {}))
        layout_names.update(str(key) for key in trajectory_embedding.keys())
    return sorted(layout_names)

def _serialize_trajectory_dict_for_uns(trajectory_dict: Dict[str, Any]) -> Dict[str, Any]:
    serialized = dict(trajectory_dict or {})
    raw_wrapper_dict = _safe_dict(serialized.get("raw_wrapper_dict", {}))
    if raw_wrapper_dict.get("wrapper_type"):
        serialized["original_wrapper_type"] = str(raw_wrapper_dict.get("wrapper_type", ""))

    milestone_wrapper = serialized.get("milestone_wrapper")
    if milestone_wrapper is not None and hasattr(milestone_wrapper, "__dict__"):
        serialized["milestone_wrapper"] = dict(milestone_wrapper.__dict__)

    waypoint_wrapper = serialized.get("waypoint_wrapper")
    if waypoint_wrapper is not None and hasattr(waypoint_wrapper, "__dict__"):
        waypoint_payload = dict(waypoint_wrapper.__dict__)
        waypoint_payload.pop("milestone_wrapper", None)
        waypoints = waypoint_payload.get("waypoints")
        if hasattr(waypoints, "replace"):
            try:
                waypoint_payload["waypoints"] = waypoints.replace({None: ""})
            except Exception:
                pass
        serialized["waypoint_wrapper"] = waypoint_payload

    if "raw_wrapper_dict" in serialized:
        serialized["raw_wrapper_dict"] = {}

    return serialized

def _normalize_export_trajectory_history(trajectory_history: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized = {}
    for name, payload in trajectory_history.items():
        key = str(name)
        if isinstance(payload, dict):
            normalized[key] = _serialize_trajectory_dict_for_uns(payload)
        elif hasattr(payload, "keys"):
            try:
                normalized[key] = _serialize_trajectory_dict_for_uns(dict(payload))
            except Exception:
                normalized[key] = {}
        elif payload is None:
            normalized[key] = {}
        else:
            normalized[key] = {}
    return normalized

def _extract_obs_color_mappings(adata: Any, uns: Dict[str, Any]) -> List[Dict[str, Any]]:
    mappings = []
    for key in sorted(uns.keys()):
        if not str(key).endswith("_colors"):
            continue
        obs_key = str(key)[:-7]
        colors = uns.get(key)
        colors = _as_sequence(colors)
        if not colors:
            continue
        labels = _series_labels_for_colors(adata, obs_key)
        if not labels:
            labels = [str(index) for index in range(len(colors))]
        items = []
        for idx, color in enumerate(colors):
            label = labels[idx] if idx < len(labels) else str(idx)
            items.append({"label": label, "color": _normalize_color(color)})
        mappings.append(
            {
                "key": obs_key,
                "kind": "obs",
                "size": len(items),
                "items": _sample_items(items),
            }
        )
    return mappings

def _extract_milestone_color_mappings(trajectory_history: Dict[str, Any]) -> List[Dict[str, Any]]:
    mappings = []
    for trajectory_name, payload in trajectory_history.items():
        milestone_wrapper = _get_item_attr(payload, "milestone_wrapper")
        if milestone_wrapper is None:
            continue

        id_list = _as_sequence(_get_item_attr(milestone_wrapper, "id_list", []))
        color_list = _as_sequence(_get_item_attr(milestone_wrapper, "color_list", []))
        if not id_list and hasattr(milestone_wrapper, "milestone_color_dict"):
            try:
                milestone_color_dict = dict(getattr(milestone_wrapper, "milestone_color_dict"))
            except Exception:
                milestone_color_dict = {}
            items = [
                {"label": str(label), "color": _normalize_color(color)}
                for label, color in milestone_color_dict.items()
            ]
        else:
            items = []
            for idx, milestone_id in enumerate(id_list):
                color = color_list[idx] if idx < len(color_list) else "#9aa7b0"
                items.append({"label": str(milestone_id), "color": _normalize_color(color)})

        if not items:
            continue

        mappings.append(
            {
                "key": f"{trajectory_name}:milestones",
                "kind": "milestone",
                "size": len(items),
                "items": _sample_items(items),
            }
        )
    return mappings

def _detect_prior_information(adata: Any) -> Dict[str, Any]:
    prior_information = {}
    obs = getattr(adata, "obs", None)
    obsm = getattr(adata, "obsm", None)
    cluster_candidates = ["clusters", "celltype"]
    basis_candidates = ["X_umap", "X_tsne", "X_pca", "X_emb"]

    if obs is not None and hasattr(obs, "columns"):
        for cluster_candidate in cluster_candidates:
            if cluster_candidate in obs.columns:
                prior_information["cluster"] = cluster_candidate
                break

    if obsm is not None and hasattr(obsm, "keys"):
        obsm_keys = set(obsm.keys())
        for basis_candidate in basis_candidates:
            if basis_candidate in obsm_keys:
                prior_information["basis"] = basis_candidate
                break

    return prior_information

def _load_method_execution_runtime() -> Tuple[Any, Any, str]:
    _ensure_headless_matplotlib()
    try:
        from cafe.data import FateAnnData  # type: ignore
        from cafe.method.fate_method import FateMethod  # type: ignore

        _patch_fate_anndata_velocity_category_compat(FateAnnData)
        _patch_plot_trajectory_title_compat()
        return FateAnnData, FateMethod, ""
    except Exception as error:
        return None, None, str(error)

def _load_cafe_data_runtime() -> Tuple[Dict[str, Any], str]:
    _ensure_headless_matplotlib()
    try:
        import cafe.data as _cafe_data  # type: ignore

        runtime: Dict[str, Any] = {}

        def _try_attr(name: str) -> Any:
            obj = getattr(_cafe_data, name, None)
            if obj is not None:
                runtime[name] = obj
            return obj

        # Required: FateAnnData is the core data model.
        FateAnnData = _try_attr("FateAnnData")
        if FateAnnData is None:
            return {}, "FateAnnData not found in cafe.data"

        # Optional dataset loaders — available vary by cafe version.
        _try_attr("read_bonemarrow")
        _try_attr("read_erythroid_lineage")
        _try_attr("read_gastrulation")
        _try_attr("read_gastrulation_5000")

        # cafe-release source uses read_pancreas; older installed builds use read_pancrease.
        pancreas = _try_attr("read_pancreas")
        if pancreas is None:
            pancreas = _try_attr("read_pancrease")
            if pancreas is not None:
                runtime["read_pancreas"] = pancreas  # normalise key

        return runtime, ""
    except Exception as error:
        return {}, str(error)

def _select_cafe_dataset_loader(datapath: str, adata: Any, runtime: Dict[str, Any]) -> Any:
    filename = os.path.basename(datapath or "").lower()
    parent_text = os.path.dirname(datapath or "").lower()
    shape = _dataset_shape(adata)

    if filename == "endocrinogenesis_day15.h5ad" and shape == {"nObs": 3696, "nVars": 27998}:
        return runtime.get("read_pancreas")
    if filename == "setty_bone_marrow.h5ad":
        return runtime.get("read_bonemarrow")
    if filename == "erythroid_lineage.h5ad":
        return runtime.get("read_erythroid_lineage")
    if filename == "gastrulation.h5ad":
        return runtime.get("read_gastrulation")
    if filename == "gastrulation_5000.h5ad":
        return runtime.get("read_gastrulation_5000")

    if "pancreas" in parent_text and filename == "endocrinogenesis_day15.h5ad" and shape["nVars"] > 10000:
        return runtime.get("read_pancreas")
    return None

def _bridged_cache_key(datapath: str, adata: Any) -> str:
    try:
        mtime = os.path.getmtime(datapath) if datapath and os.path.exists(datapath) else 0
    except OSError:
        mtime = 0
    shape = _dataset_shape(adata)
    return f"{os.path.abspath(datapath or '')}::{mtime}::{shape['nObs']}::{shape['nVars']}"

def _load_bridged_fadata_from_cafe_dataset() -> Any:
    datapath = current_app.app_config.server_config.single_dataset__datapath or ""
    adata = _get_live_adata()
    if adata is None or not datapath:
        return None

    runtime, import_error = _load_cafe_data_runtime()
    if not runtime:
        current_app.logger.warning("CAFE data runtime unavailable for online dataset bridge: %s", import_error)
        return None

    cache_key = _bridged_cache_key(datapath, adata)
    with _WRAPPED_FADATA_LOCK:
        cached = _WRAPPED_FADATA_CACHE.get(cache_key)
    if cached is not None:
        return cached

    loader = _select_cafe_dataset_loader(datapath, adata, runtime)
    if loader is None:
        return None

    try:
        fadata = loader(filename=datapath)
    except Exception as error:
        current_app.logger.warning("Failed to build bridged FateAnnData for '%s': %s", datapath, error)
        return None

    with _WRAPPED_FADATA_LOCK:
        _WRAPPED_FADATA_CACHE.clear()
        _WRAPPED_FADATA_CACHE[cache_key] = fadata
    current_app.logger.info("Built bridged FateAnnData from cafe.data loader for '%s'.", datapath)
    return fadata

def _load_bridged_uns_from_cafe_dataset() -> Dict[str, Any]:
    fadata = _load_bridged_fadata_from_cafe_dataset()
    if fadata is None:
        return {}
    return _safe_dict(getattr(fadata, "uns", {}))

def _load_fate_anndata_runtime() -> Tuple[Any, str]:
    _ensure_headless_matplotlib()
    try:
        from cafe.data import FateAnnData  # type: ignore

        _patch_fate_anndata_velocity_category_compat(FateAnnData)
        _patch_plot_trajectory_title_compat()
        return FateAnnData, ""
    except Exception as error:
        return None, str(error)

def _load_effective_fadata() -> Tuple[Any, str]:
    adata = _get_live_adata()
    if adata is None:
        return None, "Current Cellxgene dataset is unavailable."

    effective_uns, trajectory_history = _load_effective_trajectory_history()
    effective_cafe = _get_cafe_container(effective_uns)

    bridged_fadata = _load_bridged_fadata_from_cafe_dataset()
    if bridged_fadata is not None:
        try:
            merged_cafe = _safe_dict(getattr(bridged_fadata, "uns", {}).get("cafe", {}))
            merged_cafe.update(effective_cafe)
            if trajectory_history:
                merged_cafe["trajectory_history_dict"] = trajectory_history
            bridged_fadata.uns["cafe"] = merged_cafe
            if merged_cafe.get("model_name"):
                bridged_fadata.model_name = str(merged_cafe.get("model_name"))
            _restore_serialized_trajectory_wrappers(bridged_fadata)
        except Exception as error:
            current_app.logger.warning("Failed to merge effective cafe state into bridged FateAnnData: %s", error)
        return bridged_fadata, ""

    FateAnnData, import_error = _load_fate_anndata_runtime()
    if FateAnnData is None:
        return None, f"CAFE runtime is unavailable: {import_error}"

    try:
        fadata = FateAnnData.from_anndata(adata)
        if effective_cafe:
            merged_cafe = _safe_dict(getattr(fadata, "uns", {}).get("cafe", {}))
            merged_cafe.update(effective_cafe)
            if trajectory_history:
                merged_cafe["trajectory_history_dict"] = trajectory_history
            fadata.uns["cafe"] = merged_cafe
            if merged_cafe.get("model_name"):
                fadata.model_name = str(merged_cafe.get("model_name"))
            _restore_serialized_trajectory_wrappers(fadata)
        return fadata, ""
    except Exception as error:
        return None, str(error)

def _source_info(uns: Dict[str, Any]) -> Dict[str, Any]:
    dataset_meta = _dataset_meta()
    datapath = current_app.app_config.server_config.single_dataset__datapath or ""
    dataset_exists = bool(datapath and os.path.exists(datapath))
    dataset_size = 0
    if dataset_exists:
        try:
            dataset_size = int(os.path.getsize(datapath))
        except OSError:
            dataset_size = 0
    return {
        "engine": "cellxgene",
        "datasetPath": datapath,
        "datasetFileName": os.path.basename(datapath) if datapath else "",
        "datasetFileExists": dataset_exists,
        "datasetFileSize": dataset_size,
        "unsFilename": str(uns.get("filename", "")),
        "title": dataset_meta["name"],
    }

def _build_export_fadata() -> Any:
    fadata, fadata_error = _load_effective_fadata()
    if fadata is None:
        raise RuntimeError(fadata_error or "Current Cellxgene dataset is unavailable.")
    effective_uns, trajectory_history = _load_effective_trajectory_history()
    cafe_container = _get_cafe_container(effective_uns)
    normalized_history = _normalize_export_trajectory_history(trajectory_history)
    export_cafe = _safe_dict(getattr(fadata, "uns", {}).get("cafe", {}))
    export_cafe.update(cafe_container)
    export_cafe["trajectory_history_dict"] = normalized_history
    fadata.uns["cafe"] = export_cafe
    if normalized_history:
        fadata.model_name = _best_default(sorted(normalized_history.keys()), ["ref"])
    return fadata

def _resolve_selection(
    trajectory_history: Dict[str, Any],
    requested_trajectory: str,
    requested_layout: str,
) -> Tuple[str, str, Dict[str, Any], List[str], List[str]]:
    trajectory_names = sorted(trajectory_history.keys())
    if not trajectory_names:
        return "", "", {}, [], []

    trajectory_name = (
        requested_trajectory
        if requested_trajectory in trajectory_history
        else _best_default(trajectory_names, ["ref"])
    )
    entry = trajectory_history[trajectory_name]
    layout_names = _layout_names(entry)
    requested_layout_text = str(requested_layout or "").strip()
    layout_name = requested_layout_text or _best_default(layout_names, ["umap", "tsne", "pca"])
    if not layout_name and layout_names:
        layout_name = _best_default(layout_names, ["umap", "tsne", "pca"])
    return trajectory_name, layout_name, entry, trajectory_names, layout_names
