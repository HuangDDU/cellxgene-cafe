"""Utility helpers for the CAFE plugin backend routes."""

import json
import os
from io import BytesIO
from typing import Any, Dict, List, Tuple

from flask import current_app


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
    if trajectory_history:
        return uns, trajectory_history

    uns_from_file = _load_uns_from_dataset_file()
    trajectory_history_from_file = _trajectory_history_dict(uns_from_file)
    if trajectory_history_from_file:
        return uns_from_file, trajectory_history_from_file

    return uns, trajectory_history


def _layout_names(entry: Dict[str, Any]) -> List[str]:
    trajectory_embedding = entry.get("trajectory_embedding", {})
    if not isinstance(trajectory_embedding, dict):
        return []
    return sorted(trajectory_embedding.keys())


def _build_preview(entry: Dict[str, Any], layout_name: str) -> Dict[str, Any]:
    trajectory_embedding = entry.get("trajectory_embedding", {})
    layout_payload = trajectory_embedding.get(layout_name, {}) if isinstance(trajectory_embedding, dict) else {}

    milestone_rows = _rows_from_maybe_table(layout_payload.get("milestone_positions", []))
    waypoint_rows = _rows_from_maybe_table(layout_payload.get("wp_segments", []))

    id_list = entry.get("milestone_wrapper", {}).get("id_list", [])
    color_list = entry.get("milestone_wrapper", {}).get("color_list", [])
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


def _build_benchmark_rows(trajectory_history: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    rows: List[Dict[str, Any]] = []
    metric_keys = set()

    for trajectory_name, payload in trajectory_history.items():
        metric_dict = payload.get("metric_dict", {}) if isinstance(payload, dict) else {}
        row: Dict[str, Any] = {"id": trajectory_name}
        if isinstance(metric_dict, dict):
            for key, value in metric_dict.items():
                metric_keys.add(key)
                if isinstance(value, (int, float)):
                    row[key] = _as_float(value, default=0.0)
                else:
                    row[key] = _to_json_value(value)
        rows.append(row)

    return rows, sorted(metric_keys)


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
    layout_name = (
        requested_layout
        if requested_layout in layout_names
        else _best_default(layout_names, ["umap", "tsne", "pca"])
    )
    return trajectory_name, layout_name, entry, trajectory_names, layout_names


def _figure_to_png_bytes(fig: Any) -> bytes:
    import matplotlib.pyplot as plt

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", dpi=140)
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()


def _extract_first_figure(render_result: Any) -> Any:
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


def _draw_preview_fallback(preview: Dict[str, Any], title: str, message: str = "") -> bytes:
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
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.set_title(title)
    ax.axis("off")
    ax.text(0.02, 0.92, message, transform=ax.transAxes, va="top", ha="left", fontsize=10, color="#334155", wrap=True)
    return _figure_to_png_bytes(fig)


def _render_static_with_cafe(view: str, trajectory_name: str, layout_name: str) -> bytes:
    # Enforce non-interactive backend for Flask server rendering.
    import matplotlib

    matplotlib.use("Agg", force=True)
    import cafe
    from cafe.data import FateAnnData

    plot_ns = getattr(cafe, "plot", None)
    alt_plot_ns = getattr(cafe, "pl", None)

    data_adaptor = current_app.data_adaptor
    adata = getattr(data_adaptor, "data", None)
    if adata is None:
        raise RuntimeError("data_adaptor.data is unavailable")

    fadata = FateAnnData.from_anndata(adata)
    basis_candidates: List[Any] = [None]
    if layout_name:
        basis_candidates = [layout_name]
        if not str(layout_name).startswith("X_"):
            basis_candidates.append(f"X_{layout_name}")

    if view == "graph":
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
                result = plot_trajectory_func(fadata, **kwargs)
                last_error = None
                break
            except Exception as error:
                last_error = error
        if last_error is not None:
            raise last_error
    elif view == "stream":
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

    return _figure_to_png_bytes(_extract_first_figure(result))
