import ast
import json
import os
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


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

def _first_present(row: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""

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

def _runtime_display_name(runtime_key: str) -> str:
    display_names = {
        "python_function": "Local Python",
        "conda": "Conda",
        "cafe_docker": "Cafe Docker",
        "dynverse_docker": "Dynverse Docker",
    }
    return display_names.get(runtime_key, runtime_key)

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

