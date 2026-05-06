"""Utility helpers for the CAFE plugin backend routes."""

import ast
import csv
import json
import os
import shutil
import tempfile
import threading
import time
import traceback
import uuid
import zipfile
from datetime import datetime
from importlib import util as importlib_util
from io import BytesIO
from typing import Any, Dict, List, Tuple

from flask import current_app

_METHOD_JOB_LOCK = threading.Lock()
_METHOD_JOBS: Dict[str, Dict[str, Any]] = {}
_WRAPPED_FADATA_LOCK = threading.Lock()
_WRAPPED_FADATA_CACHE: Dict[str, Any] = {}

_EXPLORER_BENCHMARK_METRICS = [
    "pseudotime_correlation",
    "isomorphic",
    "edge_flip",
    "him",
    "correlation",
    "F1_branches",
    "F1_milestones",
    "time",
    "memory",
]

_EXPLORER_GENE_SETS = [
    {
        "name": "T cell differentiation",
        "category": "immune",
        "genes": ["CD3D", "CD3E", "CD4", "CD8A", "IL7R", "CCR7", "TCF7", "GATA3", "TBX21", "FOXP3"],
    },
    {
        "name": "Cytotoxic lymphocyte program",
        "category": "immune",
        "genes": ["NKG7", "GNLY", "GZMB", "GZMA", "PRF1", "IFNG", "KLRD1", "KLRB1"],
    },
    {
        "name": "Interferon response",
        "category": "pathway",
        "genes": ["ISG15", "IFIT1", "IFIT2", "IFIT3", "MX1", "OAS1", "STAT1", "IRF7", "IFI6", "CXCL10"],
    },
    {
        "name": "Cell cycle G2M",
        "category": "pathway",
        "genes": ["MKI67", "TOP2A", "CENPF", "NUSAP1", "UBE2C", "CCNB1", "BIRC5", "CDK1", "AURKB"],
    },
    {
        "name": "Epithelial identity",
        "category": "lineage",
        "genes": ["EPCAM", "KRT8", "KRT18", "KRT19", "MUC1", "CLDN4", "CDH1"],
    },
    {
        "name": "EMT and migration",
        "category": "pathway",
        "genes": ["VIM", "FN1", "SNAI1", "SNAI2", "ZEB1", "ZEB2", "TWIST1", "ITGA5", "COL1A1"],
    },
    {
        "name": "Hypoxia response",
        "category": "pathway",
        "genes": ["HIF1A", "VEGFA", "CA9", "LDHA", "SLC2A1", "ENO1", "PGK1", "BNIP3"],
    },
    {
        "name": "Apoptosis",
        "category": "pathway",
        "genes": ["BAX", "BAK1", "CASP3", "CASP8", "CASP9", "FAS", "BCL2", "BID", "PMAIP1"],
    },
    {
        "name": "Myeloid activation",
        "category": "immune",
        "genes": ["LYZ", "S100A8", "S100A9", "FCGR3A", "LST1", "CTSS", "TYROBP", "AIF1", "CST3"],
    },
]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _best_default(items: List[str], preferred: List[str]) -> str:
    if not items:
        return ""
    item_set = {x.lower(): x for x in items}
    for name in preferred:
        if name.lower() in item_set:
            return item_set[name.lower()]
    return items[0]


def _to_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value

    if hasattr(value, "item"):
        try:
            return _to_json_value(value.item())
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]

    return str(value)


def _rows_from_maybe_table(value: Any) -> List[Dict[str, Any]]:
    if hasattr(value, "to_dict"):
        try:
            records = value.to_dict("records")
            if isinstance(records, list):
                return [row for row in records if isinstance(row, dict)]
        except Exception:
            pass

    if isinstance(value, list):
        rows = []
        for row in value:
            if isinstance(row, dict):
                rows.append({str(k): _to_json_value(v) for k, v in row.items()})
        return rows

    if isinstance(value, dict):
        if value and all(isinstance(v, list) for v in value.values()):
            keys = list(value.keys())
            row_count = min(len(value[k]) for k in keys)
            rows: List[Dict[str, Any]] = []
            for i in range(row_count):
                rows.append({str(k): _to_json_value(value[k][i]) for k in keys})
            return rows
        return [{str(k): _to_json_value(v) for k, v in value.items()}]

    return []


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


def _ensure_preview_layout_payload(entry: Dict[str, Any], layout_name: str, trajectory_name: str) -> Dict[str, Any]:
    _, effective_wrapper_type = _entry_wrapper_type(trajectory_name, entry)
    if str(effective_wrapper_type).lower() == "velocity":
        return {}

    trajectory_embedding = _safe_dict(_get_item_attr(entry, "trajectory_embedding", {}))
    layout_payload = trajectory_embedding.get(layout_name, {}) if isinstance(trajectory_embedding, dict) else {}
    milestone_rows = _rows_from_maybe_table(layout_payload.get("milestone_positions", []))
    waypoint_rows = _rows_from_maybe_table(layout_payload.get("wp_segments", []))
    if milestone_rows or waypoint_rows:
        return layout_payload if isinstance(layout_payload, dict) else {}

    fadata, fadata_error = _load_effective_fadata()
    if fadata is None:
        current_app.logger.warning("Unable to build preview layout for trajectory '%s': %s", trajectory_name, fadata_error)
        return layout_payload if isinstance(layout_payload, dict) else {}

    if trajectory_name:
        try:
            fadata.model_name = trajectory_name
        except Exception:
            pass

    try:
        import cafe

        plot_ns = getattr(cafe, "plot", None)
        alt_plot_ns = getattr(cafe, "pl", None)
        plot_trajectory_func = None
        if plot_ns is not None and hasattr(plot_ns, "plot_trajectory"):
            plot_trajectory_func = plot_ns.plot_trajectory
        elif alt_plot_ns is not None and hasattr(alt_plot_ns, "plot_trajectory"):
            plot_trajectory_func = alt_plot_ns.plot_trajectory
        if plot_trajectory_func is None:
            return layout_payload if isinstance(layout_payload, dict) else {}

        last_error = None
        for basis in _preview_basis_candidates(layout_name, fadata):
            for kwargs in (
                {
                    "model_name": trajectory_name or None,
                    "basis": basis,
                    "color": "clusters",
                    "show_milestone_labels": False,
                },
                {
                    "model_name": trajectory_name or None,
                    "basis": basis,
                    "show_milestone_labels": False,
                },
                {
                    "basis": basis,
                    "color": "clusters",
                    "show_milestone_labels": False,
                },
                {
                    "basis": basis,
                    "show_milestone_labels": False,
                },
            ):
                try:
                    plot_trajectory_func(fadata, **kwargs)
                    refreshed_entry = _safe_dict(fadata.get_trajectory_dict(trajectory_name or getattr(fadata, "model_name", "")))
                    refreshed_embedding = _safe_dict(_get_item_attr(refreshed_entry, "trajectory_embedding", {}))
                    preferred_basis = kwargs.get("basis")
                    if preferred_basis in refreshed_embedding:
                        return _safe_dict(refreshed_embedding.get(preferred_basis, {}))
                    if layout_name in refreshed_embedding:
                        return _safe_dict(refreshed_embedding.get(layout_name, {}))
                    for candidate in _preview_basis_candidates(layout_name, fadata):
                        if candidate in refreshed_embedding:
                            return _safe_dict(refreshed_embedding.get(candidate, {}))
                    if refreshed_embedding:
                        first_key = next(iter(refreshed_embedding.keys()))
                        return _safe_dict(refreshed_embedding.get(first_key, {}))
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
            if last_error is None:
                break
        if last_error is not None:
            current_app.logger.warning(
                "Failed to compute trajectory embedding for preview trajectory='%s' layout='%s': %s",
                trajectory_name,
                layout_name,
                last_error,
            )
    except Exception as error:
        current_app.logger.warning(
            "Failed to initialize cafe runtime for preview trajectory='%s' layout='%s': %s",
            trajectory_name,
            layout_name,
            error,
        )
    return layout_payload if isinstance(layout_payload, dict) else {}


def _build_preview(entry: Dict[str, Any], layout_name: str, trajectory_name: str = "") -> Dict[str, Any]:
    layout_payload = _ensure_preview_layout_payload(entry, layout_name, trajectory_name)

    milestone_rows = _rows_from_maybe_table(layout_payload.get("milestone_positions", []))
    waypoint_rows = _rows_from_maybe_table(layout_payload.get("wp_segments", []))
    milestone_rows, waypoint_rows = _normalize_overlay_rows_for_host(
        milestone_rows,
        waypoint_rows,
        layout_name,
    )

    milestone_wrapper = _get_item_attr(entry, "milestone_wrapper", {})
    id_list = _as_sequence(_get_item_attr(milestone_wrapper, "id_list", []))
    color_list = _as_sequence(_get_item_attr(milestone_wrapper, "color_list", []))
    color_by_id = {
        str(mid): color_list[idx]
        for idx, mid in enumerate(id_list)
        if idx < len(color_list)
    }

    node_map: Dict[str, Dict[str, Any]] = {}
    edge_map: Dict[str, Dict[str, Any]] = {}

    for row in milestone_rows:
        node_id = str(row.get("milestone_id", ""))
        if node_id and node_id not in node_map:
            node_map[node_id] = {
                "id": node_id,
                "label": node_id,
                "x": _as_float(row.get("comp_1")),
                "y": _as_float(row.get("comp_2")),
                "color": color_by_id.get(node_id, "#9aa7b0"),
            }

        group_id = str(row.get("group", ""))
        if group_id and group_id not in edge_map:
            edge_map[group_id] = {
                "id": group_id,
                "source": str(row.get("from", "")),
                "target": str(row.get("to", "")),
                "label": group_id,
            }

    segment_map: Dict[str, List[Dict[str, Any]]] = {}
    for row in waypoint_rows:
        group_id = str(row.get("group", ""))
        if not group_id:
            continue
        segment_map.setdefault(group_id, []).append(
            {
                "x": _as_float(row.get("comp_1")),
                "y": _as_float(row.get("comp_2")),
                "percentage": _as_float(row.get("percentage"), default=0.0),
            }
        )

    for points in segment_map.values():
        points.sort(key=lambda p: p["percentage"], reverse=True)

    return {
        "nodes": list(node_map.values()),
        "edges": list(edge_map.values()),
        "waypointSegments": segment_map,
        "milestonePositions": milestone_rows,
        "wpSegments": waypoint_rows,
    }


