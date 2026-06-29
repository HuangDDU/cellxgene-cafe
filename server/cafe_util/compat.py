import logging
import os
from typing import Any

from flask import current_app

import matplotlib
matplotlib.use("Agg")


def _patch_cafe_logger() -> None:
    """Enable show_path on cafe's RichHandler so warnings include file:line location."""
    try:
        from cafe._logging import logger as _cafe_logger
        for handler in list(_cafe_logger.handlers):
            if hasattr(handler, "_log_render") or handler.__class__.__name__ == "RichHandler":
                # Enable path display: shows (filename:line) after each log entry
                try:
                    handler._log_render.show_path = True
                except Exception:
                    pass
                handler.setFormatter(logging.Formatter(
                    "%(message)s \x1b[2m(%(filename)s:%(lineno)d)\x1b[0m"
                ))
    except Exception:
        pass


def _ensure_headless_matplotlib() -> None:
    os.environ["MPLBACKEND"] = "Agg"
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    _patch_cafe_logger()

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

