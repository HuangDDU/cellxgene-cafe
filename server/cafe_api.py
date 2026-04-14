"""Flask route layer for the CAFE plugin backend."""

import os

from flask import Blueprint, current_app, jsonify, make_response, request

from .cafe_util import (
    _build_benchmark_rows,
    _build_preview,
    _dataset_meta,
    _draw_preview_fallback,
    _draw_text_fallback,
    _load_effective_trajectory_history,
    _render_static_with_cafe,
    _resolve_selection,
)

cafe_bp = Blueprint("cafe", __name__, url_prefix="/api/cafe")


@cafe_bp.route("/manifest", methods=["GET"])
def get_manifest():
    """Return plugin metadata and enabled modules for frontend bootstrap."""
    payload = {
        "apiVersion": 1,
        "dataset": _dataset_meta(),
        "plugin": {"name": "cafe", "version": "0.1.0"},
        "capabilities": ["plot", "data", "method", "explorer", "agent"],
        "defaultTab": "plot",
        "modules": [
            {"key": "plot", "enabled": True},
            {"key": "data", "enabled": False},
            {"key": "method", "enabled": False},
            {"key": "explorer", "enabled": True},
            {"key": "agent", "enabled": False},
        ],
    }
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/context", methods=["GET"])
def get_context():
    """Return normalized trajectory context used by Dynamics and Explorer UI sections."""
    uns, trajectory_history = _load_effective_trajectory_history()
    trajectory_name, layout_name, entry, trajectory_names, layout_names = _resolve_selection(
        trajectory_history,
        request.args.get("trajectory", ""),
        request.args.get("layout", ""),
    )

    if not trajectory_names:
        return make_response(
            jsonify(
                {
                    "dataset": _dataset_meta(),
                    "trajectories": [],
                    "current": {"trajectory": "", "layout": ""},
                    "plot": {
                        "benchmarkRows": [],
                        "metricKeys": [],
                        "preview": {"nodes": [], "edges": [], "waypointSegments": {}},
                    },
                }
            ),
            200,
        )

    benchmark_rows, metric_keys = _build_benchmark_rows(trajectory_history)
    preview = _build_preview(entry, layout_name)

    payload = {
        "dataset": _dataset_meta(),
        "host": {
            "engine": "cellxgene",
            "apiVersion": "v0.2",
        },
        "trajectories": trajectory_names,
        "layouts": layout_names,
        "current": {
            "trajectory": trajectory_name,
            "layout": layout_name,
        },
        "plot": {
            "benchmarkRows": benchmark_rows,
            "metricKeys": metric_keys,
            "preview": {
                "nodes": preview["nodes"],
                "edges": preview["edges"],
                "waypointSegments": preview["waypointSegments"],
            },
            "overlaySpec": {
                "milestonePositions": preview["milestonePositions"],
                "wpSegments": preview["wpSegments"],
            },
        },
        "gateway": {
            "enabled": bool(os.environ.get("CAFE_GATEWAY_URL")),
            "url": os.environ.get("CAFE_GATEWAY_URL", ""),
        },
    }
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/plot/static", methods=["GET"])
def get_static_plot():
    """Render a static PNG with cafe.plot, then gracefully degrade to fallback drawing."""
    view = str(request.args.get("view", "trajectory")).strip().lower() or "trajectory"
    if view not in {"trajectory", "graph", "stream"}:
        view = "trajectory"

    uns, trajectory_history = _load_effective_trajectory_history()
    trajectory_name, layout_name, entry, trajectory_names, _ = _resolve_selection(
        trajectory_history,
        request.args.get("trajectory", ""),
        request.args.get("layout", ""),
    )

    if not trajectory_names:
        png_data = _draw_text_fallback(
            title="CAFE static plot",
            message="No trajectory history is available in uns['cafe']['trajectory_history_dict'].",
        )
        response = make_response(png_data, 200)
        response.headers["Content-Type"] = "image/png"
        response.headers["X-CAFE-PLOT-SOURCE"] = "fallback-no-trajectory"
        return response

    try:
        png_data = _render_static_with_cafe(view, trajectory_name, layout_name)
        response = make_response(png_data, 200)
        response.headers["Content-Type"] = "image/png"
        response.headers["X-CAFE-PLOT-SOURCE"] = "cafe.plot"
        return response
    except Exception as error:
        current_app.logger.warning("Static plot render failed for view=%s trajectory=%s layout=%s: %s", view, trajectory_name, layout_name, error)
        preview = _build_preview(entry, layout_name)
        if view in {"trajectory", "graph"}:
            png_data = _draw_preview_fallback(
                preview,
                title=f"{view.title()} static fallback",
                message=f"Fallback rendered because cafe.plot failed: {error}",
            )
            source = "fallback-preview"
        else:
            png_data = _draw_text_fallback(
                title="Stream static fallback",
                message=(
                    "Stream static rendering failed in backend cafe.plot. "
                    f"\nReason: {error}"
                ),
            )
            source = "fallback-text"

        response = make_response(png_data, 200)
        response.headers["Content-Type"] = "image/png"
        response.headers["X-CAFE-PLOT-SOURCE"] = source
        return response


@cafe_bp.route("/trajectory/spec", methods=["GET"])
def get_trajectory_spec():
    """Backward-compatible alias for context response."""
    context_response = get_context()
    return context_response


@cafe_bp.route("/gateway/status", methods=["GET"])
def get_gateway_status():
    """Expose gateway capability and configured control-plane URL."""
    payload = {
        "enabled": bool(os.environ.get("CAFE_GATEWAY_URL")),
        "url": os.environ.get("CAFE_GATEWAY_URL", ""),
        "message": "Gateway control-plane hook is reserved for stage 4.",
    }
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/job/submit", methods=["POST"])
def submit_job_placeholder():
    """Reserved endpoint for method job scheduler integration."""
    return make_response(
        jsonify(
            {
                "status": "not_implemented",
                "message": "Method job scheduler is TODO. This endpoint is reserved by architecture.",
            }
        ),
        501,
    )


@cafe_bp.route("/job/<job_id>", methods=["GET"])
def query_job_placeholder(job_id: str):
    """Reserved endpoint for method job status lookup."""
    return make_response(
        jsonify(
            {
                "status": "not_implemented",
                "jobId": job_id,
                "message": "Method job status API is TODO. This endpoint is reserved by architecture.",
            }
        ),
        501,
    )