def _normalize_overlay_rows_for_host(
    milestone_rows: List[Dict[str, Any]],
    waypoint_rows: List[Dict[str, Any]],
    layout_name: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    adata = _get_live_adata()
    obsm = getattr(adata, "obsm", None)
    if adata is None or obsm is None:
        return milestone_rows, waypoint_rows

    layout_key = ""
    for candidate in (layout_name, f"X_{layout_name}" if layout_name and not str(layout_name).startswith("X_") else ""):
        text = str(candidate or "").strip()
        if text and text in obsm:
            layout_key = text
            break

    if not layout_key:
        return milestone_rows, waypoint_rows

    try:
        import numpy as np

        coords = np.asarray(obsm[layout_key])
        if coords.ndim != 2 or coords.shape[1] < 2 or coords.shape[0] == 0:
            return milestone_rows, waypoint_rows

        finite_mask = np.isfinite(coords[:, 0]) & np.isfinite(coords[:, 1])
        if not np.any(finite_mask):
            return milestone_rows, waypoint_rows

        finite_coords = coords[finite_mask]
        min_x = float(np.min(finite_coords[:, 0]))
        max_x = float(np.max(finite_coords[:, 0]))
        min_y = float(np.min(finite_coords[:, 1]))
        max_y = float(np.max(finite_coords[:, 1]))
    except Exception:
        return milestone_rows, waypoint_rows

    if max_x <= min_x or max_y <= min_y:
        return milestone_rows, waypoint_rows

    pad = 0.04
    span_x = max_x - min_x
    span_y = max_y - min_y
    span = max(span_x, span_y)
    if span <= 0:
        return milestone_rows, waypoint_rows

    usable = 1 - 2 * pad
    offset_x = pad + (usable - (span_x / span) * usable) / 2
    offset_y = pad + (usable - (span_y / span) * usable) / 2

    def _scale(value: Any, low: float, offset: float) -> Any:
        number = _as_float(value, default=None)
        if number is None:
            return value
        normalized = (float(number) - low) / span
        normalized = offset + normalized * usable
        return round(normalized, 6)

    def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_rows: List[Dict[str, Any]] = []
        for row in rows:
            next_row = dict(row)
            next_row["comp_1"] = _scale(row.get("comp_1"), min_x, offset_x)
            next_row["comp_2"] = _scale(row.get("comp_2"), min_y, offset_y)
            normalized_rows.append(next_row)
        return normalized_rows

    return _normalize_rows(milestone_rows), _normalize_rows(waypoint_rows)


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


def _try_numeric(value: Any) -> Tuple[bool, float]:
    if value is None or isinstance(value, bool):
        return False, 0.0
    if isinstance(value, (int, float)):
        return True, float(value)
    try:
        text = str(value).strip()
        if not text:
            return False, 0.0
        return True, float(text)
    except (TypeError, ValueError):
        return False, 0.0


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
        text = str(cell_id)
        if not text.isdigit():
            return value, False
        position = int(text)
        if position < 0 or position >= len(obs_names):
            return value, False
        mapped_values.append(obs_names[position])

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
        if not cell_id.isdigit():
            return value, False
        position = int(cell_id)
        if position < 0 or position >= len(obs_names):
            return value, False
        mapped_values.append(obs_names[position])
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

        cell_id_list, list_changed = _align_cell_id_list_to_obs(_get_item_attr(milestone_wrapper, "cell_id_list"), obs_names)
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


def _merge_metric_dict_into_live_adata(
    trajectory_history: Dict[str, Any],
    trajectory_name: str,
    metric_dict: Dict[str, Any],
) -> None:
    adata = _get_live_adata()
    if adata is None or not hasattr(adata, "uns"):
        return
    if "cafe" not in adata.uns or not isinstance(adata.uns.get("cafe"), dict):
        adata.uns["cafe"] = {}

    cafe_container = adata.uns["cafe"]
    live_history = cafe_container.get("trajectory_history_dict")
    if not isinstance(live_history, dict):
        live_history = {}
        cafe_container["trajectory_history_dict"] = live_history

    payload = trajectory_history.get(trajectory_name, {})
    if isinstance(payload, dict):
        live_payload = _serialize_trajectory_dict_for_uns(payload)
    else:
        live_payload = {}
    live_payload["metric_dict"] = dict(metric_dict)
    live_history[trajectory_name] = live_payload


def _ensure_explorer_benchmark_metrics(trajectory_history: Dict[str, Any]) -> Dict[str, Any]:
    status = {
        "attempted": False,
        "calculated": [],
        "skipped": [],
        "message": "",
    }
    if not trajectory_history or "ref" not in trajectory_history:
        status["message"] = "Reference trajectory 'ref' is required before metric calculation."
        return status

    target_models = [
        str(name)
        for name, payload in trajectory_history.items()
        if str(name) != "ref" and not _has_numeric_metric_dict(payload)
    ]
    if not target_models:
        status["message"] = "Existing metric_dict values are already available."
        return status

    fadata, fadata_error = _load_effective_fadata()
    if fadata is None:
        status["message"] = fadata_error or "Current Cellxgene dataset is unavailable."
        return status

    available_models = set(getattr(fadata, "get_all_model_name", lambda parse=False: [])(parse=False))
    target_models = [name for name in target_models if name in available_models]
    if not target_models:
        status["message"] = "No Explorer trajectory without metrics is available in FateAnnData."
        return status

    status["attempted"] = True
    try:
        _align_positional_trajectory_cell_ids(fadata)
        from cafe.metric import calculate_metrics

        metric_df = calculate_metrics(
            fadata,
            now_models=target_models,
            ref_model="ref",
            metrics=list(_EXPLORER_BENCHMARK_METRICS),
        )
    except Exception as error:
        status["message"] = f"Metric calculation failed: {error}"
        return status

    for model_name in target_models:
        if model_name not in getattr(metric_df, "index", []):
            status["skipped"].append(model_name)
            continue
        metric_dict = _row_to_numeric_metric_dict(metric_df.loc[model_name])
        metric_dict = _drop_missing_resource_metrics(trajectory_history.get(model_name, {}), metric_dict)
        if not metric_dict:
            status["skipped"].append(model_name)
            continue
        try:
            if hasattr(fadata, "add_metric"):
                fadata.add_metric(metric_dict, model_name=model_name)
        except Exception:
            pass
        if model_name in trajectory_history and isinstance(trajectory_history[model_name], dict):
            trajectory_history[model_name]["metric_dict"] = dict(metric_dict)
        _merge_metric_dict_into_live_adata(trajectory_history, model_name, metric_dict)
        status["calculated"].append(model_name)

    if status["calculated"]:
        status["message"] = f"Calculated benchmark metrics for: {', '.join(status['calculated'])}."
    elif status["skipped"]:
        status["message"] = "Metric calculation ran, but all computed values were empty or non-numeric."
    else:
        status["message"] = "No metrics were calculated."
    return status


def _integration_payload_count(trajectory_history: Dict[str, Any], keys: List[str]) -> int:
    count = 0
    normalized_keys = {str(key).lower() for key in keys}
    for payload in trajectory_history.values():
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if str(key).lower() not in normalized_keys:
                continue
            if value is None:
                continue
            if isinstance(value, dict) and not value:
                continue
            if isinstance(value, list) and not value:
                continue
            rows = _rows_from_maybe_table(value)
            count += len(rows) if rows else 1
    return count


def _top_driver_gene_names(driver_genes: Dict[str, Any], limit: int = 50) -> List[str]:
    genes = []
    seen = set()
    for item in driver_genes.get("items") or []:
        gene = str(item.get("gene", "")).strip()
        if gene and gene not in seen:
            genes.append(gene)
            seen.add(gene)
        if len(genes) >= limit:
            break
    return genes


def _compute_grn_fallback(driver_genes: Dict[str, Any], max_genes: int = 16, max_edges: int = 32) -> Dict[str, Any]:
    import numpy as np

    adata = _get_live_adata()
    if adata is None or not driver_genes.get("available"):
        return {"enabled": False, "itemCount": 0, "items": [], "message": "No driver genes are available for GRN fallback."}

    var_names = [str(name) for name in getattr(adata, "var_names", [])]
    var_index = {gene: index for index, gene in enumerate(var_names)}
    genes = [gene for gene in _top_driver_gene_names(driver_genes, limit=max_genes * 2) if gene in var_index][:max_genes]
    if len(genes) < 2:
        return {"enabled": False, "itemCount": 0, "items": [], "message": "Not enough driver genes are present in AnnData.var_names for GRN fallback."}

    gene_indices = [var_index[gene] for gene in genes]
    matrix = _extract_dense_gene_matrix(adata, gene_indices)
    if matrix.shape[0] < 3 or matrix.shape[1] < 2:
        return {"enabled": False, "itemCount": 0, "items": [], "message": "Not enough expression data are available for GRN fallback."}

    std = np.nanstd(matrix, axis=0)
    keep = std > 0
    genes = [gene for gene, keep_gene in zip(genes, keep) if bool(keep_gene)]
    matrix = matrix[:, keep]
    if matrix.shape[1] < 2:
        return {"enabled": False, "itemCount": 0, "items": [], "message": "Driver gene expression is constant, so GRN fallback cannot be computed."}

    corr = np.corrcoef(matrix, rowvar=False)
    edges = []
    for i in range(len(genes)):
        for j in range(i + 1, len(genes)):
            weight = float(corr[i, j])
            if not np.isfinite(weight):
                continue
            edges.append(
                {
                    "source": genes[i],
                    "target": genes[j],
                    "weight": round(weight, 4),
                    "absWeight": round(abs(weight), 4),
                    "sign": "positive" if weight >= 0 else "negative",
                }
            )

    edges.sort(key=lambda item: (-item["absWeight"], item["source"], item["target"]))
    edges = edges[:max_edges]
    return {
        "enabled": bool(edges),
        "itemCount": len(edges),
        "items": edges,
        "message": (
            "Computed fallback co-expression GRN from top driver genes."
            if edges
            else "No finite driver-gene correlations were available for GRN fallback."
        ),
    }


def _hypergeom_tail(overlap: int, background_size: int, gene_set_size: int, selected_size: int) -> float:
    try:
        from scipy.stats import hypergeom

        return float(hypergeom.sf(overlap - 1, background_size, gene_set_size, selected_size))
    except Exception:
        return 1.0


def _compute_gene_set_fallback(driver_genes: Dict[str, Any], categories: List[str], label: str) -> Dict[str, Any]:
    import math

    adata = _get_live_adata()
    if adata is None or not driver_genes.get("available"):
        return {"enabled": False, "itemCount": 0, "items": [], "message": f"No driver genes are available for {label} fallback."}

    background = {str(name).upper() for name in getattr(adata, "var_names", [])}
    ordered_selected = [gene.upper() for gene in _top_driver_gene_names(driver_genes, limit=80)]
    selected = set(ordered_selected)
    selected &= background
    if not selected:
        return {"enabled": False, "itemCount": 0, "items": [], "message": f"No selected driver genes are present in AnnData.var_names for {label} fallback."}

    rows = []
    category_set = set(categories)
    for gene_set in _EXPLORER_GENE_SETS:
        if gene_set["category"] not in category_set:
            continue
        genes = {gene.upper() for gene in gene_set["genes"]} & background
        overlap_genes = sorted(selected & genes)
        if not overlap_genes:
            continue
        p_value = _hypergeom_tail(len(overlap_genes), len(background), len(genes), len(selected))
        score = -math.log10(max(p_value, 1e-300))
        rows.append(
            {
                "term": gene_set["name"],
                "category": gene_set["category"],
                "overlap": len(overlap_genes),
                "setSize": len(genes),
                "selectedSize": len(selected),
                "pValue": p_value,
                "score": round(score, 4),
                "genes": ", ".join(overlap_genes[:12]),
            }
        )

    rows.sort(key=lambda item: (-item["score"], item["term"]))
    if not rows:
        fallback_genes = [gene for gene in ordered_selected if gene in selected][:20]
        if fallback_genes:
            term = "Trajectory driver gene program" if label == "enrichment" else "Trajectory-associated pathway signature"
            rows.append(
                {
                    "term": term,
                    "category": "data_driven",
                    "overlap": len(fallback_genes),
                    "setSize": len(fallback_genes),
                    "selectedSize": len(selected),
                    "pValue": None,
                    "score": round(len(fallback_genes) / max(len(selected), 1), 4),
                    "genes": ", ".join(fallback_genes[:12]),
                }
            )

    return {
        "enabled": bool(rows),
        "itemCount": len(rows),
        "items": rows[:12],
        "message": (
            f"Computed fallback {label} from top driver genes and built-in marker sets."
            if rows and rows[0].get("category") != "data_driven"
            else f"No built-in {label} gene sets overlapped; showing a data-driven driver-gene signature."
        ),
    }


def _build_integration_status(trajectory_history: Dict[str, Any], driver_genes: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    driver_genes = driver_genes or {}
    configs = [
        {
            "key": "grn",
            "label": "GRN",
            "payloadKeys": ["grn", "GRN", "gene_regulatory_network", "geneRegulatoryNetwork"],
            "emptyMessage": "No GRN payload was found in the current trajectory history.",
            "fallback": lambda: _compute_grn_fallback(driver_genes),
        },
        {
            "key": "enrichment",
            "label": "Enrichment",
            "payloadKeys": ["enrichment", "enrichment_results", "enrichmentResults"],
            "emptyMessage": "No enrichment payload was found in the current trajectory history.",
            "fallback": lambda: _compute_gene_set_fallback(driver_genes, ["immune", "lineage", "pathway"], "enrichment"),
        },
        {
            "key": "pathway",
            "label": "Pathway",
            "payloadKeys": ["pathway", "pathway_results", "pathwayResults"],
            "emptyMessage": "No pathway payload was found in the current trajectory history.",
            "fallback": lambda: _compute_gene_set_fallback(driver_genes, ["pathway"], "pathway"),
        },
    ]

    items = []
    for config in configs:
        count = _integration_payload_count(trajectory_history, config["payloadKeys"])
        fallback = {} if count > 0 else config["fallback"]()
        items.append(
            {
                "key": config["key"],
                "label": config["label"],
                "enabled": count > 0 or bool(fallback.get("enabled")),
                "itemCount": count if count > 0 else int(fallback.get("itemCount", 0) or 0),
                "items": fallback.get("items", []),
                "source": "payload" if count > 0 else "computed_fallback",
                "message": (
                    f"Found {count} existing {config['label']} payload item{'s' if count != 1 else ''}."
                    if count > 0
                    else fallback.get("message") or config["emptyMessage"]
                ),
            }
        )
    return items


def _first_present(row: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _build_metric_comparison(rows: List[Dict[str, Any]], metric_keys: List[str]) -> Dict[str, Any]:
    metrics: List[Dict[str, Any]] = []
    overall_scores: Dict[str, float] = {}
    overall_counts: Dict[str, int] = {}
    numeric_metric_count = 0

    for row in rows:
        row_id = str(row.get("id", ""))
        if row_id:
            overall_scores.setdefault(row_id, 0.0)
            overall_counts.setdefault(row_id, 0)

    for key in metric_keys:
        numeric_values = []
        for row in rows:
            row_id = str(row.get("id", ""))
            if not row_id:
                continue
            is_numeric, numeric_value = _try_numeric(row.get(key))
            if is_numeric:
                numeric_values.append({"id": row_id, "value": numeric_value})

        if not numeric_values:
            metrics.append(
                {
                    "key": str(key),
                    "numeric": False,
                    "leader": None,
                    "range": {"min": None, "max": None},
                    "rankings": [],
                    "values": [],
                }
            )
            continue

        numeric_metric_count += 1
        numeric_values.sort(key=lambda item: (-item["value"], item["id"]))
        min_value = min(item["value"] for item in numeric_values)
        max_value = max(item["value"] for item in numeric_values)
        rankings = []
        values = []

        for index, item in enumerate(numeric_values):
            if max_value == min_value:
                normalized = 1.0
            else:
                normalized = (item["value"] - min_value) / (max_value - min_value)
            normalized = round(normalized, 6)
            ranking_item = {
                "rank": index + 1,
                "id": item["id"],
                "value": item["value"],
                "normalized": normalized,
            }
            rankings.append(ranking_item)
            values.append(
                {
                    "id": item["id"],
                    "value": item["value"],
                    "normalized": normalized,
                }
            )
            overall_scores[item["id"]] = overall_scores.get(item["id"], 0.0) + normalized
            overall_counts[item["id"]] = overall_counts.get(item["id"], 0) + 1

        metrics.append(
            {
                "key": str(key),
                "numeric": True,
                "leader": rankings[0],
                "range": {"min": min_value, "max": max_value},
                "rankings": rankings[:8],
                "values": values,
            }
        )

    overall_ranking = []
    for row in rows:
        row_id = str(row.get("id", ""))
        metric_count = overall_counts.get(row_id, 0)
        if not row_id or not metric_count:
            continue
        overall_ranking.append(
            {
                "id": row_id,
                "score": round(overall_scores[row_id] / metric_count, 6),
                "value": round(overall_scores[row_id] / metric_count, 6),
                "normalized": round(overall_scores[row_id] / metric_count, 6),
                "metricCount": metric_count,
            }
        )

    overall_ranking.sort(key=lambda item: (-item["score"], item["id"]))
    for index, item in enumerate(overall_ranking):
        item["rank"] = index + 1

    return {
        "metrics": metrics,
        "numericMetricCount": numeric_metric_count,
        "overallRanking": overall_ranking[:12],
        "rankingHeuristic": "Average normalized numeric metrics; higher values rank first.",
    }


def _extract_driver_genes(trajectory_history: Dict[str, Any]) -> Dict[str, Any]:
    candidate_keys = [
        "driver_genes",
        "driver_gene_df",
        "driver_gene_table",
        "driver_gene_scores",
        "feature_importance",
        "feature_importance_df",
        "feature_importance_table",
        "gene_importance",
    ]
    items = []
    source_keys = []

    for trajectory_name, payload in trajectory_history.items():
        for source_key in candidate_keys:
            raw_value = _get_item_attr(payload, source_key)
            if raw_value is None:
                continue
            rows = _rows_from_maybe_table(raw_value)
            if not rows and isinstance(raw_value, dict):
                rows = [{"gene": key, "score": value} for key, value in raw_value.items()]

            normalized_rows = []
            for index, row in enumerate(rows):
                gene = _first_present(row, ["gene", "symbol", "feature", "name", "id"])
                if not gene:
                    continue

                score = None
                for score_key in ["score", "importance", "weight", "value", "ranking_score"]:
                    is_numeric, numeric_value = _try_numeric(row.get(score_key))
                    if is_numeric:
                        score = numeric_value
                        break

                normalized_rows.append(
                    {
                        "trajectoryId": str(trajectory_name),
                        "gene": gene,
                        "rank": index + 1,
                        "score": score,
                        "sourceKey": source_key,
                    }
                )

            if normalized_rows:
                source_keys.append(source_key)
                items.extend(normalized_rows[:25])
                break

    items.sort(key=lambda item: (item["trajectoryId"], item["rank"], item["gene"]))
    return {
        "available": bool(items),
        "items": items[:80],
        "sourceKeys": sorted(set(source_keys)),
        "message": (
            "Driver gene tables were normalized from trajectory payloads."
            if items
            else "No normalized driver gene table was found in the current trajectory payloads."
        ),
    }


def _build_gene_trend_series_from_rows(
    rows: List[Dict[str, Any]],
    trajectory_name: str,
    source_key: str,
    default_gene: str = "",
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, float]]] = {}

    for row in rows:
        gene = _first_present(row, ["gene", "symbol", "feature", "name"]) or default_gene
        lineage = _first_present(row, ["lineage", "branch", "milestone", "group"])

        x_value = None
        y_value = None
        for key in ["pseudotime", "time", "percentage", "x"]:
            is_numeric, numeric_value = _try_numeric(row.get(key))
            if is_numeric:
                x_value = numeric_value
                break
        for key in ["value", "expression", "trend", "y", "score"]:
            is_numeric, numeric_value = _try_numeric(row.get(key))
            if is_numeric:
                y_value = numeric_value
                break

        if not gene or x_value is None or y_value is None:
            continue

        grouped.setdefault((trajectory_name, gene, lineage), []).append({"x": x_value, "y": y_value})

    series = []
    for (trajectory_id, gene, lineage), points in grouped.items():
        points.sort(key=lambda item: item["x"])
        series.append(
            {
                "trajectoryId": trajectory_id,
                "gene": gene,
                "lineage": lineage,
                "sourceKey": source_key,
                "points": points,
            }
        )

    series.sort(key=lambda item: (item["trajectoryId"], item["gene"], item["lineage"]))
    return series


def _extract_gene_trends(trajectory_history: Dict[str, Any]) -> Dict[str, Any]:
    candidate_keys = [
        "gene_trends",
        "gene_trend_df",
        "gene_trend_table",
        "gene_trend_dict",
        "trend_table",
        "gene_expression_trend",
    ]
    series = []
    source_keys = []

    for trajectory_name, payload in trajectory_history.items():
        for source_key in candidate_keys:
            raw_value = _get_item_attr(payload, source_key)
            if raw_value is None:
                continue

            normalized_series: List[Dict[str, Any]] = []
            rows = _rows_from_maybe_table(raw_value)
            if rows:
                normalized_series = _build_gene_trend_series_from_rows(rows, str(trajectory_name), source_key)
            elif isinstance(raw_value, dict):
                for gene_name, gene_value in raw_value.items():
                    gene_rows = _rows_from_maybe_table(gene_value)
                    if gene_rows:
                        normalized_series.extend(
                            _build_gene_trend_series_from_rows(
                                gene_rows,
                                str(trajectory_name),
                                source_key,
                                default_gene=str(gene_name),
                            )
                        )

            if normalized_series:
                source_keys.append(source_key)
                series.extend(normalized_series[:12])
                break

    series.sort(key=lambda item: (item["trajectoryId"], item["gene"], item["lineage"]))
    return {
        "available": bool(series),
        "series": series[:24],
        "sourceKeys": sorted(set(source_keys)),
        "message": (
            "Gene trend series were normalized from trajectory payloads."
            if series
            else "No normalized gene trend series were found in the current trajectory payloads."
        ),
    }


def _build_explorer_fadata(trajectory_history: Dict[str, Any], trajectory_name: str) -> Tuple[Any, Any, str]:
    adata = _get_live_adata()
    if adata is None:
        return None, None, "Current Cellxgene dataset is unavailable."

    FateAnnData, import_error = _load_fate_anndata_runtime()
    if FateAnnData is None:
        return None, None, f"CAFE runtime is unavailable: {import_error}"

    try:
        adata_snapshot = adata.copy()
        fadata = FateAnnData.from_anndata(adata_snapshot)
        uns = _safe_dict(getattr(fadata, "uns", {}))
        cafe_container = _safe_dict(uns.get("cafe", {}))
        cafe_container["trajectory_history_dict"] = trajectory_history
        if trajectory_name:
            cafe_container["model_name"] = trajectory_name
            fadata.model_name = trajectory_name
        fadata.uns["cafe"] = cafe_container
        _restore_serialized_trajectory_wrappers(fadata)
        return fadata, adata_snapshot, ""
    except Exception as error:
        return None, None, str(error)


def _select_explorer_gene_indices(adata: Any, max_genes: int = 256) -> List[int]:
    var = getattr(adata, "var", None)
    n_vars = int(getattr(adata, "n_vars", 0) or 0)
    if var is None or n_vars <= 0:
        return []

    try:
        columns = set(str(column) for column in getattr(var, "columns", []))
        if "highly_variable" in columns:
            hv_mask = var["highly_variable"].fillna(False).astype(bool)
            hv_indices = [int(index) for index in range(len(hv_mask)) if bool(hv_mask.iloc[index])]
            if hv_indices:
                return hv_indices[:max_genes]
        if "highly_variable_rank" in columns:
            ranked = var["highly_variable_rank"].dropna().sort_values()
            ranked_indices = [int(var.index.get_loc(index)) for index in ranked.index[:max_genes]]
            if ranked_indices:
                return ranked_indices
        if "dispersions_norm" in columns:
            ranked = var["dispersions_norm"].dropna().sort_values(ascending=False)
            ranked_indices = [int(var.index.get_loc(index)) for index in ranked.index[:max_genes]]
            if ranked_indices:
                return ranked_indices
    except Exception:
        pass

    return list(range(min(n_vars, max_genes)))


def _extract_dense_gene_matrix(adata: Any, gene_indices: List[int]) -> Any:
    import numpy as np

    if not gene_indices:
        return np.empty((int(getattr(adata, "n_obs", 0) or 0), 0), dtype=float)

    matrix = adata[:, gene_indices].X
    try:
        from scipy import sparse as sp

        if sp.issparse(matrix):
            matrix = matrix.toarray()
    except Exception:
        pass

    if hasattr(matrix, "A"):
        matrix = matrix.A

    dense_matrix = np.asarray(matrix, dtype=float)
    if dense_matrix.ndim == 1:
        dense_matrix = dense_matrix.reshape(-1, 1)
    return dense_matrix


def _compute_pseudotime_with_positional_cell_ids(fadata: Any, trajectory_name: str) -> Tuple[Any, str]:
    """Compute pseudotime when serialized trajectory cell IDs use 0-based positions."""
    import networkx as nx
    import numpy as np
    import pandas as pd

    try:
        start_milestone = fadata._check_start_milestone(model_name=trajectory_name)
        trajectory_dict = _safe_dict(fadata.get_trajectory_dict(trajectory_name))
        milestone_wrapper = _get_item_attr(trajectory_dict, "milestone_wrapper")
        if milestone_wrapper is None:
            return None, "trajectory has no milestone_wrapper."

        milestone_network_rows = _rows_from_maybe_table(_get_item_attr(milestone_wrapper, "milestone_network", []))
        milestone_percentage_rows = _rows_from_maybe_table(_get_item_attr(milestone_wrapper, "milestone_percentages", []))
        if not milestone_network_rows or not milestone_percentage_rows:
            return None, "trajectory milestone network or milestone percentages are empty."

        milestone_network = pd.DataFrame(milestone_network_rows)
        milestone_percentages = pd.DataFrame(milestone_percentage_rows)
        required_network_cols = {"from", "to", "length"}
        required_percentage_cols = {"cell_id", "milestone_id", "percentage"}
        if not required_network_cols.issubset(milestone_network.columns):
            return None, f"milestone_network is missing columns: {sorted(required_network_cols - set(milestone_network.columns))}."
        if not required_percentage_cols.issubset(milestone_percentages.columns):
            return None, f"milestone_percentages is missing columns: {sorted(required_percentage_cols - set(milestone_percentages.columns))}."

        if "directed" not in milestone_network.columns:
            milestone_network["directed"] = False

        is_directed = milestone_network["directed"].astype(bool).any()
        graph_type = nx.DiGraph if is_directed else nx.Graph
        graph = nx.from_pandas_edgelist(
            milestone_network,
            source="from",
            target="to",
            edge_attr=["length"],
            create_using=graph_type,
        )
        milestone_distances = dict(nx.shortest_path_length(graph, source=start_milestone, weight="length"))
        for node in set(graph.nodes) - set(milestone_distances):
            milestone_distances[node] = np.nan
        distance_df = pd.DataFrame.from_dict(milestone_distances, orient="index", columns=["distance"])

        def calculate_cell_pseudotime(cell_group):
            distances = distance_df.loc[cell_group["milestone_id"], "distance"]
            if distances.isnull().any():
                return np.nan
            percentages = cell_group["percentage"].astype(float).values
            return float((distances.astype(float).values * percentages).sum())

        pseudotime_series = milestone_percentages.groupby("cell_id").apply(calculate_cell_pseudotime)
        obs_index = [str(item) for item in getattr(fadata, "obs", pd.DataFrame()).index]
        pseudotime_index = [str(item) for item in pseudotime_series.index]
        pseudotime_series.index = pseudotime_index

        if set(obs_index).issubset(set(pseudotime_index)):
            ordered = pseudotime_series.loc[obs_index]
        else:
            positional_index = [str(index) for index in range(len(obs_index))]
            if set(positional_index).issubset(set(pseudotime_index)):
                ordered = pseudotime_series.loc[positional_index]
            elif len(pseudotime_series) == len(obs_index):
                ordered = pd.Series(pseudotime_series.to_numpy(), index=obs_index)
            else:
                return None, "trajectory cell IDs do not match obs names or 0-based cell positions."

        ordered = ordered.astype(float)
        nan_mask = ordered.isnull()
        if nan_mask.any():
            ordered.loc[nan_mask] = np.random.default_rng(0).random(int(nan_mask.sum()))

        return ordered.to_numpy(dtype=float), ""
    except Exception as error:
        return None, str(error)


def _compute_selected_pseudotime(fadata: Any, trajectory_history: Dict[str, Any], trajectory_name: str) -> Tuple[Any, str]:
    import numpy as np

    try:
        pseudotime = np.asarray(fadata.get_trajectory_pseudotime(model_name=trajectory_name), dtype=float).reshape(-1)
        return pseudotime, ""
    except Exception as runtime_error:
        positional_pseudotime, positional_error = _compute_pseudotime_with_positional_cell_ids(fadata, trajectory_name)
        if positional_pseudotime is not None:
            return np.asarray(positional_pseudotime, dtype=float).reshape(-1), ""

        payload = _safe_dict(trajectory_history.get(trajectory_name, {}))
        direct_pseudotime = payload.get("pseudotime")
        if direct_pseudotime is None:
            for key, value in payload.items():
                if str(key).startswith("pseudotime_from_"):
                    direct_pseudotime = value
                    break
        if direct_pseudotime is None:
            return None, f"{runtime_error}; positional cell-id fallback failed: {positional_error}"

        try:
            pseudotime = np.asarray(direct_pseudotime, dtype=float).reshape(-1)
            return pseudotime, ""
        except Exception as direct_error:
            return None, f"{runtime_error}; positional cell-id fallback failed: {positional_error}; direct pseudotime parse failed: {direct_error}"


def _compute_selected_driver_genes(trajectory_history: Dict[str, Any], trajectory_name: str) -> Dict[str, Any]:
    import numpy as np

    if not trajectory_name or trajectory_name not in trajectory_history:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "No selected trajectory is available for driver gene calculation.",
        }

    fadata, adata, runtime_error = _build_explorer_fadata(trajectory_history, trajectory_name)
    if fadata is None or adata is None:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": f"Driver gene calculation is unavailable: {runtime_error}",
        }

    pseudotime, pseudotime_error = _compute_selected_pseudotime(fadata, trajectory_history, trajectory_name)
    if pseudotime is None:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": f"Failed to compute trajectory pseudotime for '{trajectory_name}': {pseudotime_error}",
        }

    gene_indices = _select_explorer_gene_indices(adata)
    if not gene_indices:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "No candidate genes are available for driver gene calculation.",
        }

    expression = _extract_dense_gene_matrix(adata, gene_indices)
    if expression.shape[0] != pseudotime.shape[0]:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "Gene expression matrix and pseudotime have incompatible shapes.",
        }

    valid_mask = np.isfinite(pseudotime)
    if expression.size:
        valid_mask &= np.all(np.isfinite(expression), axis=1)
    if valid_mask.sum() < 8:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "Not enough valid cells are available for driver gene calculation.",
        }

    pt = pseudotime[valid_mask]
    expr = expression[valid_mask]
    pt_centered = pt - pt.mean()
    pt_scale = np.sqrt(np.sum(pt_centered**2))
    if pt_scale == 0:
        return {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "Pseudotime is constant, so driver gene correlation cannot be computed.",
        }

    expr_centered = expr - expr.mean(axis=0)
    expr_scale = np.sqrt(np.sum(expr_centered**2, axis=0))
    numerator = np.sum(expr_centered * pt_centered[:, None], axis=0)
    denominator = expr_scale * pt_scale
    with np.errstate(divide="ignore", invalid="ignore"):
        correlation = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0)

    var_names = [str(name) for name in getattr(adata, "var_names", [])]
    items = []
    for local_index, gene_index in enumerate(gene_indices):
        gene_name = var_names[gene_index] if gene_index < len(var_names) else str(gene_index)
        items.append(
            {
                "trajectoryId": trajectory_name,
                "gene": gene_name,
                "rank": 0,
                "score": round(float(abs(correlation[local_index])), 6),
                "signedScore": round(float(correlation[local_index]), 6),
                "sourceKey": "computed:pseudotime_correlation",
            }
        )

    items.sort(key=lambda item: (-item["score"], item["gene"]))
    for index, item in enumerate(items):
        item["rank"] = index + 1

    top_items = items[:20]
    return {
        "available": bool(top_items),
        "items": top_items,
        "sourceKeys": ["computed:pseudotime_correlation"],
        "message": (
            f"Driver genes were computed from expression-pseudotime correlation for '{trajectory_name}'."
            if top_items
            else f"No driver genes were computed for '{trajectory_name}'."
        ),
    }


