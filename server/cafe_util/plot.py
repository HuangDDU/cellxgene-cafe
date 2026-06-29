import os
from io import BytesIO
from typing import Any, Dict, List, Tuple

import numpy as np
from flask import current_app

import matplotlib
matplotlib.use("Agg")

from .adata import (
    _align_positional_trajectory_cell_ids,
    _get_live_adata,
    _load_effective_fadata,
    _load_effective_trajectory_history,
    _preview_basis_candidates,
)

from .common import (
    _as_float,
    _as_sequence,
    _best_default,
    _entry_wrapper_type,
    _get_cafe_container,
    _get_item_attr,
    _rows_from_maybe_table,
    _safe_dict
)

from .compat import (
    _ensure_headless_matplotlib
)


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

    # Align positional cell IDs before calling cafe.plot (fixes cell_000 → real barcode mapping)
    try:
        _align_positional_trajectory_cell_ids(fadata)
    except Exception:
        pass

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
    # TODO: static image cache in .cafe
    # Enforce non-interactive backend for Flask server rendering.
    _ensure_headless_matplotlib()
    import cafe

    plot_ns = getattr(cafe, "plot", None)
    alt_plot_ns = getattr(cafe, "pl", None)

    fadata, fadata_error = _load_effective_fadata()
    if fadata is None:
        raise RuntimeError(fadata_error or "Effective FateAnnData is unavailable")

    # Align positional cell IDs before calling cafe.plot (fixes cell_000 → real barcode mapping)
    try:
        _align_positional_trajectory_cell_ids(fadata)
    except Exception:
        pass

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
