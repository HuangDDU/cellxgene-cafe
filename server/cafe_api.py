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
            {"key": "agent", "enabled": True},
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
    """Render a static PNG with cafe.plot, with img/ caching to avoid repeated rendering."""
    import os as _os
    try:
        view = str(request.args.get("view", "trajectory")).strip().lower() or "trajectory"
        if view not in {"trajectory", "graph", "stream"}:
            view = "trajectory"
        overlay = str(request.args.get("overlay", "")).strip().lower() in {"1", "true", "yes"}

        # Check static plot cache (img/ subdirectory)
        cache_dir = _resolve_cafe_cache_dir()
        cached_png = None
        if cache_dir:
            uns, trajectory_history = _load_effective_trajectory_history()
            t_name, l_name, _, _, _ = _resolve_selection(
                trajectory_history,
                request.args.get("trajectory", ""),
                request.args.get("layout", ""),
            )
            if t_name and l_name:
                cache_path = _os.path.join(cache_dir, "img", f"{view}_{t_name}_{l_name}.png")
                if _os.path.isfile(cache_path):
                    try:
                        with open(cache_path, "rb") as f:
                            cached_png = f.read()
                    except Exception:
                        cached_png = None

        if cached_png is not None:
            response = make_response(cached_png, 200)
            response.headers["Content-Type"] = "image/png"
            response.headers["X-CAFE-PLOT-SOURCE"] = "cache-img"
            return response

        uns, trajectory_history = _load_effective_trajectory_history()
        trajectory_name, layout_name, entry, trajectory_names, _ = _resolve_selection(
            trajectory_history,
            request.args.get("trajectory", ""),
            request.args.get("layout", ""),
        )
        print(f"Static plot request: view={view} trajectory={trajectory_name} layout={layout_name} overlay={overlay}")
        
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
            # Save to cache for future requests
            if cache_dir and trajectory_name and layout_name:
                try:
                    img_dir = _os.path.join(cache_dir, "img")
                    _os.makedirs(img_dir, exist_ok=True)
                    cache_path = _os.path.join(img_dir, f"{view}_{trajectory_name}_{layout_name}.png")
                    with open(cache_path, "wb") as f:
                        f.write(png_data)
                except Exception:
                    pass
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