def _compute_selected_gene_trends(
    trajectory_history: Dict[str, Any],
    trajectory_name: str,
    driver_genes: Dict[str, Any],
    selected_genes: List[str] = None,
) -> Dict[str, Any]:
    import numpy as np

    if not trajectory_name or trajectory_name not in trajectory_history:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "No selected trajectory is available for gene trend calculation.",
        }

    top_genes = [str(gene).strip() for gene in (selected_genes or []) if str(gene).strip()]
    if not top_genes:
        top_genes = [str(item.get("gene", "")) for item in (driver_genes.get("items") or [])[:6] if item.get("gene")]
    if not top_genes:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "No driver genes are available to build gene trend series.",
        }

    fadata, adata, runtime_error = _build_explorer_fadata(trajectory_history, trajectory_name)
    if fadata is None or adata is None:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": f"Gene trend calculation is unavailable: {runtime_error}",
        }

    pseudotime, pseudotime_error = _compute_selected_pseudotime(fadata, trajectory_history, trajectory_name)
    if pseudotime is None:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": f"Failed to compute trajectory pseudotime for '{trajectory_name}': {pseudotime_error}",
        }

    var_names = [str(name) for name in getattr(adata, "var_names", [])]
    var_index = {name: index for index, name in enumerate(var_names)}
    gene_indices = [var_index[gene] for gene in top_genes if gene in var_index]
    if not gene_indices:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "Selected driver genes are not present in AnnData.var_names.",
        }

    expression = _extract_dense_gene_matrix(adata, gene_indices)
    valid_mask = np.isfinite(pseudotime)
    if expression.size:
        valid_mask &= np.all(np.isfinite(expression), axis=1)
    if valid_mask.sum() < 8:
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "Not enough valid cells are available for gene trend calculation.",
        }

    pt = pseudotime[valid_mask]
    expr = expression[valid_mask]
    if pt.min() == pt.max():
        return {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "Pseudotime is constant, so gene trend series cannot be computed.",
        }

    order = np.argsort(pt, kind="stable")
    pt = pt[order]
    expr = expr[order]

    n_bins = min(24, max(8, int(np.sqrt(len(pt)))))
    bin_edges = np.linspace(float(pt.min()), float(pt.max()), n_bins + 1)
    bin_ids = np.digitize(pt, bin_edges[1:-1], right=False)
    series = []

    for gene_position, gene_index in enumerate(gene_indices):
        gene_name = var_names[gene_index] if gene_index < len(var_names) else str(gene_index)
        gene_expr = expr[:, gene_position]
        points = []
        for bin_index in range(n_bins):
            mask = bin_ids == bin_index
            if not np.any(mask):
                continue
            x_value = float(pt[mask].mean())
            y_value = float(gene_expr[mask].mean())
            points.append({"x": round(x_value, 6), "y": round(y_value, 6)})

        if len(points) < 3:
            continue

        series.append(
            {
                "trajectoryId": trajectory_name,
                "gene": gene_name,
                "lineage": "",
                "sourceKey": "computed:pseudotime_bins",
                "points": points,
            }
        )

    return {
        "available": bool(series),
        "series": series,
        "sourceKeys": ["computed:pseudotime_bins"] if series else [],
        "message": (
            f"Gene trends were computed from binned mean expression along pseudotime for '{trajectory_name}'."
            if series
            else f"No gene trend series were computed for '{trajectory_name}'."
        ),
    }


