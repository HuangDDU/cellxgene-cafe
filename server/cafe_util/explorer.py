import ast
import csv
import json
import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from flask import current_app
from scipy.stats import hypergeom

from .adata import (
    _align_cell_id_list_to_obs,
    _align_cell_id_table_to_obs,
    _align_positional_trajectory_cell_ids,
    _build_benchmark_rows,
    _dataset_meta,
    _drop_missing_resource_metrics,
    _get_live_adata,
    _has_numeric_metric_dict,
    _load_effective_fadata,
    _load_effective_trajectory_history,
    _load_fate_anndata_runtime,
    _parse_positional_cell_id,
    _resolve_selection,
    _row_to_numeric_metric_dict,
    _serialize_trajectory_dict_for_uns,
)

from .common import (
    _as_sequence,
    _first_present,
    _get_item_attr,
    _restore_serialized_trajectory_wrappers,
    _rows_from_maybe_table,
    _safe_dict,
    _trajectory_entry_summary,
    _try_numeric
)


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

def _build_integration_status(
    trajectory_history: Dict[str, Any],
    driver_genes: Dict[str, Any] = None,
    allow_computed_fallback: bool = True,
) -> List[Dict[str, Any]]:
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
        fallback = {} if count > 0 or not allow_computed_fallback else config["fallback"]()
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
                    else fallback.get("message") or (
                        "Computed fallback is deferred until Explorer details finish loading."
                        if not allow_computed_fallback
                        else config["emptyMessage"]
                    )
                ),
            }
        )
    return items

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
    include_heavy: bool = True,
) -> Dict[str, Any]:
    _, trajectory_history = _load_effective_trajectory_history()
    trajectory_name, layout_name, entry, trajectory_names, layout_names = _resolve_selection(
        trajectory_history,
        requested_trajectory,
        requested_layout,
    )
    if include_heavy:
        metric_status = _ensure_explorer_benchmark_metrics(trajectory_history)
    else:
        metric_status = {
            "attempted": False,
            "calculated": [],
            "skipped": [],
            "message": "Benchmark metric calculation is deferred for the lightweight Explorer summary.",
        }

    if include_heavy and metric_status.get("calculated"):
        _, trajectory_history = _load_effective_trajectory_history()
        trajectory_name, layout_name, entry, trajectory_names, layout_names = _resolve_selection(
            trajectory_history,
            requested_trajectory,
            requested_layout,
        )
    benchmark_rows, metric_keys = _build_benchmark_rows(trajectory_history)
    gene_selection = _search_explorer_gene_names(gene_query, selected_genes)

    if include_heavy:
        driver_genes = _compute_selected_driver_genes(trajectory_history, trajectory_name)
    else:
        driver_genes = {
            "available": False,
            "items": [],
            "sourceKeys": [],
            "message": "Driver gene calculation is deferred for the lightweight Explorer summary.",
        }

    if not driver_genes.get("available"):
        computed_driver_genes = driver_genes
        driver_genes = _extract_driver_genes(trajectory_history)
        if not driver_genes.get("available") and computed_driver_genes.get("message"):
            driver_genes["message"] = (
                f"{driver_genes['message']} "
                f"Computed fallback also failed: {computed_driver_genes['message']}"
            )

    if include_heavy:
        gene_trends = _compute_selected_gene_trends(
            trajectory_history,
            trajectory_name,
            driver_genes,
            selected_genes=gene_selection["selectedGenes"],
        )
    else:
        gene_trends = {
            "available": False,
            "series": [],
            "sourceKeys": [],
            "message": "Gene trend calculation is deferred for the lightweight Explorer summary.",
        }

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
        "integrations": _build_integration_status(
            trajectory_history,
            driver_genes,
            allow_computed_fallback=include_heavy,
        ),
        "detailDeferred": not include_heavy,
    }
