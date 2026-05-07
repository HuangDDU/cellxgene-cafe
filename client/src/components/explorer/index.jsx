import React from "react";

import { fetchExplorerSummary } from "../../lib/api";

// ---- pure helper functions ----

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(3);
  }
  return String(value);
}

function tryNumeric(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return { ok: false, value: 0 };
  }
  const n = Number(value);
  return Number.isFinite(n) ? { ok: true, value: n } : { ok: false, value: 0 };
}

function normalizeTrendPoints(points) {
  if (!points?.length) return [];
  const ys = points.map((p) => Number(p.y));
  const minY = Math.min(...ys);
  const span = Math.max(...ys) - minY || 1;
  return points.map((p) => ({ x: Number(p.x), y: (Number(p.y) - minY) / span }));
}

// ---- pure presentational sub-components (no hooks, no context) ----

class InfoGrid extends React.Component {
  render() {
    const { items } = this.props;
    return (
      <div className="cafe-info-grid">
        {items.map(({ label, value }) => (
          <div key={label} className="cafe-info-item">
            <div className="cafe-info-label">{label}</div>
            <div className="cafe-info-value">{value ?? "n/a"}</div>
          </div>
        ))}
      </div>
    );
  }
}

class MetricBarList extends React.Component {
  render() {
    const { items } = this.props;
    if (!items?.length) return <div className="cafe-note">No numeric rankings.</div>;
    return (
      <div className="cafe-bar-list">
        {items.map((item) => (
          <div key={`${item.id}-${item.rank}`} className="cafe-bar-row">
            <div className="cafe-bar-label">
              <span className="cafe-bar-rank">#{item.rank}</span>
              <span>{item.id}</span>
            </div>
            <div className="cafe-bar-track">
              <div
                className="cafe-bar-fill"
                style={{ width: `${Math.max(item.normalized * 100, 6)}%` }}
              />
            </div>
            <div className="cafe-bar-value">{formatMetricValue(item.value)}</div>
          </div>
        ))}
      </div>
    );
  }
}