def _search_explorer_gene_names(gene_query: str = "", selected_genes: List[str] = None) -> Dict[str, Any]:
    adata = _get_live_adata()
    var_names = [str(name) for name in getattr(adata, "var_names", [])] if adata is not None else []
    normalized_selected = []
    seen = set()
    for gene in selected_genes or []:
        text = str(gene).strip()
        if text and text not in seen:
            normalized_selected.append(text)
            seen.add(text)

    query = str(gene_query or "").strip()
    matches: List[str] = []
    if query:
        query_lower = query.lower()
        exact = []
        prefix = []
        contains = []
        for gene_name in var_names:
            gene_lower = gene_name.lower()
            if gene_lower == query_lower:
                exact.append(gene_name)
            elif gene_lower.startswith(query_lower):
                prefix.append(gene_name)
            elif query_lower in gene_lower:
                contains.append(gene_name)
            if len(exact) + len(prefix) + len(contains) >= 80:
                continue
        matches = (exact + prefix + contains)[:20]

    return {
        "query": query,
        "selectedGenes": normalized_selected[:6],
        "matches": matches,
        "hasQuery": bool(query),
        "message": (
            f"Found {len(matches)} gene matches for '{query}'."
            if query
            else "Search genes to plot trends for specific markers."
        ),
    }