@cafe_bp.route("/agent/query", methods=["POST"])
def agent_query():
    """Accept an LLM-style query about cell fate analysis and return a response."""
    import os as _os

    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return make_response(jsonify({"status": "error", "message": "Empty query"}), 400)

    # Build a rich context summary to include with the prompt
    try:
        from .cafe_util.data import _build_data_summary
        from .cafe_util.adata import _load_effective_trajectory_history
    except ImportError:
        from cafe_util.data import _build_data_summary
        from cafe_util.adata import _load_effective_trajectory_history

    data_summary = _build_data_summary() or {}
    trajectories = data_summary.get("trajectories", [])
    prior_info = data_summary.get("fateAnnData", {}).get("priorInformation", {})
    dataset = data_summary.get("dataset", {})

    context_text = f"""Dataset: {dataset.get('name', 'unknown')}
Shape: {dataset.get('shape', {}).get('nObs', '?')} cells × {dataset.get('shape', {}).get('nVars', '?')} genes
Trajectories available: {', '.join([t.get('displayName', t.get('id', '?')) for t in trajectories[:10]])}
Prior knowledge: {str(prior_info)[:500]}
"""

    api_key = _os.environ.get("CAFE_LLM_API_KEY", "")
    api_base = _os.environ.get("CAFE_LLM_API_BASE", "https://api.openai.com/v1")
    model = _os.environ.get("CAFE_LLM_MODEL", "")

    if api_key and model:
        # Use LLM API
        try:
            import requests as _requests
            resp = _requests.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": f"You are Cafe Agent, an expert in single-cell RNA-seq cell fate trajectory analysis. Answer questions based on the provided dataset context.\n\nDataset Context:\n{context_text}"},
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 800,
                    "temperature": 0.7,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                body = resp.json()
                answer = body.get("choices", [{}])[0].get("message", {}).get("content", "No response.")
                return make_response(jsonify({"status": "ok", "response": answer}), 200)
            else:
                current_app.logger.warning("LLM API error: %s %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            current_app.logger.warning("LLM API call failed: %s", exc)

    # Fallback: return a structured response based on available data
    import json as _json
    lower_q = query.lower()
    if "trajectory" in lower_q or "overview" in lower_q:
        answer = f"The dataset '{dataset.get('name', 'unknown')}' contains {len(trajectories)} trajectories: {', '.join([t.get('displayName', t.get('id', '?')) for t in trajectories])}. Each trajectory represents a cell fate lineage inferred from single-cell transcriptomics data."
    elif "driver" in lower_q or "gene" in lower_q:
        answer = "Driver genes are identified based on their differential expression along trajectory branches. To get specific driver gene results, run the Explorer > Drivers analysis for the trajectory of interest."
    elif "benchmark" in lower_q or "method" in lower_q:
        answer = f"The current dataset has {len(trajectories)} trajectories available for benchmarking. Visit the Explorer > Benchmark tab to view metric comparisons and Explorer > Comparison for cross-method rankings."
    elif "next" in lower_q or "suggest" in lower_q:
        answer = "Suggested next steps:\n1. Run driver gene analysis to identify key regulators\n2. Compare trajectory methods in Explorer > Comparison\n3. Check gene expression trends along pseudotime in Explorer > Trends\n4. Export the trajectory package for offline analysis"
    else:
        answer = f"I'm Cafe Agent, here to help with cell fate trajectory analysis. The current dataset '{dataset.get('name', 'unknown')}' has {len(trajectories)} trajectories. You can ask about trajectories, driver genes, benchmark metrics, method comparison, or suggested next steps."

    return make_response(jsonify({"status": "ok", "response": answer, "fallback": not (api_key and model)}), 200)


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


# ---- Cafe Cache helpers ----

def _resolve_cafe_cache_dir():
    """Resolve cafe cache directory: fadata.result_dir → CAFE_RESULT_DIR env → None."""
    import os as _os
    try:
        from .cafe_util.adata import _load_effective_fadata
    except ImportError:
        from cafe_util.adata import _load_effective_fadata
    fadata, _ = _load_effective_fadata()
    if fadata is not None and hasattr(fadata, "result_dir") and _os.path.isdir(fadata.result_dir):
        return fadata.result_dir
    env_dir = _os.environ.get("CAFE_RESULT_DIR", "")
    if env_dir and _os.path.isdir(env_dir):
        return env_dir
    return None


def _scan_cache_subdirs(cache_dir):
    """Scan cafe cache directory. Returns {subdir_name: [file_names]}."""
    import os as _os
    subs = {}
    for name in ("img", "h5ad", "log", "metric", "benchmark", "trajectory_history"):
        path = _os.path.join(cache_dir, name)
        if _os.path.isdir(path):
            subs[name] = sorted(_os.listdir(path))
    return subs


# ---- Cafe Cache endpoints ----

@cafe_bp.route("/data/cafe-cache", methods=["GET"])
def list_cafe_cache():
    """List Cafe Cache directory contents."""
    import os as _os, time as _time
    cache_dir = _resolve_cafe_cache_dir()
    if not cache_dir:
        return make_response(jsonify({
            "status": "ok", "cacheDir": None, "message": "No cafe cache directory found. Set CAFE_RESULT_DIR or ensure fadata.result_dir is available.",
            "subdirs": {}, "imported": [],
        }), 200)

    try:
        from .cafe_util.adata import _load_effective_trajectory_history
    except ImportError:
        from cafe_util.adata import _load_effective_trajectory_history

    subdirs = _scan_cache_subdirs(cache_dir)
    _, trajectory_history = _load_effective_trajectory_history()
    imported_names = sorted(trajectory_history.keys()) if trajectory_history else []

    # List img files with mtimes
    img_files = []
    img_dir = _os.path.join(cache_dir, "img")
    if _os.path.isdir(img_dir):
        for fname in sorted(_os.listdir(img_dir)):
            fpath = _os.path.join(img_dir, fname)
            img_files.append({"name": fname, "mtime": _os.path.getmtime(fpath)})

    # List trajectory_history pkl files
    traj_files = []
    traj_dir = _os.path.join(cache_dir, "trajectory_history")
    if _os.path.isdir(traj_dir):
        for fname in sorted(_os.listdir(traj_dir)):
            if fname.endswith(".pkl"):
                fpath = _os.path.join(traj_dir, fname)
                traj_files.append({"name": fname, "mtime": _os.path.getmtime(fpath)})

    return make_response(jsonify({
        "status": "ok",
        "cacheDir": cache_dir,
        "subdirs": subdirs,
        "imgFiles": img_files,
        "trajFiles": traj_files,
        "imported": imported_names,
    }), 200)


@cafe_bp.route("/data/import-trajectory", methods=["POST"])
def import_trajectory():
    """Import trajectory_history/*.pkl into current fadata via load_trajectory_dict."""
    import pickle as _pickle, os as _os
    try:
        from .cafe_util.adata import _load_effective_fadata
    except ImportError:
        from cafe_util.adata import _load_effective_fadata

    payload = request.get_json(silent=True) or {}
    pkl_name = payload.get("name", "")
    import_all = payload.get("all", False)

    if not pkl_name and not import_all:
        return make_response(jsonify({"status": "error", "message": "Provide pkl name or all=true"}), 400)

    cache_dir = _resolve_cafe_cache_dir()
    if not cache_dir:
        return make_response(jsonify({"status": "error", "message": "No cafe cache directory"}), 503)

    traj_dir = _os.path.join(cache_dir, "trajectory_history")
    if not _os.path.isdir(traj_dir):
        return make_response(jsonify({"status": "error", "message": "No trajectory_history/ in cache"}), 404)

    fadata, err = _load_effective_fadata()
    if fadata is None:
        return make_response(jsonify({"status": "error", "message": f"No FateAnnData: {err}"}), 503)

    imported = []
    pkl_files = []
    if import_all:
        pkl_files = sorted(f for f in _os.listdir(traj_dir) if f.endswith(".pkl"))
    elif pkl_name:
        path = _os.path.join(traj_dir, pkl_name)
        if _os.path.isfile(path):
            pkl_files = [pkl_name]
        else:
            return make_response(jsonify({"status": "error", "message": f"Not found: {pkl_name}"}), 404)

    for fname in pkl_files:
        try:
            with open(_os.path.join(traj_dir, fname), "rb") as f:
                trajectory_dict = _pickle.load(f)
            # load_trajectory_dict merges trajectory into fadata
            fadata.load_trajectory_dict(trajectory_dict)
            imported.append(fname)
        except Exception as exc:
            current_app.logger.warning("Failed to import trajectory %s: %s", fname, exc)

    return make_response(jsonify({
        "status": "ok",
        "imported": len(imported),
        "files": imported,
    }), 200)


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
