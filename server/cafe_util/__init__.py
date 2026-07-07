"""cafe_util package — backward-compatible re-exports."""

from .adata import (
    _build_benchmark_rows,
    _data_model_meta,
    _dataset_meta,
    _layout_names,
    _load_effective_trajectory_history,
    _resolve_selection,
    _trajectory_history_dict,
)

from .common import (
    _as_float,
    _best_default,
    _rows_from_maybe_table,
    _to_json_value,
    _trajectory_entry_summary,
)

from .data import (
    _build_data_h5ad_export,
    _build_data_summary,
    _build_data_trajectory_package_export,
    _build_debug_source_payload,
    _cleanup_export_dir
)

from .explorer import (
    _build_explorer_summary
)

from .method import (
    _cancel_method_job,
    _method_catalog,
    _method_job_logs,
    _method_job_result,
    _query_method_job,
    _submit_method_job,
    _trajectory_options
)

from .plot import (
    _build_preview,
    _draw_preview_fallback,
    _draw_text_fallback,
    _render_static_with_cafe
)