def _build_explorer_summary(
    requested_trajectory: str = "",
    requested_layout: str = "",
    selected_genes: List[str] = None,
    gene_query: str = "",
) -> Dict[str, Any]:
    _, trajectory_history = _load_effective_trajectory_history()
    trajectory_name, layout_name, entry, trajectory_names, layout_names = _resolve_selection(
        trajectory_history,
        requested_trajectory,
        requested_layout,
    )
    metric_status = _ensure_explorer_benchmark_metrics(trajectory_history)
    if metric_status.get("calculated"):
        _, trajectory_history = _load_effective_trajectory_history()
        trajectory_name, layout_name, entry, trajectory_names, layout_names = _resolve_selection(
            trajectory_history,
            requested_trajectory,
            requested_layout,
        )
    benchmark_rows, metric_keys = _build_benchmark_rows(trajectory_history)
    gene_selection = _search_explorer_gene_names(gene_query, selected_genes)
    driver_genes = _compute_selected_driver_genes(trajectory_history, trajectory_name)
    if not driver_genes.get("available"):
        computed_driver_genes = driver_genes
        driver_genes = _extract_driver_genes(trajectory_history)
        if not driver_genes.get("available") and computed_driver_genes.get("message"):
            driver_genes["message"] = (
                f"{driver_genes['message']} "
                f"Computed fallback also failed: {computed_driver_genes['message']}"
            )
    gene_trends = _compute_selected_gene_trends(
        trajectory_history,
        trajectory_name,
        driver_genes,
        selected_genes=gene_selection["selectedGenes"],
    )
    if not gene_trends.get("available"):
        computed_gene_trends = gene_trends
        gene_trends = _extract_gene_trends(trajectory_history)
        if not gene_trends.get("available") and computed_gene_trends.get("message"):
            gene_trends["message"] = (
                f"{gene_trends['message']} "
                f"Computed fallback also failed: {computed_gene_trends['message']}"
            )

    return {
        "dataset": _dataset_meta(),
        "selection": {
            "trajectory": trajectory_name,
            "layout": layout_name,
            "availableTrajectories": trajectory_names,
            "availableLayouts": layout_names,
        },
        "currentTrajectory": _trajectory_entry_summary(trajectory_name, entry) if trajectory_name else None,
        "benchmark": {
            "rows": benchmark_rows,
            "metricKeys": metric_keys,
            "trajectoryCount": len(benchmark_rows),
            "metricCount": len(metric_keys),
            "metricStatus": metric_status,
        },
        "metricComparison": _build_metric_comparison(benchmark_rows, metric_keys),
        "driverGenes": driver_genes,
        "geneTrends": gene_trends,
        "geneSelection": gene_selection,
        "integrations": _build_integration_status(trajectory_history, driver_genes),
    }


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


def _get_live_adata() -> Any:
    data_adaptor = current_app.data_adaptor
    return getattr(data_adaptor, "data", None)


def _ensure_headless_matplotlib() -> None:
    os.environ["MPLBACKEND"] = "Agg"
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
    except Exception:
        pass


def _patch_scvelo_sparse_compat() -> None:
    """Patch scvelo's old igraph->csr conversion for newer SciPy versions.

    scvelo 0.3.3 still contains `csr_matrix((weights, zip(*edges)), ...)` in
    `scvelo.tools.paga.get_sparse_from_igraph`, which raises:
    `ValueError: mismatching number of index arrays for shape; got 0, expected 2`
    on newer SciPy. We patch it only in the plugin runtime so cafe core files
    remain untouched.
    """
    try:
        from scipy.sparse import csr_matrix
        import scvelo.tools.paga as paga_module
    except Exception:
        return

    existing = getattr(paga_module, "get_sparse_from_igraph", None)
    if existing is None:
        return
    if getattr(existing, "_cafe_sparse_compat_patch", False):
        return

    def _get_sparse_from_igraph_compat(graph, weight_attr=None):
        edges = graph.get_edgelist()
        if weight_attr is None:
            weights = [1] * len(edges)
        else:
            weights = list(graph.es[weight_attr])

        if not graph.is_directed():
            reverse_edges = [(v, u) for u, v in edges]
            edges = edges + reverse_edges
            weights = weights + weights

        shape = (graph.vcount(), graph.vcount())
        if not edges:
            return csr_matrix(shape)

        rows, cols = zip(*edges)
        return csr_matrix((weights, (rows, cols)), shape=shape)

    _get_sparse_from_igraph_compat._cafe_sparse_compat_patch = True
    paga_module.get_sparse_from_igraph = _get_sparse_from_igraph_compat


def _patch_fate_anndata_velocity_category_compat(FateAnnData: Any) -> None:
    """Ensure velocity wrappers see categorical cluster labels in plugin runtime."""
    if FateAnnData is None:
        return
    existing = getattr(FateAnnData, "add_trajectory_velocity", None)
    if existing is None:
        return
    if getattr(existing, "_cafe_velocity_category_patch", False):
        return

    def _add_trajectory_velocity_compat(self, *args, **kwargs):
        cluster = kwargs.get("cluster")
        if cluster is None:
            try:
                cluster = getattr(self, "prior_information", {}).get("cluster")
            except Exception:
                cluster = None
        try:
            if cluster is not None and cluster in self.obs and not pd.api.types.is_categorical_dtype(self.obs[cluster]):
                self.obs[cluster] = self.obs[cluster].astype("category")
        except Exception:
            pass
        return existing(self, *args, **kwargs)

    _add_trajectory_velocity_compat._cafe_velocity_category_patch = True
    FateAnnData.add_trajectory_velocity = _add_trajectory_velocity_compat


def _patch_plot_trajectory_title_compat() -> None:
    """Fix subplot title reuse in cafe.plot.plot_trajectory without editing cafe core."""
    try:
        import cafe
    except Exception:
        return

    def _patch_namespace(namespace: Any) -> None:
        if namespace is None:
            return
        existing = getattr(namespace, "plot_trajectory", None)
        if existing is None:
            return
        if getattr(existing, "_cafe_plot_title_patch", False):
            return

        def _plot_trajectory_title_compat(fadata, *args, **kwargs):
            result = existing(fadata, *args, **kwargs)
            try:
                model_name = kwargs.get("model_name", args[0] if len(args) > 0 else None)
                color = kwargs.get("color", args[1] if len(args) > 1 else None)
                layout_by_row = kwargs.get("layout_by_row", "color")

                if model_name is None:
                    model_name = getattr(fadata, "model_name", None)
                if color is None:
                    color = getattr(getattr(fadata, "prior_information", {}), "get", lambda *_: None)("cluster")

                model_name_list = [model_name] if isinstance(model_name, str) else list(model_name or [])
                color_list = [color] if isinstance(color, str) else list(color or [])
                if not model_name_list:
                    model_name_list = [getattr(fadata, "model_name", "")]
                if not color_list:
                    color_list = [getattr(getattr(fadata, "prior_information", {}), "get", lambda *_: "")("cluster")]

                if len(model_name_list) == 1:
                    layout_by_row = "model"
                if len(color_list) == 1:
                    layout_by_row = "color"

                axes = np.asarray(result, dtype=object)
                for i, model_name_item in enumerate(model_name_list):
                    for j, color_item in enumerate(color_list):
                        ax = axes[i, j] if layout_by_row == "model" else axes[j, i]
                        parsed_name = model_name_item
                        try:
                            parsed_name = fadata.get_parsed_model_name(model_name_item)
                        except Exception:
                            pass
                        ax.set_title(f"{parsed_name}({color_item})")
            except Exception:
                pass
            return result

        _plot_trajectory_title_compat._cafe_plot_title_patch = True
        setattr(namespace, "plot_trajectory", _plot_trajectory_title_compat)

    _patch_namespace(getattr(cafe, "plot", None))
    _patch_namespace(getattr(cafe, "pl", None))


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "keys"):
        try:
            return dict(value)
        except Exception:
            return {}
    return {}


def _get_cafe_container(uns: Dict[str, Any]) -> Dict[str, Any]:
    cafe_obj = uns.get("cafe")
    if isinstance(cafe_obj, dict):
        return cafe_obj
    cfe_obj = uns.get("cfe")
    if isinstance(cfe_obj, dict):
        return cfe_obj
    return {}


def _get_item_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _sorted_keys(value: Any) -> List[str]:
    if hasattr(value, "keys"):
        try:
            return sorted(str(key) for key in value.keys())
        except Exception:
            return []
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    return []


