"""Flask route layer for the CAFE plugin backend."""

import os

from flask import Blueprint, current_app, jsonify, make_response, request, send_file

from .cafe_util import (
    _build_debug_source_payload,
    _build_data_h5ad_export,
    _build_data_summary,
    _build_data_trajectory_package_export,
    _build_benchmark_rows,
    _build_explorer_summary,
    _cancel_method_job,
    _cleanup_export_dir,
    _dataset_meta,
    _build_preview,
    _trajectory_options,
    _trajectory_entry_summary,
    _draw_preview_fallback,
    _draw_text_fallback,
    _load_effective_trajectory_history,
    _method_catalog,
    _method_job_logs,
    _method_job_result,
    _query_method_job,
    _render_static_with_cafe,
    _resolve_selection,
    _submit_method_job,
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
            {"key": "data", "enabled": True},
            {"key": "method", "enabled": True},
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
                    "trajectoryOptions": [],
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
    preview = _build_preview(entry, layout_name, trajectory_name)
    if layout_name and layout_name not in layout_names and (preview["nodes"] or preview["waypointSegments"]):
        layout_names = sorted(set(layout_names + [layout_name]))

    payload = {
        "dataset": _dataset_meta(),
        "host": {
            "engine": "cellxgene",
            "apiVersion": "v0.2",
        },
        "trajectories": trajectory_names,
        "trajectoryOptions": _trajectory_options(trajectory_history),
        "layouts": layout_names,
        "current": {
            "trajectory": trajectory_name,
            "layout": layout_name,
        },
        "currentTrajectory": _trajectory_entry_summary(trajectory_name, entry) if trajectory_name else None,
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
    try:
        view = str(request.args.get("view", "trajectory")).strip().lower() or "trajectory"
        if view not in {"trajectory", "graph", "stream"}:
            view = "trajectory"
        overlay = str(request.args.get("overlay", "")).strip().lower() in {"1", "true", "yes"}

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
            png_data = _render_static_with_cafe(view, trajectory_name, layout_name, overlay=overlay)
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
    except Exception as error:
        current_app.logger.warning("Static plot endpoint failed before render: %s", error)
        png_data = _draw_text_fallback(
            title="CAFE static plot fallback",
            message=f"Static plot endpoint failed before render.\nReason: {error}",
        )
        response = make_response(png_data, 200)
        response.headers["Content-Type"] = "image/png"
        response.headers["X-CAFE-PLOT-SOURCE"] = "fallback-endpoint"
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


@cafe_bp.route("/data/summary", methods=["GET"])
def get_data_summary():
    """Return normalized FateAnnData summary for the Data module."""
    payload = _build_data_summary()
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/debug/source", methods=["GET"])
def get_debug_source():
    """Return raw source-of-truth details for dataset and cafe trajectory state."""
    payload = _build_debug_source_payload()
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/data/export/h5ad", methods=["GET"])
def export_data_h5ad():
    """Export a snapshot h5ad including the effective cafe trajectory state."""
    try:
        export_path, download_name, mimetype, tempdir = _build_data_h5ad_export()
    except Exception as error:
        current_app.logger.warning("Failed to build CAFE h5ad export: %s", error)
        return make_response(
            jsonify({"status": "error", "message": f"Failed to export h5ad snapshot: {error}"}),
            503,
        )

    response = send_file(export_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    response.call_on_close(lambda: _cleanup_export_dir(tempdir))
    return response


@cafe_bp.route("/data/export/trajectory-package", methods=["GET"])
def export_trajectory_package():
    """Export trajectory history as a reproducible offline package."""
    try:
        export_path, download_name, mimetype, tempdir = _build_data_trajectory_package_export()
    except Exception as error:
        current_app.logger.warning("Failed to build CAFE trajectory package export: %s", error)
        return make_response(
            jsonify({"status": "error", "message": f"Failed to export trajectory package: {error}"}),
            503,
        )

    response = send_file(export_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
    response.call_on_close(lambda: _cleanup_export_dir(tempdir))
    return response


@cafe_bp.route("/explorer/summary", methods=["GET"])
def get_explorer_summary():
    """Return normalized downstream analysis summary for the Explorer module."""
    genes_raw = str(request.args.get("genes", ""))
    selected_genes = [item.strip() for item in genes_raw.split(",") if item.strip()]
    payload = _build_explorer_summary(
        request.args.get("trajectory", ""),
        request.args.get("layout", ""),
        selected_genes=selected_genes,
        gene_query=request.args.get("geneQuery", ""),
    )
    return make_response(jsonify(payload), 200)


@cafe_bp.route("/method/catalog", methods=["GET"])
def get_method_catalog():
    """Return method catalog, parameter schema, and runtime choices."""
    try:
        payload = _method_catalog()
        return make_response(jsonify(payload), 200)
    except Exception as error:
        current_app.logger.warning("Failed to build method catalog: %s", error)
        return make_response(
            jsonify({"status": "error", "message": f"Failed to build method catalog: {error}"}),
            503,
        )


@cafe_bp.route("/job/submit", methods=["POST"])
def submit_job():
    """Submit a method orchestration job."""
    try:
        payload = request.get_json(silent=True) or {}
        job = _submit_method_job(payload)
        return make_response(jsonify(job), 202)
    except ValueError as error:
        return make_response(jsonify({"status": "error", "message": str(error)}), 400)
    except Exception as error:
        current_app.logger.warning("Failed to submit method job: %s", error)
        return make_response(jsonify({"status": "error", "message": str(error)}), 503)


@cafe_bp.route("/job/<job_id>", methods=["GET"])
def query_job(job_id: str):
    """Query method job status."""
    try:
        payload = _query_method_job(job_id)
        return make_response(jsonify(payload), 200)
    except KeyError:
        return make_response(jsonify({"status": "error", "message": f"Unknown job: {job_id}"}), 404)


@cafe_bp.route("/job/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id: str):
    """Request cancellation for a method job."""
    try:
        payload = _cancel_method_job(job_id)
        return make_response(jsonify(payload), 200)
    except KeyError:
        return make_response(jsonify({"status": "error", "message": f"Unknown job: {job_id}"}), 404)


@cafe_bp.route("/job/<job_id>/result", methods=["GET"])
def get_job_result(job_id: str):
    """Fetch method job result summary."""
    try:
        payload = _method_job_result(job_id)
        return make_response(jsonify(payload), 200)
    except KeyError:
        return make_response(jsonify({"status": "error", "message": f"Unknown job: {job_id}"}), 404)


@cafe_bp.route("/job/<job_id>/logs", methods=["GET"])
def get_job_logs(job_id: str):
    """Fetch method job logs."""
    try:
        payload = _method_job_logs(job_id)
        return make_response(jsonify(payload), 200)
    except KeyError:
        return make_response(jsonify({"status": "error", "message": f"Unknown job: {job_id}"}), 404)