class IntegrationPreview extends React.Component {
  render() {
    const { item } = this.props;
    const rows = item.items || [];
    if (!rows.length) return null;

    if (item.key === "grn") {
      return (
        <div className="cafe-table-wrap" style={{ marginTop: "10px" }}>
          <table className="cafe-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Target</th>
                <th>Weight</th>
                <th>Sign</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 8).map((r) => (
                <tr key={`${r.source}-${r.target}`}>
                  <td>{r.source}</td>
                  <td>{r.target}</td>
                  <td>{formatMetricValue(r.weight)}</td>
                  <td>{r.sign}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return (
      <div className="cafe-table-wrap" style={{ marginTop: "10px" }}>
        <table className="cafe-table">
          <thead>
            <tr>
              <th>Term</th>
              <th>Overlap</th>
              <th>Score</th>
              <th>Genes</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 8).map((r) => (
              <tr key={`${item.key}-${r.term}`}>
                <td>{r.term}</td>
                <td>{r.overlap}</td>
                <td>{formatMetricValue(r.score)}</td>
                <td>{r.genes || "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
}

class Sparkline extends React.Component {
  render() {
    const { points } = this.props;
    if (!points?.length) return <div className="cafe-note">No points.</div>;
    const W = 220,
      H = 80;
    const xs = points.map((p) => Number(p.x));
    const ys = points.map((p) => Number(p.y));
    const minX = Math.min(...xs),
      maxX = Math.max(...xs),
      xSpan = maxX - minX || 1;
    const minY = Math.min(...ys),
      maxY = Math.max(...ys),
      ySpan = maxY - minY || 1;
    const d = points
      .map((p, i) => {
        const x = ((Number(p.x) - minX) / xSpan) * (W - 12) + 6;
        const y = H - (((Number(p.y) - minY) / ySpan) * (H - 12) + 6);
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
    return (
      <svg className="cafe-sparkline-svg" viewBox={`0 0 ${W} ${H}`}>
        <path d={d} />
      </svg>
    );
  }
}

class MultiTrendChart extends React.Component {
  render() {
    const { seriesList, scaleMode } = this.props;
    const palette = ["#2f6f9f", "#d67344", "#4d8f4a", "#8b5fbf", "#c2577b", "#4f8f99"];
    const prepared = (seriesList || [])
      .filter((s) => s.points?.length)
      .map((s, i) => ({
        ...s,
        color: palette[i % palette.length],
        points: scaleMode === "normalized" ? normalizeTrendPoints(s.points) : s.points,
      }));
    if (!prepared.length) return <div className="cafe-note">No comparison series.</div>;

    const W = 520,
      H = 220,
      P = 20;
    const xs = prepared.flatMap((s) => s.points.map((p) => Number(p.x)));
    const ys = prepared.flatMap((s) => s.points.map((p) => Number(p.y)));
    const minX = Math.min(...xs),
      maxX = Math.max(...xs),
      xSpan = maxX - minX || 1;
    const minY = Math.min(...ys),
      maxY = Math.max(...ys),
      ySpan = maxY - minY || 1;

    return (
      <div className="cafe-trend-compare-wrap">
        <svg className="cafe-trend-compare-svg" viewBox={`0 0 ${W} ${H}`}>
          <rect x="0" y="0" width={W} height={H} rx="8" ry="8" />
          {prepared.map((s) => {
            const d = s.points
              .map((p, i) => {
                const x = ((Number(p.x) - minX) / xSpan) * (W - P * 2) + P;
                const y = H - (((Number(p.y) - minY) / ySpan) * (H - P * 2) + P);
                return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
              })
              .join(" ");
            return <path key={`${s.trajectoryId}-${s.gene}`} d={d} style={{ stroke: s.color }} />;
          })}
        </svg>
        <div className="cafe-trend-legend">
          {prepared.map((s) => (
            <div key={`${s.trajectoryId}-${s.gene}`} className="cafe-trend-legend-item">
              <span className="cafe-trend-legend-swatch" style={{ background: s.color }} />
              <span>{s.gene}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }
}

// ---- main component ----

export default class Explorer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      summary: null,
      loading: true,
      error: "",
      activeSubModule: "benchmark",
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
    this._loadSummary();
  }

  componentDidUpdate(prevProps) {
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
      activeSubModule,
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
    const comparisonMetrics = summary?.metricComparison?.metrics || [];
    const driverGenes = summary?.driverGenes || {};
    const geneTrends = summary?.geneTrends || {};
    const geneSelection = summary?.geneSelection || {};
    const integrations = summary?.integrations || [];
    const currentTrajectory = summary?.currentTrajectory || null;
    const overallRanking = summary?.metricComparison?.overallRanking || [];
    const visibleRows = this._visibleBenchmarkRows();

    const handleAddGene = (gene) => {
      const g = String(gene || "").trim();
      if (!g) return;
      this.setState((prev) => {
        if (prev.selectedGenes.includes(g)) return null;
        return { selectedGenes: [...prev.selectedGenes, g].slice(0, 6), activeSubModule: "trends" };
      });
    };
    const handleRemoveGene = (gene) =>
      this.setState((prev) => ({ selectedGenes: prev.selectedGenes.filter((g) => g !== gene) }));
    const handleGeneSearch = () =>
      this.setState({ geneQuery: geneQueryInput.trim(), activeSubModule: "trends" });
    const handleClearSearch = () => this.setState({ geneQuery: "", geneQueryInput: "" });

    return (
      <div>
        <div className="cafe-card">
          <h4>Explorer Overview</h4>
          <InfoGrid
            items={[
              { label: "Dataset", value: summary?.dataset?.name },
              {
                label: "Current Trajectory",
                value: currentTrajectory?.id || summary?.selection?.trajectory,
              },
              { label: "Current Layout", value: summary?.selection?.layout },
              { label: "Trajectories", value: summary?.benchmark?.trajectoryCount },
              { label: "Metrics", value: summary?.benchmark?.metricCount },
              { label: "Numeric Metrics", value: summary?.metricComparison?.numericMetricCount },
            ]}
          />
        </div>

        <div className="cafe-card">
          <h4>Explorer</h4>
          <div className="cafe-switch-row">
            {["benchmark", "comparison", "drivers", "trends", "integrations"].map((tab) => (
              <button
                key={tab}
                type="button"
                className={`cafe-chip-btn ${activeSubModule === tab ? "is-active" : ""}`}
                onClick={() => this.setState({ activeSubModule: tab })}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {activeSubModule === "benchmark" && (
          <div className="cafe-card">
            <h4>Trajectory Benchmark</h4>
            {!benchmarkRows.length ? (
              <div className="cafe-note">
                No benchmark metrics found in current trajectory history.
              </div>
            ) : (
              <div>
                <div className="cafe-explorer-toolbar">
                  <div className="cafe-field">
                    <label htmlFor="explorer-search">Search trajectory</label>
                    <input
                      id="explorer-search"
                      type="text"
                      value={searchText}
                      onChange={(e) => this.setState({ searchText: e.target.value })}
                      placeholder="Filter by trajectory id"
                    />
                  </div>
                  <div className="cafe-field">
                    <label htmlFor="explorer-sort">Sort by</label>
                    <select
                      id="explorer-sort"
                      value={sortMetric || "id"}
                      onChange={(e) => this.setState({ sortMetric: e.target.value })}
                    >
                      <option value="id">id</option>
                      {metricKeys.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="cafe-field">
                    <label htmlFor="explorer-direction">Direction</label>
                    <select
                      id="explorer-direction"
                      value={sortDirection}
                      onChange={(e) => this.setState({ sortDirection: e.target.value })}
                    >
                      <option value="desc">desc</option>
                      <option value="asc">asc</option>
                    </select>
                  </div>
                </div>
                <div className="cafe-table-wrap">
                  <table className="cafe-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        {metricKeys.map((k) => (
                          <th key={k}>{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRows.map((row) => (
                        <tr key={row.id}>
                          <td>{row.id}</td>
                          {metricKeys.map((k) => (
                            <td key={`${row.id}-${k}`}>{formatMetricValue(row[k])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeSubModule === "comparison" && (
          <div>
            <div className="cafe-card">
              <h4>Overall Ranking</h4>
              {!overallRanking.length ? (
                <div className="cafe-note">
                  No numeric metrics are available for cross-method ranking.
                </div>
              ) : (
                <div>
                  <div className="cafe-note" style={{ marginBottom: "8px" }}>
                    {summary?.metricComparison?.rankingHeuristic}
                  </div>
                  <MetricBarList items={overallRanking} />
                </div>
              )}
            </div>
            <div className="cafe-explorer-metric-grid">
              {comparisonMetrics
                .filter((m) => m.numeric)
                .map((metric) => (
                  <div key={metric.key} className="cafe-card cafe-explorer-metric-card">
                    <h4>{metric.key}</h4>
                    <InfoGrid
                      items={[
                        { label: "Leader", value: metric.leader?.id },
                        { label: "Best", value: formatMetricValue(metric.leader?.value) },
                        { label: "Min", value: formatMetricValue(metric.range?.min) },
                        { label: "Max", value: formatMetricValue(metric.range?.max) },
                      ]}
                    />
                    <div className="cafe-data-section">
                      <div className="cafe-data-subtitle">Top trajectories</div>
                      <MetricBarList items={metric.rankings} />
                    </div>
                  </div>
                ))}
              {!comparisonMetrics.some((m) => m.numeric) && (
                <div className="cafe-card">
                  <div className="cafe-note">
                    No numeric metric comparison is available for the current dataset.
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeSubModule === "drivers" && (
          <div className="cafe-card">
            <h4>Driver Genes</h4>
            {!driverGenes.available ? (
              <div className="cafe-note">
                {driverGenes.message || "No normalized driver gene table is available yet."}
              </div>
            ) : (
              <div>
                <div className="cafe-note" style={{ marginBottom: "8px" }}>
                  Sources: {driverGenes.sourceKeys?.join(", ") || "n/a"}
                </div>
                <div className="cafe-table-wrap">
                  <table className="cafe-table">
                    <thead>
                      <tr>
                        <th>Trajectory</th>
                        <th>Rank</th>
                        <th>Gene</th>
                        <th>Score</th>
                        <th>Source</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(driverGenes.items || []).map((item) => (
                        <tr key={`${item.trajectoryId}-${item.rank}-${item.gene}`}>
                          <td>{item.trajectoryId}</td>
                          <td>{item.rank}</td>
                          <td>{item.gene}</td>
                          <td>{formatMetricValue(item.score)}</td>
                          <td>{item.sourceKey}</td>
                          <td>
                            <button
                              type="button"
                              className="cafe-chip-btn"
                              onClick={() => handleAddGene(item.gene)}
                            >
                              Plot Trend
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeSubModule === "trends" && (
          <div className="cafe-card">
            <h4>Gene Trends</h4>
            <div className="cafe-explorer-toolbar">
              <div className="cafe-field">
                <label htmlFor="explorer-gene-query">Search gene</label>
                <input
                  id="explorer-gene-query"
                  type="text"
                  value={geneQueryInput}
                  onChange={(e) => this.setState({ geneQueryInput: e.target.value })}
                  placeholder="e.g. GATA3"
                />
              </div>
              <div className="cafe-form-actions">
                <button type="button" className="cafe-btn" onClick={handleGeneSearch}>
                  Search
                </button>
                <button type="button" className="cafe-btn" onClick={handleClearSearch}>
                  Clear Search
                </button>
              </div>
            </div>
            <div className="cafe-data-section">
              <div className="cafe-data-subtitle">Selected genes</div>
              {!selectedGenes.length ? (
                <div className="cafe-note">
                  No genes selected. Pick from driver genes or search for a marker.
                </div>
              ) : (
                <div className="cafe-key-list">
                  {selectedGenes.map((gene) => (
                    <button
                      key={gene}
                      type="button"
                      className="cafe-key-pill cafe-gene-pill is-active"
                      onClick={() => handleRemoveGene(gene)}
                    >
                      {gene} ×
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="cafe-data-section">
              <div className="cafe-data-subtitle">Search matches</div>
              {!geneSelection.matches?.length ? (
                <div className="cafe-note">{geneSelection.message || "No search results."}</div>
              ) : (
                <div className="cafe-key-list">
                  {geneSelection.matches.map((gene) => {
                    const selected = selectedGenes.includes(gene);
                    return (
                      <button
                        key={gene}
                        type="button"
                        className={`cafe-key-pill cafe-gene-pill ${selected ? "is-active" : ""}`}
                        onClick={() => (selected ? handleRemoveGene(gene) : handleAddGene(gene))}
                      >
                        {selected ? `${gene} ✓` : gene}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="cafe-switch-row" style={{ marginBottom: "12px" }}>
              <span className="cafe-note">Trend scale:</span>
              {["raw", "normalized"].map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`cafe-chip-btn ${trendScale === s ? "is-active" : ""}`}
                  onClick={() => this.setState({ trendScale: s })}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            {!geneTrends.available ? (
              <div className="cafe-note">
                {geneTrends.message || "No normalized gene trend series are available yet."}
              </div>
            ) : (
              <div>
                <div className="cafe-data-section">
                  <div className="cafe-data-subtitle">Comparison View</div>
                  <MultiTrendChart seriesList={geneTrends.series || []} scaleMode={trendScale} />
                </div>
                <div className="cafe-explorer-trend-grid">
                  {(geneTrends.series || []).map((series) => (
                    <div
                      key={`${series.trajectoryId}-${series.gene}-${series.lineage}`}
                      className="cafe-explorer-trend-card"
                    >
                      <div className="cafe-method-title">{series.gene}</div>
                      <div className="cafe-note">
                        {series.trajectoryId}
                        {series.lineage ? ` | ${series.lineage}` : ""}
                        {series.sourceKey ? ` | ${series.sourceKey}` : ""}
                      </div>
                      <Sparkline
                        points={
                          trendScale === "normalized"
                            ? normalizeTrendPoints(series.points || [])
                            : series.points || []
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeSubModule === "integrations" && (
          <div className="cafe-explorer-integration-grid">
            {integrations.map((item) => (
              <div key={item.key} className="cafe-card cafe-explorer-integration-card">
                <div className="cafe-method-header">
                  <div className="cafe-method-title">{item.label}</div>
                  <span
                    className={`cafe-status-badge ${item.enabled ? "is-succeeded" : "is-unknown"}`}
                  >
                    {item.enabled ? "ready" : "unavailable"}
                  </span>
                </div>
                {item.enabled && (
                  <div className="cafe-note" style={{ marginTop: "8px" }}>
                    Items: {item.itemCount ?? "n/a"}
                    {item.source ? ` | Source: ${item.source}` : ""}
                  </div>
                )}
                <div className="cafe-note" style={{ marginTop: "8px" }}>
                  {item.message}
                </div>
                <IntegrationPreview item={item} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
}