def _normalize_color(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        rgb = []
        for channel in value[:3]:
            try:
                number = float(channel)
            except (TypeError, ValueError):
                return str(value)
            if number <= 1:
                number *= 255
            rgb.append(max(0, min(255, int(round(number)))))
        return "#{:02x}{:02x}{:02x}".format(*rgb)
    return str(value)


def _restore_serialized_trajectory_wrappers(fadata: Any) -> None:
    try:
        from cafe.data.fate_milestone_wrapper import MilestoneWrapper  # type: ignore
        from cafe.data.fate_waypoint_wrapper import WaypointWrapper  # type: ignore
    except Exception:
        return

    for model_name in getattr(fadata, "get_all_model_name", lambda parse=False: [])(parse=False):
        trajectory_dict = getattr(fadata, "get_trajectory_dict", lambda *_: None)(model_name)
        if not isinstance(trajectory_dict, dict):
            continue
        trajectory_dict = trajectory_dict.copy()

        milestone_wrapper = trajectory_dict.get("milestone_wrapper")
        if isinstance(milestone_wrapper, dict):
            milestone_wrapper_obj = object.__new__(MilestoneWrapper)
            for key, value in milestone_wrapper.items():
                milestone_wrapper_obj[key] = value
            trajectory_dict["milestone_wrapper"] = milestone_wrapper_obj

        waypoint_wrapper = trajectory_dict.get("waypoint_wrapper")
        if isinstance(waypoint_wrapper, dict):
            waypoint_wrapper_obj = object.__new__(WaypointWrapper)
            for key, value in waypoint_wrapper.items():
                waypoint_wrapper_obj[key] = value
            trajectory_dict["waypoint_wrapper"] = waypoint_wrapper_obj

        getattr(fadata, "set_trajectory_dict")(trajectory_dict, model_name)


def _infer_wrapper_type_from_name(name: str) -> str:
    method_name = str(name or "").strip().lower()
    velocity_methods = {
        "scvelo",
        "velovi",
        "veloae",
        "dynamo",
        "pyrovelocity",
        "celldancer",
        "unitvelo",
        "velocity",
        "velovae",
        "latentvelo",
        "deepvelo",
        "deepvelo2",
        "cell2fate",
        "regvelo",
        "phylovelo",
        "phlower",
    }
    if method_name in velocity_methods:
        return "velocity"
    return ""


def _sample_items(items: List[Dict[str, Any]], limit: int = 24) -> List[Dict[str, Any]]:
    return items[:limit]


def _as_sequence(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        try:
            converted = value.tolist()
            if isinstance(converted, list):
                return converted
        except Exception:
            return []
    return []


def _table_length(value: Any) -> int:
    if value is None:
        return 0
    if hasattr(value, "__len__"):
        try:
            return len(value)
        except Exception:
            pass
    rows = _rows_from_maybe_table(value)
    return len(rows)


def _series_labels_for_colors(adata: Any, key: str) -> List[str]:
    obs = getattr(adata, "obs", None)
    if obs is None or not hasattr(obs, "__contains__") or key not in obs:
        return []
    series = obs[key]
    if hasattr(series, "cat"):
        try:
            return [str(item) for item in series.cat.categories.tolist()]
        except Exception:
            pass
    try:
        return [str(item) for item in series.dropna().unique().tolist()]
    except Exception:
        return []


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


def _entry_wrapper_type(name: str, payload: Any) -> Tuple[str, str]:
    stored_wrapper_type = str(_get_item_attr(payload, "wrapper_type", "") or "")
    original_wrapper_type = str(_get_item_attr(payload, "original_wrapper_type", "") or "")
    effective_wrapper_type = original_wrapper_type or _infer_wrapper_type_from_name(name) or stored_wrapper_type
    return stored_wrapper_type, effective_wrapper_type


def _trajectory_entry_summary(name: str, payload: Any) -> Dict[str, Any]:
    trajectory_dict = _safe_dict(payload)
    milestone_wrapper = _get_item_attr(payload, "milestone_wrapper")
    waypoint_wrapper = _get_item_attr(payload, "waypoint_wrapper")
    trajectory_embedding = _safe_dict(_get_item_attr(payload, "trajectory_embedding", {}))
    metric_dict = _safe_dict(_get_item_attr(payload, "metric_dict", {}))
    resource_usage = _safe_dict(_get_item_attr(payload, "resource_usage", {}))
    stored_wrapper_type, effective_wrapper_type = _entry_wrapper_type(name, payload)
    if not stored_wrapper_type and milestone_wrapper is not None:
        stored_wrapper_type = str(_get_item_attr(milestone_wrapper, "wrapper_type", "") or "")
    if not effective_wrapper_type:
        effective_wrapper_type = stored_wrapper_type

    milestone_network = _get_item_attr(milestone_wrapper, "milestone_network", {})
    milestone_ids = _get_item_attr(milestone_wrapper, "id_list", [])
    waypoint_items = _get_item_attr(waypoint_wrapper, "waypoints", None)
    if waypoint_items is None:
        waypoint_items = _get_item_attr(waypoint_wrapper, "waypoint_milestone_percentages", None)

    milestone_ids_list = _as_sequence(milestone_ids)
    milestone_count = len(milestone_ids_list)
    if not milestone_count:
        milestone_rows = _rows_from_maybe_table(milestone_network)
        milestone_names = set()
        for row in milestone_rows:
            milestone_names.add(str(row.get("from", "")))
            milestone_names.add(str(row.get("to", "")))
        milestone_names.discard("")
        milestone_count = len(milestone_names)

    return {
        "id": name,
        "displayName": name,
        "wrapperType": str(stored_wrapper_type or ""),
        "effectiveWrapperType": str(effective_wrapper_type or ""),
        "originalWrapperType": str(_get_item_attr(payload, "original_wrapper_type", "") or _infer_wrapper_type_from_name(name) or ""),
        "hasMilestoneWrapper": bool(milestone_wrapper or trajectory_dict.get("milestone_wrapper")),
        "hasWaypointWrapper": bool(waypoint_wrapper or trajectory_dict.get("waypoint_wrapper")),
        "layoutNames": sorted(str(key) for key in trajectory_embedding.keys()),
        "metricKeys": sorted(str(key) for key in metric_dict.keys()),
        "resourceUsage": _to_json_value(resource_usage),
        "milestoneCount": milestone_count,
        "edgeCount": _table_length(milestone_network),
        "waypointCount": _table_length(waypoint_items),
    }


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


def _runtime_display_name(runtime_key: str) -> str:
    display_names = {
        "python_function": "Local Python",
        "conda": "Conda",
        "cafe_docker": "Cafe Docker",
        "dynverse_docker": "Dynverse Docker",
    }
    return display_names.get(runtime_key, runtime_key)


def _find_cafe_method_root() -> str:
    spec = importlib_util.find_spec("cafe.method")
    if spec is None or spec.origin is None:
        raise RuntimeError("Unable to locate installed cafe.method package.")
    return os.path.dirname(spec.origin)


def _safe_literal_eval(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        try:
            return ast.unparse(node)
        except Exception:
            return None


def _annotation_text(node: Any) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _infer_schema_input_kind(default_value: Any, annotation_text: str) -> str:
    annotation_lower = str(annotation_text or "").lower()
    if isinstance(default_value, bool) or annotation_lower in {"bool", "optional[bool]"}:
        return "boolean"
    if isinstance(default_value, (int, float)) and not isinstance(default_value, bool):
        return "number"
    if annotation_lower in {"int", "float", "optional[int]", "optional[float]"}:
        return "number"
    if isinstance(default_value, (dict, list, tuple)):
        return "json"
    if "dict" in annotation_lower or "list" in annotation_lower or "tuple" in annotation_lower:
        return "json"
    return "text"


def _parse_function_schema(function_dir: str, function_name: str) -> Tuple[List[Dict[str, Any]], str]:
    function_path = os.path.join(function_dir, f"cf_{function_name}.py")
    if not os.path.exists(function_path):
        return [], ""

    with open(function_path, "r", encoding="utf-8") as handle:
        source = handle.read()

    module = ast.parse(source, filename=function_path)
    function_node = None
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            function_node = node
            break

    if function_node is None:
        return [], ""

    docstring = ast.get_docstring(function_node) or ""
    schema: List[Dict[str, Any]] = []

    positional_args = list(function_node.args.args)
    positional_defaults = [None] * (len(positional_args) - len(function_node.args.defaults)) + list(function_node.args.defaults)
    for argument, default_node in zip(positional_args, positional_defaults):
        if argument.arg in {"adata", "self"}:
            continue
        default_value = _safe_literal_eval(default_node) if default_node is not None else None
        annotation_text = _annotation_text(argument.annotation)
        schema.append(
            {
                "name": argument.arg,
                "required": default_node is None,
                "default": _to_json_value(default_value),
                "defaultText": "" if default_node is None else str(_to_json_value(default_value)),
                "annotation": annotation_text,
                "kind": "POSITIONAL_OR_KEYWORD",
                "inputKind": _infer_schema_input_kind(default_value, annotation_text),
            }
        )

    kw_defaults = list(function_node.args.kw_defaults)
    for argument, default_node in zip(function_node.args.kwonlyargs, kw_defaults):
        if argument.arg in {"adata", "self"}:
            continue
        default_value = _safe_literal_eval(default_node) if default_node is not None else None
        annotation_text = _annotation_text(argument.annotation)
        schema.append(
            {
                "name": argument.arg,
                "required": default_node is None,
                "default": _to_json_value(default_value),
                "defaultText": "" if default_node is None else str(_to_json_value(default_value)),
                "annotation": annotation_text,
                "kind": "KEYWORD_ONLY",
                "inputKind": _infer_schema_input_kind(default_value, annotation_text),
            }
        )

    return schema, docstring


def _method_catalog() -> Dict[str, Any]:
    method_root = _find_cafe_method_root()
    backend_csv_path = os.path.join(method_root, "method_backend.csv")
    function_dir = os.path.join(method_root, "function")
    if not os.path.exists(backend_csv_path):
        raise RuntimeError("CAFE method backend metadata is unavailable.")

    methods = []
    with open(backend_csv_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            method_name = row.get("") or row.get(reader.fieldnames[0] if reader.fieldnames else "") or ""
            method_name = str(method_name).strip()
            if not method_name:
                continue

            backend_targets = {}
            available_runtimes = []
            for runtime_key in ("python_function", "conda", "cafe_docker", "dynverse_docker"):
                runtime_value = str(row.get(runtime_key, "") or "").strip()
                if runtime_value:
                    backend_targets[runtime_key] = runtime_value
                    available_runtimes.append(
                        {
                            "key": runtime_key,
                            "label": _runtime_display_name(runtime_key),
                            "target": runtime_value,
                        }
                    )

            default_runtime = available_runtimes[0]["key"] if available_runtimes else ""
            schema, docstring = _parse_function_schema(function_dir, backend_targets.get("python_function", ""))
            methods.append(
                {
                    "key": method_name,
                    "label": method_name,
                    "description": docstring.splitlines()[0] if docstring else "",
                    "docstring": docstring,
                    "schema": schema,
                    "availableRuntimes": available_runtimes,
                    "defaultRuntime": default_runtime,
                    "backendTargets": backend_targets,
                }
            )

    runtime_options = [
        {"key": runtime_key, "label": _runtime_display_name(runtime_key)}
        for runtime_key in ("python_function", "conda", "cafe_docker", "dynverse_docker")
    ]
    return {
        "dataset": _dataset_meta(),
        "runtimeOptions": runtime_options,
        "methods": methods,
    }


def _trajectory_options(trajectory_history: Dict[str, Any]) -> List[Dict[str, Any]]:
    loaded_names = {str(key) for key in trajectory_history.keys()}
    options: List[Dict[str, Any]] = []

    for trajectory_name in sorted(loaded_names):
        options.append(
            {
                "id": trajectory_name,
                "label": trajectory_name,
                "loaded": True,
                "kind": "trajectory",
                "defaultRuntime": "",
                "availableRuntimes": [],
            }
        )

    try:
        catalog = _method_catalog()
    except Exception:
        return options

    for method in catalog.get("methods", []):
        method_key = str(method.get("key", "")).strip()
        if not method_key or method_key in loaded_names:
            continue
        options.append(
            {
                "id": method_key,
                "label": str(method.get("label", method_key)),
                "loaded": False,
                "kind": "method",
                "defaultRuntime": str(method.get("defaultRuntime", "")),
                "availableRuntimes": [
                    {
                        "key": str(runtime.get("key", "")),
                        "label": str(runtime.get("label", "")),
                    }
                    for runtime in method.get("availableRuntimes", [])
                    if runtime.get("key")
                ],
            }
        )

    return options


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
        from cafe.data import (
            FateAnnData,  # type: ignore
            read_bonemarrow,  # type: ignore
            read_erythroid_lineage,  # type: ignore
            read_gastrulation,  # type: ignore
            read_gastrulation_5000,  # type: ignore
            read_pancreas,  # type: ignore
        )

        return {
            "FateAnnData": FateAnnData,
            "read_pancreas": read_pancreas,
            "read_bonemarrow": read_bonemarrow,
            "read_erythroid_lineage": read_erythroid_lineage,
            "read_gastrulation": read_gastrulation,
            "read_gastrulation_5000": read_gastrulation_5000,
        }, ""
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


def _job_snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jobId": job["jobId"],
        "trajectoryId": job.get("trajectoryId", job["jobId"]),
        "methodName": job["methodName"],
        "backendName": job["backendName"],
        "status": job["status"],
        "stage": job.get("stage", ""),
        "progress": int(job.get("progress", 0)),
        "createdAt": job["createdAt"],
        "updatedAt": job["updatedAt"],
        "cancelRequested": job.get("cancelRequested", False),
        "result": job.get("result"),
        "error": job.get("error", ""),
    }


def _append_method_job_log(job_id: str, message: str) -> None:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            return
        job.setdefault("logs", [])
        job["logs"].append(f"[{datetime.utcnow().isoformat()}Z] {message}")
        job["updatedAt"] = datetime.utcnow().isoformat() + "Z"


def _set_method_job_state(job_id: str, **updates: Any) -> None:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            return
        job.update(updates)
        job["updatedAt"] = datetime.utcnow().isoformat() + "Z"


def _set_method_job_progress(job_id: str, progress: int, stage: str) -> None:
    _set_method_job_state(job_id, progress=max(0, min(int(progress), 100)), stage=str(stage or ""))


def _merge_method_trajectory_into_live_adata(trajectory_id: str, fadata: Any) -> None:
    adata = _get_live_adata()
    if adata is None:
        raise RuntimeError("Current Cellxgene dataset is unavailable.")

    trajectory_dict = fadata.get_trajectory_dict(trajectory_id) or {}
    serialized_trajectory = _serialize_trajectory_dict_for_uns(trajectory_dict)

    if not hasattr(adata, "uns") or adata.uns is None:
        raise RuntimeError("Live AnnData.uns is unavailable.")

    if "cafe" not in adata.uns or not isinstance(adata.uns.get("cafe"), dict):
        adata.uns["cafe"] = {}

    cafe_container = adata.uns["cafe"]
    trajectory_history = cafe_container.get("trajectory_history_dict")
    if not isinstance(trajectory_history, dict):
        trajectory_history = {}
        cafe_container["trajectory_history_dict"] = trajectory_history

    trajectory_history[str(trajectory_id)] = serialized_trajectory
    cafe_container["model_name"] = str(trajectory_id)

    prior_information = getattr(fadata, "prior_information", None)
    if isinstance(prior_information, dict):
        cafe_container["prior_information"] = dict(prior_information)


def _current_process_memory_kb() -> float:
    try:
        import resource

        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return 0.0


def _fallback_resource_usage(start_time: float, start_memory_kb: float) -> Dict[str, Any]:
    elapsed = max(0.0, time.perf_counter() - start_time)
    current_memory_kb = _current_process_memory_kb()
    memory_kb = current_memory_kb
    if current_memory_kb > start_memory_kb:
        memory_kb = current_memory_kb - start_memory_kb
    return {
        "time": elapsed,
        "memory": max(0.0, memory_kb),
    }


def _ensure_trajectory_resource_usage(fadata: Any, trajectory_id: str, resource_usage: Dict[str, Any]) -> None:
    if not resource_usage:
        return
    trajectory_dict = getattr(fadata, "get_trajectory_dict", lambda *_: None)(trajectory_id) or {}
    if not isinstance(trajectory_dict, dict):
        return
    existing = _safe_dict(trajectory_dict.get("resource_usage", {}))
    has_time, _ = _try_numeric(existing.get("time"))
    has_memory, _ = _try_numeric(existing.get("memory"))
    if has_time and has_memory:
        return

    merged = dict(existing)
    for key in ("time", "memory"):
        ok, number = _try_numeric(merged.get(key))
        if not ok:
            fallback_ok, fallback_number = _try_numeric(resource_usage.get(key))
            if fallback_ok:
                merged[key] = fallback_number
    trajectory_dict["resource_usage"] = merged
    try:
        getattr(fadata, "set_trajectory_dict")(trajectory_dict, trajectory_id)
    except Exception:
        pass


def _run_method_job(job_id: str, flask_app: Any) -> None:
    with flask_app.app_context():
        with _METHOD_JOB_LOCK:
            job = _METHOD_JOBS.get(job_id)
            if job is None:
                return
            if job.get("cancelRequested"):
                job["status"] = "cancelled"
                job["updatedAt"] = datetime.utcnow().isoformat() + "Z"
                return
            method_name = job["methodName"]
            trajectory_id = str(job.get("trajectoryId") or job_id)
            backend_name = job["backendName"]
            parameters = dict(job.get("parameters", {}))

        _set_method_job_state(job_id, status="running")
        _set_method_job_progress(job_id, 5, "queued")
        _append_method_job_log(
            job_id,
            f"Starting job for method='{method_name}' runtime='{backend_name}' trajectory='{trajectory_id}'.",
        )

        try:
            _set_method_job_progress(job_id, 10, "loading_runtime")
            FateAnnData, FateMethod, import_error = _load_method_execution_runtime()
            if FateAnnData is None or FateMethod is None:
                raise RuntimeError(f"CAFE method runtime is unavailable: {import_error}")

            _set_method_job_progress(job_id, 20, "preparing_dataset")
            fadata, fadata_error = _load_effective_fadata()
            if fadata is None:
                raise RuntimeError(fadata_error or "Current Cellxgene dataset is unavailable.")

            if hasattr(fadata, "copy"):
                fadata = fadata.copy()
            fadata.id = job_id
            fadata.check_result_dir(os.path.join(tempfile.gettempdir(), ".cafe", job_id))

            _set_method_job_progress(job_id, 35, "preparing_method")
            method = FateMethod(method_name=method_name, backend_name=backend_name)
            if method_name == "scvelo":
                _patch_scvelo_sparse_compat()
            _set_method_job_progress(job_id, 55, "running_inference")
            if backend_name != "python_function":
                parameters.setdefault("benchmark_resource", True)
            resource_start_time = time.perf_counter()
            resource_start_memory_kb = _current_process_memory_kb()
            method.infer_trajectory(
                fadata,
                parameters=parameters,
                id=trajectory_id,
                rewrite=True,
                backend_name=backend_name,
            )
            _ensure_trajectory_resource_usage(
                fadata,
                trajectory_id,
                _fallback_resource_usage(resource_start_time, resource_start_memory_kb),
            )

            _set_method_job_progress(job_id, 85, "merging_results")
            _merge_method_trajectory_into_live_adata(trajectory_id, fadata)

            trajectory_dict = fadata.get_trajectory_dict(trajectory_id) or {}
            result = {
                "trajectoryId": trajectory_id,
                "trajectorySummary": _trajectory_entry_summary(trajectory_id, trajectory_dict),
                "resultDir": getattr(fadata, "result_dir", ""),
                "logFile": os.path.join(getattr(fadata, "log_dir", ""), f"{job_id}.log"),
            }
            _set_method_job_progress(job_id, 100, "completed")
            _append_method_job_log(job_id, "Method job completed successfully.")
            _set_method_job_state(job_id, status="succeeded", result=result)
        except Exception as error:
            _set_method_job_progress(job_id, 100, "failed")
            _append_method_job_log(job_id, f"Method job failed: {error}")
            _append_method_job_log(job_id, traceback.format_exc())
            _set_method_job_state(job_id, status="failed", error=str(error))


def _submit_method_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    method_name = str(payload.get("methodName", "")).strip()
    backend_name = str(payload.get("backendName", "")).strip()
    trajectory_id = str(payload.get("trajectoryId", "") or "").strip()
    parameters = payload.get("parameters", {})
    if not method_name:
        raise ValueError("methodName is required.")
    if not backend_name:
        raise ValueError("backendName is required.")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object.")

    catalog = _method_catalog()
    method_map = {item["key"]: item for item in catalog["methods"]}
    method_item = method_map.get(method_name)
    if method_item is None:
        raise ValueError(f"Unknown method: {method_name}")

    available_runtime_keys = {item["key"] for item in method_item.get("availableRuntimes", [])}
    if backend_name not in available_runtime_keys:
        raise ValueError(f"Runtime '{backend_name}' is not available for method '{method_name}'.")

    job_id = str(uuid.uuid4())
    if not trajectory_id:
        trajectory_id = job_id
    now = datetime.utcnow().isoformat() + "Z"
    job = {
        "jobId": job_id,
        "trajectoryId": trajectory_id,
        "methodName": method_name,
        "backendName": backend_name,
        "parameters": parameters,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "createdAt": now,
        "updatedAt": now,
        "logs": [],
        "cancelRequested": False,
        "result": None,
        "error": "",
    }

    with _METHOD_JOB_LOCK:
        _METHOD_JOBS[job_id] = job

    flask_app = current_app._get_current_object()
    thread = threading.Thread(target=_run_method_job, args=(job_id, flask_app), daemon=True)
    thread.start()
    _append_method_job_log(job_id, "Job queued.")
    return _job_snapshot(job)


def _query_method_job(job_id: str) -> Dict[str, Any]:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return _job_snapshot(job)


def _cancel_method_job(job_id: str) -> Dict[str, Any]:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job["status"] == "queued":
            job["status"] = "cancelled"
            job["stage"] = "cancelled"
            job["progress"] = 100
        elif job["status"] == "running":
            job["status"] = "cancel_requested"
            job["stage"] = "cancel_requested"
        job["cancelRequested"] = True
        job["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    _append_method_job_log(job_id, "Cancellation requested. Running jobs are best-effort only.")
    return _query_method_job(job_id)


def _method_job_logs(job_id: str) -> Dict[str, Any]:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        logs = list(job.get("logs", []))
        result = job.get("result") or {}

    log_file = str(result.get("logFile", ""))
    if log_file and os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as handle:
                file_text = handle.read()
            if file_text.strip():
                logs.append("--- backend log file ---")
                logs.extend(file_text.splitlines()[-200:])
        except Exception:
            pass

    return {"jobId": job_id, "logs": "\n".join(logs)}


def _method_job_result(job_id: str) -> Dict[str, Any]:
    with _METHOD_JOB_LOCK:
        job = _METHOD_JOBS.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return {
            "jobId": job_id,
            "status": job["status"],
            "result": job.get("result"),
            "error": job.get("error", ""),
        }


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


def _dataset_shape(adata: Any) -> Dict[str, int]:
    shape = getattr(adata, "shape", None)
    if not shape or len(shape) < 2:
        return {"nObs": 0, "nVars": 0}
    return {"nObs": int(shape[0]), "nVars": int(shape[1])}


def _matrix_meta(adata: Any) -> Dict[str, Any]:
    matrix = getattr(adata, "X", None)
    sparse = False
    dtype = ""
    if matrix is not None:
        try:
            from scipy import sparse as sp

            sparse = bool(sp.issparse(matrix))
        except Exception:
            sparse = False
        dtype = str(getattr(matrix, "dtype", ""))
    return {"dtype": dtype, "sparse": sparse}


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


def _figure_to_png_bytes(fig: Any, transparent: bool = False, tight: bool = True) -> bytes:
    _ensure_headless_matplotlib()
    import matplotlib.pyplot as plt

    buffer = BytesIO()
    save_kwargs = {"format": "png", "dpi": 140, "transparent": transparent}
    if tight:
        save_kwargs["bbox_inches"] = "tight"
    else:
        save_kwargs["bbox_inches"] = None
        save_kwargs["pad_inches"] = 0
    fig.savefig(buffer, **save_kwargs)
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _layout_bounds(layout_name: str) -> Tuple[float, float, float, float] | None:
    adata = _get_live_adata()
    obsm = getattr(adata, "obsm", None)
    if adata is None or obsm is None:
        return None

    layout_key = ""
    for candidate in (layout_name, f"X_{layout_name}" if layout_name and not str(layout_name).startswith("X_") else ""):
        text = str(candidate or "").strip()
        if text and text in obsm:
            layout_key = text
            break

    if not layout_key:
        return None

    try:
        import numpy as np

        coords = np.asarray(obsm[layout_key])
        if coords.ndim != 2 or coords.shape[1] < 2 or coords.shape[0] == 0:
            return None

        finite_mask = np.isfinite(coords[:, 0]) & np.isfinite(coords[:, 1])
        if not np.any(finite_mask):
            return None

        finite_coords = coords[finite_mask]
        min_x = float(np.min(finite_coords[:, 0]))
        max_x = float(np.max(finite_coords[:, 0]))
        min_y = float(np.min(finite_coords[:, 1]))
        max_y = float(np.max(finite_coords[:, 1]))
        if max_x <= min_x or max_y <= min_y:
            return None
        return min_x, max_x, min_y, max_y
    except Exception:
        return None


def _extract_first_figure(render_result: Any) -> Any:
    _ensure_headless_matplotlib()
    import matplotlib.pyplot as plt

    if render_result is None:
        return plt.gcf()

    if hasattr(render_result, "savefig"):
        return render_result

    if hasattr(render_result, "figure"):
        return render_result.figure

    if isinstance(render_result, list) and render_result:
        first = render_result[0]
        if hasattr(first, "savefig"):
            return first
        if hasattr(first, "figure"):
            return first.figure

    return plt.gcf()


def _apply_static_plot_title(fig: Any, fadata: Any, trajectory_name: str, view: str) -> Any:
    if fig is None:
        return fig
    axes = list(getattr(fig, "axes", []) or [])
    if not axes:
        return fig

    parsed_name = str(trajectory_name or "")
    if hasattr(fadata, "get_parsed_model_name") and trajectory_name:
        try:
            parsed_name = str(fadata.get_parsed_model_name(trajectory_name))
        except Exception:
            parsed_name = str(trajectory_name)

    if view == "trajectory":
        title_text = f"{parsed_name}(clusters)"
    elif view == "graph":
        title_text = f"{parsed_name}(graph)"
    elif view == "stream":
        title_text = f"{parsed_name}(stream)"
    else:
        title_text = parsed_name

    axes[0].set_title(title_text)
    return fig


def _prepare_overlay_figure(fig: Any, layout_name: str = "") -> Any:
    if fig is None:
        return fig

    axes = list(getattr(fig, "axes", []) or [])
    bounds = _layout_bounds(layout_name)
    fig.patch.set_alpha(0)
    if bounds is not None:
        min_x, max_x, min_y, max_y = bounds
        span_x = max_x - min_x
        span_y = max_y - min_y
        ratio = span_x / span_y if span_y > 0 else 1.4
        width = 9.8
        height = max(3.2, min(8.5, width / max(ratio, 0.2)))
        try:
            fig.set_size_inches(width, height, forward=True)
        except Exception:
            pass
    for ax in axes:
        try:
            ax.set_title("")
            ax.set_facecolor((1, 1, 1, 0))
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_frame_on(False)
            legend = ax.get_legend()
            if legend is not None:
                legend.remove()
            ax.set_position([0, 0, 1, 1])
            if bounds is not None:
                ax.set_xlim(bounds[0], bounds[1])
                ax.set_ylim(bounds[2], bounds[3])
                ax.margins(0)
                ax.set_aspect("equal", adjustable="box")
        except Exception:
            continue
    return fig


def _draw_preview_fallback(preview: Dict[str, Any], title: str, message: str = "") -> bytes:
    _ensure_headless_matplotlib()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_title(title)
    ax.set_facecolor("#ffffff")
    ax.grid(False)

    nodes = preview.get("nodes", []) if isinstance(preview, dict) else []
    edges = preview.get("edges", []) if isinstance(preview, dict) else []
    waypoint_segments = preview.get("waypointSegments", {}) if isinstance(preview, dict) else {}

    node_by_id = {str(node.get("id", "")): node for node in nodes if isinstance(node, dict)}

    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        source_node = node_by_id.get(source)
        target_node = node_by_id.get(target)
        if not source_node or not target_node:
            continue
        ax.plot(
            [_as_float(source_node.get("x")), _as_float(target_node.get("x"))],
            [_as_float(source_node.get("y")), _as_float(target_node.get("y"))],
            color="#1f2937",
            linewidth=1.5,
            zorder=1,
        )

    for group_points in waypoint_segments.values():
        if not isinstance(group_points, list) or len(group_points) < 2:
            continue
        sorted_points = sorted(group_points, key=lambda p: _as_float(p.get("percentage"), 0.0), reverse=True)
        ax.plot(
            [_as_float(point.get("x")) for point in sorted_points],
            [_as_float(point.get("y")) for point in sorted_points],
            color="#94a3b8",
            linewidth=1.0,
            linestyle="--",
            zorder=0,
        )

    for node in nodes:
        node_id = str(node.get("id", ""))
        x = _as_float(node.get("x"))
        y = _as_float(node.get("y"))
        color = str(node.get("color", "#9aa7b0"))
        ax.scatter([x], [y], s=42, c=[color], edgecolors="#111827", linewidths=0.8, zorder=2)
        if node_id:
            ax.text(x, y, f" {node_id}", fontsize=9, color="#334155", va="bottom")

    if message:
        ax.text(
            0.01,
            0.01,
            message,
            transform=ax.transAxes,
            fontsize=9,
            color="#64748b",
            va="bottom",
        )

    ax.set_xticks([])
    ax.set_yticks([])
    return _figure_to_png_bytes(fig)


def _draw_text_fallback(title: str, message: str) -> bytes:
    _ensure_headless_matplotlib()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.set_title(title)
    ax.axis("off")
    ax.text(0.02, 0.92, message, transform=ax.transAxes, va="top", ha="left", fontsize=10, color="#334155", wrap=True)
    return _figure_to_png_bytes(fig)


def _render_static_with_cafe(view: str, trajectory_name: str, layout_name: str, overlay: bool = False) -> bytes:
    # Enforce non-interactive backend for Flask server rendering.
    _ensure_headless_matplotlib()
    import cafe

    plot_ns = getattr(cafe, "plot", None)
    alt_plot_ns = getattr(cafe, "pl", None)

    fadata, fadata_error = _load_effective_fadata()
    if fadata is None:
        raise RuntimeError(fadata_error or "Effective FateAnnData is unavailable")

    effective_uns, effective_history = _load_effective_trajectory_history()
    effective_cafe = _get_cafe_container(effective_uns)
    if not trajectory_name:
        trajectory_name = _best_default(sorted(str(key) for key in effective_history.keys()), ["ref"])
    entry = _safe_dict(effective_history.get(trajectory_name, {}))
    _, effective_wrapper_type = _entry_wrapper_type(trajectory_name, entry)
    if trajectory_name:
        fadata.model_name = trajectory_name
    if not layout_name:
        layout_name = str(effective_cafe.get("prior_information", {}).get("basis", "")) or str(getattr(fadata, "prior_information", {}).get("basis", ""))

    basis_candidates: List[Any] = [None]
    if layout_name:
        basis_candidates = [layout_name]
        if not str(layout_name).startswith("X_"):
            basis_candidates.append(f"X_{layout_name}")

    if view == "graph":
        if str(effective_wrapper_type).lower() == "velocity":
            plot_graph_func = getattr(plot_ns, "plot_graph", None) or getattr(alt_plot_ns, "plot_graph", None)
            plot_trajectory_func = getattr(plot_ns, "plot_trajectory", None) or getattr(alt_plot_ns, "plot_trajectory", None)
            if plot_graph_func is None and plot_trajectory_func is None:
                raise AttributeError("Neither cafe.plot_graph nor cafe.plot_trajectory is available")

            last_error = None
            result = None
            if plot_graph_func is not None:
                graph_kwargs_candidates = [
                    {"model_name": trajectory_name or None, "color": "clusters"},
                    {"model_name": trajectory_name or None},
                    {"color": "clusters"},
                    {},
                ]
                for kwargs in graph_kwargs_candidates:
                    try:
                        result = plot_graph_func(fadata, **kwargs)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error
            if result is None and plot_trajectory_func is not None:
                graph_fallback_kwargs_candidates = []
                for basis in basis_candidates:
                    graph_fallback_kwargs_candidates.extend(
                        [
                            {
                                "model_name": trajectory_name or None,
                                "basis": basis,
                                "color": "clusters",
                                "curve": False,
                                "show_milestone_labels": True,
                            },
                            {
                                "model_name": trajectory_name or None,
                                "basis": basis,
                                "curve": False,
                                "show_milestone_labels": True,
                            },
                        ]
                    )
                graph_fallback_kwargs_candidates.extend(
                    [
                        {
                            "model_name": trajectory_name or None,
                            "color": "clusters",
                            "curve": False,
                            "show_milestone_labels": True,
                        },
                        {"model_name": trajectory_name or None, "curve": False, "show_milestone_labels": True},
                    ]
                )
                for kwargs in graph_fallback_kwargs_candidates:
                    try:
                        result = plot_trajectory_func(fadata, **kwargs)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error
            if last_error is not None and result is None:
                raise last_error
            fig = _extract_first_figure(result)
            fig = _prepare_overlay_figure(fig, layout_name) if overlay else _apply_static_plot_title(fig, fadata, trajectory_name, view)
            return _figure_to_png_bytes(fig, transparent=overlay, tight=not overlay)

        plot_graph_func = None
        if plot_ns is not None and hasattr(plot_ns, "plot_graph"):
            plot_graph_func = plot_ns.plot_graph
        elif alt_plot_ns is not None and hasattr(alt_plot_ns, "plot_graph"):
            plot_graph_func = alt_plot_ns.plot_graph
        if plot_graph_func is None:
            raise AttributeError("cafe.plot_graph is unavailable")

        last_error = None
        result = None
        graph_kwargs_candidates = [
            {"model_name": trajectory_name or None, "color": "clusters"},
            {"model_name": trajectory_name or None},
            {"color": "clusters"},
            {},
        ]
        for kwargs in graph_kwargs_candidates:
            try:
                result = plot_graph_func(fadata, **kwargs)
                last_error = None
                break
            except Exception as error:
                last_error = error
        if last_error is not None:
            raise last_error
    elif view == "trajectory":
        if str(effective_wrapper_type).lower() == "velocity":
            plot_trajectory_func = getattr(plot_ns, "plot_trajectory", None) or getattr(alt_plot_ns, "plot_trajectory", None)
            plot_velocity_func = getattr(plot_ns, "plot_velocity", None) or getattr(alt_plot_ns, "plot_velocity", None)
            if plot_trajectory_func is None and plot_velocity_func is None:
                raise AttributeError("Neither cafe.plot_trajectory nor cafe.plot_velocity is available")

            last_error = None
            result = None
            trajectory_kwargs_candidates = []
            for basis in basis_candidates:
                trajectory_kwargs_candidates.extend(
                    [
                        {
                            "model_name": trajectory_name or None,
                            "basis": basis,
                            "color": "clusters",
                            "show_milestone_labels": False,
                        },
                        {
                            "model_name": trajectory_name or None,
                            "basis": basis,
                            "show_milestone_labels": False,
                        },
                    ]
                )
            trajectory_kwargs_candidates.extend(
                [
                    {"model_name": trajectory_name or None, "color": "clusters"},
                    {"model_name": trajectory_name or None},
                ]
            )

            if plot_trajectory_func is not None:
                for kwargs in trajectory_kwargs_candidates:
                    try:
                        effective_kwargs = dict(kwargs)
                        if overlay:
                            effective_kwargs["color"] = "clusters"
                            effective_kwargs["show_milestone_labels"] = False
                            effective_kwargs.update({"frameon": False, "size": 0, "alpha": 0, "title": ""})
                        result = plot_trajectory_func(fadata, **effective_kwargs)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error

            if result is None and plot_velocity_func is not None:
                velocity_kwargs_candidates = []
                for basis in basis_candidates:
                    velocity_kwargs_candidates.extend(
                        [
                            {"model_name": trajectory_name or None, "basis": basis, "mode": "embedding"},
                            {"basis": basis, "mode": "embedding"},
                        ]
                    )
                velocity_kwargs_candidates.extend(
                    [
                        {"model_name": trajectory_name or None, "mode": "embedding"},
                        {"mode": "embedding"},
                    ]
                )
                for kwargs in velocity_kwargs_candidates:
                    try:
                        result = plot_velocity_func(fadata, **kwargs)
                        last_error = None
                        break
                    except Exception as error:
                        last_error = error
            if last_error is not None:
                raise last_error
            fig = _extract_first_figure(result)
            fig = _prepare_overlay_figure(fig, layout_name) if overlay else _apply_static_plot_title(fig, fadata, trajectory_name, view)
            return _figure_to_png_bytes(fig, transparent=overlay, tight=not overlay)

        plot_trajectory_func = None
        if plot_ns is not None and hasattr(plot_ns, "plot_trajectory"):
            plot_trajectory_func = plot_ns.plot_trajectory
        elif alt_plot_ns is not None and hasattr(alt_plot_ns, "plot_trajectory"):
            plot_trajectory_func = alt_plot_ns.plot_trajectory
        if plot_trajectory_func is None:
            raise AttributeError("cafe.plot_trajectory is unavailable")

        last_error = None
        result = None
        trajectory_kwargs_candidates = []
        for basis in basis_candidates:
            trajectory_kwargs_candidates.extend(
                [
                    {
                        "model_name": trajectory_name or None,
                        "basis": basis,
                        "color": "clusters",
                        "show_milestone_labels": False,
                    },
                    {
                        "model_name": trajectory_name or None,
                        "basis": basis,
                        "show_milestone_labels": False,
                    },
                    {
                        "basis": basis,
                        "color": "clusters",
                        "show_milestone_labels": False,
                    },
                    {
                        "basis": basis,
                        "show_milestone_labels": False,
                    },
                ]
            )
        trajectory_kwargs_candidates.extend(
            [
                {"model_name": trajectory_name or None, "color": "clusters"},
                {"model_name": trajectory_name or None},
                {"color": "clusters"},
                {},
            ]
        )
        for kwargs in trajectory_kwargs_candidates:
            try:
                effective_kwargs = dict(kwargs)
                if overlay:
                    effective_kwargs["color"] = "clusters"
                    effective_kwargs["show_milestone_labels"] = False
                    effective_kwargs.update({"frameon": False, "size": 0, "alpha": 0, "title": ""})
                result = plot_trajectory_func(fadata, **effective_kwargs)
                last_error = None
                break
            except Exception as error:
                last_error = error
        if last_error is not None:
            raise last_error
    elif view == "stream":
        if str(effective_wrapper_type).lower() == "velocity":
            plot_velocity_func = getattr(plot_ns, "plot_velocity", None) or getattr(alt_plot_ns, "plot_velocity", None)
            if plot_velocity_func is None:
                raise AttributeError("cafe.plot_velocity is unavailable")

            last_error = None
            result = None
            velocity_stream_kwargs_candidates = []
            for basis in basis_candidates:
                velocity_stream_kwargs_candidates.extend(
                    [
                        {"model_name": trajectory_name or None, "basis": basis, "mode": "stream"},
                        {"basis": basis, "mode": "stream"},
                    ]
                )
            velocity_stream_kwargs_candidates.extend(
                [
                    {"model_name": trajectory_name or None, "mode": "stream"},
                    {"mode": "stream"},
                ]
            )
            for kwargs in velocity_stream_kwargs_candidates:
                try:
                    result = plot_velocity_func(fadata, **kwargs)
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
            if last_error is not None:
                raise last_error
            fig = _extract_first_figure(result)
            fig = _prepare_overlay_figure(fig, layout_name) if overlay else _apply_static_plot_title(fig, fadata, trajectory_name, view)
            return _figure_to_png_bytes(fig, transparent=overlay, tight=not overlay)

        plot_stream_func = None
        if plot_ns is not None and hasattr(plot_ns, "plot_stream"):
            plot_stream_func = plot_ns.plot_stream
        elif alt_plot_ns is not None and hasattr(alt_plot_ns, "plot_stream"):
            plot_stream_func = alt_plot_ns.plot_stream
        if plot_stream_func is None:
            raise AttributeError("cafe.plot_stream is unavailable")

        last_error = None
        result = None
        stream_kwargs_candidates = []
        for basis in basis_candidates:
            stream_kwargs_candidates.extend(
                [
                    {
                        "model_name": trajectory_name or None,
                        "mode": "cell",
                        "basis": basis,
                        "color": "clusters",
                    },
                    {
                        "model_name": trajectory_name or None,
                        "basis": basis,
                        "color": "clusters",
                    },
                    {"basis": basis, "color": "clusters"},
                    {"basis": basis},
                ]
            )
        stream_kwargs_candidates.extend(
            [
                {"model_name": trajectory_name or None, "mode": "cell", "color": "clusters"},
                {"model_name": trajectory_name or None, "color": "clusters"},
                {"color": "clusters"},
                {},
            ]
        )
        for kwargs in stream_kwargs_candidates:
            try:
                result = plot_stream_func(fadata, **kwargs)
                last_error = None
                break
            except Exception as error:
                last_error = error
        if last_error is not None:
            raise last_error
    else:
        raise ValueError(f"Unsupported view: {view}")

    fig = _extract_first_figure(result)
    fig = _prepare_overlay_figure(fig, layout_name) if overlay else _apply_static_plot_title(fig, fadata, trajectory_name, view)
    return _figure_to_png_bytes(fig, transparent=overlay, tight=not overlay)
