"""Unit tests for cafe_util helper functions."""

import pytest
import json

# Import the module under test.
# Many functions require current_app context; we test those that don't.
from cafe_util import (
    _as_float,
    _best_default,
    _to_json_value,
    _rows_from_maybe_table,
    _trajectory_history_dict,
    _resolve_selection,
    _layout_names,
)


class TestAsFloat:
    def test_float(self):
        assert _as_float(3.14) == 3.14

    def test_int(self):
        assert _as_float(42) == 42.0

    def test_string_number(self):
        assert _as_float("2.718") == 2.718

    def test_none_returns_default(self):
        assert _as_float(None) == 0.0

    def test_none_custom_default(self):
        assert _as_float(None, default=-1.0) == -1.0

    def test_invalid_string(self):
        assert _as_float("hello") == 0.0

    def test_invalid_string_custom_default(self):
        assert _as_float("hello", default=99.0) == 99.0


class TestBestDefault:
    def test_returns_preferred_match(self):
        assert _best_default(["umap", "tsne", "pca"], ["tsne"]) == "tsne"

    def test_case_insensitive_match(self):
        assert _best_default(["UMAP", "tSNE"], ["tsne"]) == "tSNE"

    def test_first_preferred_wins(self):
        assert _best_default(["umap", "tsne"], ["tsne", "umap"]) == "tsne"

    def test_fallback_to_first_item(self):
        assert _best_default(["pca", "umap"], ["tsne"]) == "pca"

    def test_empty_list(self):
        assert _best_default([], ["tsne"]) == ""


class TestToJsonValue:
    def test_none(self):
        assert _to_json_value(None) is None

    def test_primitive(self):
        assert _to_json_value("hello") == "hello"
        assert _to_json_value(42) == 42
        assert _to_json_value(True) is True

    def test_list(self):
        assert _to_json_value([1, "a", True]) == [1, "a", True]

    def test_tuple(self):
        assert _to_json_value((1, 2)) == [1, 2]

    def test_dict(self):
        assert _to_json_value({"a": 1}) == {"a": 1}

    def test_nested(self):
        result = _to_json_value({"x": [1, {"y": 2}]})
        assert result == {"x": [1, {"y": 2}]}

    def test_non_serializable_falls_back_to_string(self):
        class Foo:
            def __str__(self):
                return "Foo instance"

        result = _to_json_value(Foo())
        assert result == "Foo instance"


class TestRowsFromMaybeTable:
    def test_pandas_dataframe_to_dict(self):
        """Simulate a pandas DataFrame with to_dict('records')."""
        class FakeDataFrame:
            def to_dict(self, orient="records"):
                return [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        rows = _rows_from_maybe_table(FakeDataFrame())
        assert len(rows) == 2
        assert rows[0] == {"a": 1, "b": 2}

    def test_list_of_dicts(self):
        rows = _rows_from_maybe_table([{"x": 1}, {"x": 2}])
        assert len(rows) == 2

    def test_columnar_dict(self):
        rows = _rows_from_maybe_table({"col": [10, 20, 30]})
        assert len(rows) == 3
        assert rows[0] == {"col": 10}

    def test_single_dict(self):
        rows = _rows_from_maybe_table({"a": 1, "b": 2})
        assert len(rows) == 1
        assert rows[0] == {"a": 1, "b": 2}

    def test_empty_value(self):
        assert _rows_from_maybe_table(None) == []
        assert _rows_from_maybe_table([]) == []


class TestTrajectoryHistoryDict:
    def test_cafe_key(self):
        uns = {"cafe": {"trajectory_history_dict": {"ref": {"key": "val"}}}}
        assert _trajectory_history_dict(uns) == {"ref": {"key": "val"}}

    def test_cfe_fallback(self):
        uns = {"cfe": {"trajectory_history_dict": {"ref": {}}}}
        assert _trajectory_history_dict(uns) == {"ref": {}}

    def test_cafe_priority_over_cfe(self):
        uns = {
            "cafe": {"trajectory_history_dict": {"ref": {}}},
            "cfe": {"trajectory_history_dict": {"other": {}}},
        }
        assert _trajectory_history_dict(uns) == {"ref": {}}

    def test_missing_key(self):
        assert _trajectory_history_dict({}) == {}

    def test_non_dict_value(self):
        assert _trajectory_history_dict({"cafe": {"trajectory_history_dict": "not_dict"}}) == {}


class TestLayoutNames:
    def test_returns_sorted_keys(self):
        entry = {"trajectory_embedding": {"umap": {}, "tsne": {}, "pca": {}}}
        assert _layout_names(entry) == ["pca", "tsne", "umap"]

    def test_empty(self):
        assert _layout_names({}) == []
        assert _layout_names({"trajectory_embedding": "not_dict"}) == []


class TestResolveSelection:
    def test_finds_ref_by_default(self):
        history = {"ref": {"trajectory_embedding": {"umap": {}}}}
        name, layout, entry, names, layouts = _resolve_selection(history, "", "")
        assert name == "ref"
        assert layout == "umap"

    def test_prefers_requested_trajectory(self):
        history = {"ref": {"trajectory_embedding": {"umap": {}}}, "palantir": {"trajectory_embedding": {"umap": {}}}}
        name, layout, entry, names, layouts = _resolve_selection(history, "palantir", "")
        assert name == "palantir"

    def test_prefers_requested_layout(self):
        history = {"ref": {"trajectory_embedding": {"tsne": {}, "umap": {}}}}
        name, layout, entry, names, layouts = _resolve_selection(history, "", "tsne")
        assert layout == "tsne"

    def test_falls_back_to_umap(self):
        history = {"ref": {"trajectory_embedding": {"umap": {}, "pca": {}}}}
        name, layout, entry, names, layouts = _resolve_selection(history, "", "")
        assert layout == "umap"

    def test_empty_history(self):
        name, layout, entry, names, layouts = _resolve_selection({}, "", "")
        assert name == ""
        assert layout == ""
        assert names == []
