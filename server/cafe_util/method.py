import ast
import csv
import os
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime
from importlib import util as importlib_util
from typing import Any, Dict, List, Tuple

from flask import current_app

from .adata import (
    _dataset_meta,
    _get_live_adata,
    _load_effective_fadata,
    _load_method_execution_runtime,
    _serialize_trajectory_dict_for_uns
)

from .common import (
    _annotation_text,
    _infer_schema_input_kind,
    _runtime_display_name,
    _safe_dict,
    _safe_literal_eval,
    _to_json_value,
    _trajectory_entry_summary,
    _try_numeric
)

from .compat import (
    _patch_scvelo_sparse_compat
)

_METHOD_JOB_LOCK = threading.Lock()
_METHOD_JOBS: Dict[str, Dict[str, Any]] = {}


def _find_cafe_method_root() -> str:
    spec = importlib_util.find_spec("cafe.method")
    if spec is None or spec.origin is None:
        raise RuntimeError("Unable to locate installed cafe.method package.")
    return os.path.dirname(spec.origin)

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

