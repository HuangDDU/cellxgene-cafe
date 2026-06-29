import React from "react";
import { connect } from "react-redux";

import { fetchExplorerSummary } from "../../lib/api";
import Benchmark from "./Benchmark";
import DriverGene from "./DriverGene";
import Intergration from "./Intergration";

// ---- pure helper functions ----

function tryNumeric(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return { ok: false, value: 0 };
  }
  const n = Number(value);
  return Number.isFinite(n) ? { ok: true, value: n } : { ok: false, value: 0 };
}

// ---- main component ----

class Explorer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      summary: null,
      loading: true,
      error: "",
      sortMetric: "",
      sortDirection: "desc",
      searchText: "",
      geneQueryInput: "",
      geneQuery: "",
      selectedGenes: [],
      trendScale: "raw",
    };
    this._cancelled = false;
  }

  componentDidMount() {
    // Fetch immediately at app startup so tab is ready (all modules stay mounted)
    this._loadSummary();
  }

  componentDidUpdate(prevProps) {
    // Skip all context-change re-fetches while tab is hidden
    if (!this.props.active) return;

    const ctx = this.props.context;
    const prevCtx = prevProps.context;
    const tChanged = ctx?.current?.trajectory !== prevCtx?.current?.trajectory;
    const lChanged = ctx?.current?.layout !== prevCtx?.current?.layout;
    const gqChanged = this.state.geneQuery !== this._prevGeneQuery;
    const sgChanged = this.state.selectedGenes.join(",") !== (this._prevSelectedGenes || "");

    if (tChanged || lChanged || gqChanged || sgChanged) {
      this._loadSummary();
    }
    this._prevGeneQuery = this.state.geneQuery;
    this._prevSelectedGenes = this.state.selectedGenes.join(",");
  }

  componentWillUnmount() {
    this._cancelled = true;
  }

  async _loadSummary() {
    this.setState({ loading: true, error: "" });
    try {
      const nextSummary = await fetchExplorerSummary({
        trajectory: this.props.context?.current?.trajectory || "",
        layout: this.props.context?.current?.layout || "",
        geneQuery: this.state.geneQuery,
        genes: this.state.selectedGenes.join(","),
      });
      if (this._cancelled) return;
      const nextMetricKeys = nextSummary?.benchmark?.metricKeys || [];
      this.setState((prev) => {
        const patch = { summary: nextSummary, loading: false };
        if (
          (!prev.sortMetric || !nextMetricKeys.includes(prev.sortMetric)) &&
          nextMetricKeys.length
        ) {
          patch.sortMetric = nextMetricKeys[0];
        }
        return patch;
      });
    } catch (err) {
      if (!this._cancelled)
        this.setState({ error: err?.message || "Failed to load Explorer summary", loading: false });
    }
  }

  _visibleBenchmarkRows() {
    const { summary, searchText, sortMetric, sortDirection } = this.state;
    const rows = summary?.benchmark?.rows || [];
    const metricKeys = summary?.benchmark?.metricKeys || [];
    const query = searchText.trim().toLowerCase();
    const filtered = query
      ? rows.filter((r) =>
          String(r.id || "")
            .toLowerCase()
            .includes(query),
        )
      : [...rows];

    filtered.sort((a, b) => {
      const key = sortMetric || "id";
      if (key === "id") {
        return sortDirection === "asc"
          ? String(a.id || "").localeCompare(String(b.id || ""))
          : String(b.id || "").localeCompare(String(a.id || ""));
      }
      const na = tryNumeric(a[key]),
        nb = tryNumeric(b[key]);
      if (na.ok && nb.ok)
        return sortDirection === "asc" ? na.value - nb.value : nb.value - na.value;
      return sortDirection === "asc"
        ? String(a[key] || "").localeCompare(String(b[key] || ""))
        : String(b[key] || "").localeCompare(String(a[key] || ""));
    });
    return filtered;
  }

  render() {
    const { context } = this.props;
    const {
      summary,
      loading,
      error,
      sortMetric,
      sortDirection,
      searchText,
      geneQueryInput,
      selectedGenes,
      trendScale,
    } = this.state;
    if (loading) return <div className="cafe-loading">Loading Explorer summary...</div>;
    if (error) return <div className="cafe-error">{error}</div>;

    const benchmarkRows = summary?.benchmark?.rows || [];
    const metricKeys = summary?.benchmark?.metricKeys || [];
    const driverGenes = summary?.driverGenes || {};
    const geneTrends = summary?.geneTrends || {};
    const geneSelection = summary?.geneSelection || {};
    const integrations = summary?.integrations || [];
    const visibleRows = this._visibleBenchmarkRows();

    const handleAddGene = (gene) => {
      const g = String(gene || "").trim();
      if (!g) return;
      this.setState((prev) => {
        if (prev.selectedGenes.includes(g)) return null;
        return { selectedGenes: [...prev.selectedGenes, g].slice(0, 6) };
      });
    };
    const handleRemoveGene = (gene) =>
      this.setState((prev) => ({ selectedGenes: prev.selectedGenes.filter((g) => g !== gene) }));
    const handleGeneSearch = () =>
      this.setState({ geneQuery: geneQueryInput.trim() });
    const handleClearSearch = () => this.setState({ geneQuery: "", geneQueryInput: "" });

    return (
      <div>
        <Benchmark
          metricKeys={metricKeys}
          rows={visibleRows}
          searchText={searchText}
          sortMetric={sortMetric}
          sortDirection={sortDirection}
          onSearchTextChange={(value) => this.setState({ searchText: value })}
          onSortMetricChange={(value) => this.setState({ sortMetric: value })}
          onSortDirectionChange={(value) => this.setState({ sortDirection: value })}
        />

        <DriverGene
          driverGenes={driverGenes}
          geneSelection={geneSelection}
          geneTrends={geneTrends}
          selectedGenes={selectedGenes}
          geneQueryInput={geneQueryInput}
          trendScale={trendScale}
          onGeneQueryInputChange={(value) => this.setState({ geneQueryInput: value })}
          onGeneSearch={handleGeneSearch}
          onClearSearch={handleClearSearch}
          onAddGene={handleAddGene}
          onRemoveGene={handleRemoveGene}
          onTrendScaleChange={(value) => this.setState({ trendScale: value })}
        />

        <Intergration integrations={integrations} />
      </div>
    );
  }
}

const mapState = (state) => ({
  context: {
    current: {
      trajectory: state.trajectory?.trajectoryName || "",
      layout: state.cellxgene?.layoutChoice?.current || "",
    },
  },
});

export default connect(mapState)(Explorer);
