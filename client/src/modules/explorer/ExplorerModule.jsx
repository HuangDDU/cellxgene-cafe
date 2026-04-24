import React, { useEffect, useMemo, useState } from "react";

import { fetchExplorerSummary } from "../../lib/api";

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return "n/a";
    }
    return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(3);
  }
  return String(value);
}

function tryNumeric(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") {
    return { ok: false, value: 0 };
  }
  const nextValue = Number(value);
  if (Number.isFinite(nextValue)) {
    return { ok: true, value: nextValue };
  }
  return { ok: false, value: 0 };
}

function InfoGrid({ items }) {
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

function MetricBarList({ items }) {
  if (!items?.length) {
    return <div className="cafe-note">No numeric rankings.</div>;
  }
  return (
    <div className="cafe-bar-list">
      {items.map((item) => (
        <div key={`${item.id}-${item.rank}`} className="cafe-bar-row">
          <div className="cafe-bar-label">
            <span className="cafe-bar-rank">#{item.rank}</span>
            <span>{item.id}</span>
          </div>
          <div className="cafe-bar-track">
            <div className="cafe-bar-fill" style={{ width: `${Math.max(item.normalized * 100, 6)}%` }} />
          </div>
          <div className="cafe-bar-value">{formatMetricValue(item.value)}</div>
        </div>
      ))}
    </div>
  );
}

function IntegrationPreview({ item }) {
  const rows = item.items || [];
  if (!rows.length) {
    return null;
  }

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
            {rows.slice(0, 8).map((row) => (
              <tr key={`${row.source}-${row.target}`}>
                <td>{row.source}</td>
                <td>{row.target}</td>
                <td>{formatMetricValue(row.weight)}</td>
                <td>{row.sign}</td>
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
          {rows.slice(0, 8).map((row) => (
            <tr key={`${item.key}-${row.term}`}>
              <td>{row.term}</td>
              <td>{row.overlap}</td>
              <td>{formatMetricValue(row.score)}</td>
              <td>{row.genes || "n/a"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sparkline({ points }) {
  if (!points?.length) {
    return <div className="cafe-note">No points.</div>;
  }

  const width = 220;
  const height = 80;
  const xs = points.map((point) => Number(point.x));
  const ys = points.map((point) => Number(point.y));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;

  const path = points
    .map((point, index) => {
      const x = ((Number(point.x) - minX) / xSpan) * (width - 12) + 6;
      const y = height - (((Number(point.y) - minY) / ySpan) * (height - 12) + 6);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg className="cafe-sparkline-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Gene trend preview">
      <path d={path} />
    </svg>
  );
}

function normalizeTrendPoints(points) {
  if (!points?.length) {
    return [];
  }
  const ys = points.map((point) => Number(point.y));
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const span = maxY - minY || 1;
  return points.map((point) => ({
    x: Number(point.x),
    y: span === 0 ? 1 : (Number(point.y) - minY) / span,
  }));
}

function MultiTrendChart({ seriesList, scaleMode = "raw" }) {
  const palette = ["#2f6f9f", "#d67344", "#4d8f4a", "#8b5fbf", "#c2577b", "#4f8f99"];
  const preparedSeries = (seriesList || [])
    .filter((series) => series.points?.length)
    .map((series, index) => ({
      ...series,
      color: palette[index % palette.length],
      points: scaleMode === "normalized" ? normalizeTrendPoints(series.points) : series.points,
    }));

  if (!preparedSeries.length) {
    return <div className="cafe-note">No comparison series.</div>;
  }

  const width = 520;
  const height = 220;
  const padding = 20;
  const xs = preparedSeries.flatMap((series) => series.points.map((point) => Number(point.x)));
  const ys = preparedSeries.flatMap((series) => series.points.map((point) => Number(point.y)));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;

  return (
    <div className="cafe-trend-compare-wrap">
      <svg className="cafe-trend-compare-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Gene trend comparison chart">
        <rect x="0" y="0" width={width} height={height} rx="8" ry="8" />
        {preparedSeries.map((series) => {
          const path = series.points
            .map((point, index) => {
              const x = ((Number(point.x) - minX) / xSpan) * (width - padding * 2) + padding;
              const y = height - (((Number(point.y) - minY) / ySpan) * (height - padding * 2) + padding);
              return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
            })
            .join(" ");
          return <path key={`${series.trajectoryId}-${series.gene}`} d={path} style={{ stroke: series.color }} />;
        })}
      </svg>
      <div className="cafe-trend-legend">
        {preparedSeries.map((series) => (
          <div key={`${series.trajectoryId}-${series.gene}`} className="cafe-trend-legend-item">
            <span className="cafe-trend-legend-swatch" style={{ background: series.color }} />
            <span>{series.gene}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ExplorerModule({ context, refreshToken = 0 }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSubModule, setActiveSubModule] = useState("benchmark");
  const [sortMetric, setSortMetric] = useState("");
  const [sortDirection, setSortDirection] = useState("desc");
  const [searchText, setSearchText] = useState("");
  const [geneQueryInput, setGeneQueryInput] = useState("");
  const [geneQuery, setGeneQuery] = useState("");
  const [selectedGenes, setSelectedGenes] = useState([]);
  const [trendScale, setTrendScale] = useState("raw");

  useEffect(() => {
    let cancelled = false;

    async function loadSummary() {
      setLoading(true);
      setError("");
      try {
        const nextSummary = await fetchExplorerSummary({
          trajectory: context?.current?.trajectory || "",
          layout: context?.current?.layout || "",
          geneQuery,
          genes: selectedGenes.join(","),
        });
        if (cancelled) {
          return;
        }
        setSummary(nextSummary);
        const nextMetricKeys = nextSummary?.benchmark?.metricKeys || [];
        if ((!sortMetric || !nextMetricKeys.includes(sortMetric)) && nextMetricKeys.length) {
          setSortMetric(nextMetricKeys[0]);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Failed to load Explorer summary");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSummary();
    return () => {
      cancelled = true;
    };
  }, [context?.current?.trajectory, context?.current?.layout, refreshToken, geneQuery, selectedGenes]);

  const benchmarkRows = summary?.benchmark?.rows || [];
  const metricKeys = summary?.benchmark?.metricKeys || [];
  const comparisonMetrics = summary?.metricComparison?.metrics || [];
  const driverGenes = summary?.driverGenes || {};
  const geneTrends = summary?.geneTrends || {};
  const geneSelection = summary?.geneSelection || {};
  const integrations = summary?.integrations || [];
  const currentTrajectory = summary?.currentTrajectory || null;
  const overallRanking = summary?.metricComparison?.overallRanking || [];

  const visibleBenchmarkRows = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    const filteredRows = benchmarkRows.filter((row) => {
      if (!query) {
        return true;
      }
      return String(row.id || "")
        .toLowerCase()
        .includes(query);
    });

    const nextRows = [...filteredRows];
    nextRows.sort((leftRow, rightRow) => {
      const sortKey = sortMetric || "id";
      if (sortKey === "id") {
        return sortDirection === "asc"
          ? String(leftRow.id || "").localeCompare(String(rightRow.id || ""))
          : String(rightRow.id || "").localeCompare(String(leftRow.id || ""));
      }

      const leftNumeric = tryNumeric(leftRow[sortKey]);
      const rightNumeric = tryNumeric(rightRow[sortKey]);
      if (leftNumeric.ok && rightNumeric.ok) {
        return sortDirection === "asc"
          ? leftNumeric.value - rightNumeric.value
          : rightNumeric.value - leftNumeric.value;
      }

      return sortDirection === "asc"
        ? String(leftRow[sortKey] || "").localeCompare(String(rightRow[sortKey] || ""))
        : String(rightRow[sortKey] || "").localeCompare(String(leftRow[sortKey] || ""));
    });
    return nextRows;
  }, [benchmarkRows, searchText, sortDirection, sortMetric]);

  const onAddSelectedGene = (gene) => {
    const nextGene = String(gene || "").trim();
    if (!nextGene) {
      return;
    }
    setSelectedGenes((prev) => {
      if (prev.includes(nextGene)) {
        return prev;
      }
      return [...prev, nextGene].slice(0, 6);
    });
    setActiveSubModule("trends");
  };

  const onRemoveSelectedGene = (gene) => {
    setSelectedGenes((prev) => prev.filter((item) => item !== gene));
  };

  const onRunGeneSearch = () => {
    setGeneQuery(geneQueryInput.trim());
    setActiveSubModule("trends");
  };

  const onClearGeneSearch = () => {
    setGeneQuery("");
    setGeneQueryInput("");
  };

  if (loading) {
    return <div className="cafe-loading">Loading Explorer summary...</div>;
  }

  if (error) {
    return <div className="cafe-error">{error}</div>;
  }

  return (
    <div>
      <div className="cafe-card">
        <h4>Explorer Overview</h4>
        <InfoGrid
          items={[
            { label: "Dataset", value: summary?.dataset?.name },
            { label: "Current Trajectory", value: currentTrajectory?.id || summary?.selection?.trajectory },
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
          <button
            type="button"
            className={`cafe-chip-btn ${activeSubModule === "benchmark" ? "is-active" : ""}`}
            onClick={() => setActiveSubModule("benchmark")}
          >
            Benchmark
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${activeSubModule === "comparison" ? "is-active" : ""}`}
            onClick={() => setActiveSubModule("comparison")}
          >
            Comparison
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${activeSubModule === "drivers" ? "is-active" : ""}`}
            onClick={() => setActiveSubModule("drivers")}
          >
            Driver Genes
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${activeSubModule === "trends" ? "is-active" : ""}`}
            onClick={() => setActiveSubModule("trends")}
          >
            Gene Trends
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${activeSubModule === "integrations" ? "is-active" : ""}`}
            onClick={() => setActiveSubModule("integrations")}
          >
            Integrations
          </button>
        </div>
      </div>

      {activeSubModule === "benchmark" ? (
        <div className="cafe-card">
          <h4>Trajectory Benchmark</h4>
          {!benchmarkRows.length ? (
            <div className="cafe-note">No benchmark metrics found in current trajectory history.</div>
          ) : (
            <div>
              <div className="cafe-explorer-toolbar">
                <div className="cafe-field">
                  <label htmlFor="explorer-search">Search trajectory</label>
                  <input
                    id="explorer-search"
                    type="text"
                    value={searchText}
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="Filter by trajectory id"
                  />
                </div>
                <div className="cafe-field">
                  <label htmlFor="explorer-sort">Sort by</label>
                  <select id="explorer-sort" value={sortMetric || "id"} onChange={(event) => setSortMetric(event.target.value)}>
                    <option value="id">id</option>
                    {metricKeys.map((key) => (
                      <option key={key} value={key}>
                        {key}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="cafe-field">
                  <label htmlFor="explorer-direction">Direction</label>
                  <select
                    id="explorer-direction"
                    value={sortDirection}
                    onChange={(event) => setSortDirection(event.target.value)}
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
                      {metricKeys.map((key) => (
                        <th key={key}>{key}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleBenchmarkRows.map((row) => (
                      <tr key={row.id}>
                        <td>{row.id}</td>
                        {metricKeys.map((key) => (
                          <td key={`${row.id}-${key}`}>{formatMetricValue(row[key])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {activeSubModule === "comparison" ? (
        <div>
          <div className="cafe-card">
            <h4>Overall Ranking</h4>
            {!overallRanking.length ? (
              <div className="cafe-note">No numeric metrics are available for cross-method ranking.</div>
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
              .filter((metric) => metric.numeric)
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
            {!comparisonMetrics.some((metric) => metric.numeric) ? (
              <div className="cafe-card">
                <div className="cafe-note">No numeric metric comparison is available for the current dataset.</div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {activeSubModule === "drivers" ? (
        <div className="cafe-card">
          <h4>Driver Genes</h4>
          {!driverGenes.available ? (
            <div className="cafe-note">{driverGenes.message || "No normalized driver gene table is available yet."}</div>
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
                          <button type="button" className="cafe-chip-btn" onClick={() => onAddSelectedGene(item.gene)}>
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
      ) : null}

      {activeSubModule === "trends" ? (
        <div className="cafe-card">
          <h4>Gene Trends</h4>
          <div className="cafe-explorer-toolbar">
            <div className="cafe-field">
              <label htmlFor="explorer-gene-query">Search gene</label>
              <input
                id="explorer-gene-query"
                type="text"
                value={geneQueryInput}
                onChange={(event) => setGeneQueryInput(event.target.value)}
                placeholder="e.g. GATA3"
              />
            </div>
            <div className="cafe-form-actions">
              <button type="button" className="cafe-btn" onClick={onRunGeneSearch}>
                Search
              </button>
              <button type="button" className="cafe-btn" onClick={onClearGeneSearch}>
                Clear Search
              </button>
            </div>
          </div>

          <div className="cafe-data-section">
            <div className="cafe-data-subtitle">Selected genes</div>
            {!selectedGenes.length ? (
              <div className="cafe-note">No genes selected. Pick from driver genes or search for a marker.</div>
            ) : (
              <div className="cafe-key-list">
                {selectedGenes.map((gene) => (
                  <button
                    key={gene}
                    type="button"
                    className="cafe-key-pill cafe-gene-pill is-active"
                    onClick={() => onRemoveSelectedGene(gene)}
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
                  const isSelected = selectedGenes.includes(gene);
                  return (
                    <button
                      key={gene}
                      type="button"
                      className={`cafe-key-pill cafe-gene-pill ${isSelected ? "is-active" : ""}`}
                      onClick={() => (isSelected ? onRemoveSelectedGene(gene) : onAddSelectedGene(gene))}
                    >
                      {isSelected ? `${gene} ✓` : gene}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="cafe-switch-row" style={{ marginBottom: "12px" }}>
            <span className="cafe-note">Trend scale:</span>
            <button
              type="button"
              className={`cafe-chip-btn ${trendScale === "raw" ? "is-active" : ""}`}
              onClick={() => setTrendScale("raw")}
            >
              Raw
            </button>
            <button
              type="button"
              className={`cafe-chip-btn ${trendScale === "normalized" ? "is-active" : ""}`}
              onClick={() => setTrendScale("normalized")}
            >
              Normalized
            </button>
          </div>

          {!geneTrends.available ? (
            <div className="cafe-note">{geneTrends.message || "No normalized gene trend series are available yet."}</div>
          ) : (
            <div>
              <div className="cafe-data-section">
                <div className="cafe-data-subtitle">Comparison View</div>
                <MultiTrendChart seriesList={geneTrends.series || []} scaleMode={trendScale} />
              </div>

              <div className="cafe-explorer-trend-grid">
                {(geneTrends.series || []).map((series) => (
                  <div key={`${series.trajectoryId}-${series.gene}-${series.lineage}`} className="cafe-explorer-trend-card">
                    <div className="cafe-method-title">{series.gene}</div>
                    <div className="cafe-note">
                      {series.trajectoryId}
                      {series.lineage ? ` | ${series.lineage}` : ""}
                      {series.sourceKey ? ` | ${series.sourceKey}` : ""}
                    </div>
                    <Sparkline
                      points={trendScale === "normalized" ? normalizeTrendPoints(series.points || []) : series.points || []}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {activeSubModule === "integrations" ? (
        <div className="cafe-explorer-integration-grid">
          {integrations.map((item) => (
            <div key={item.key} className="cafe-card cafe-explorer-integration-card">
              <div className="cafe-method-header">
                <div className="cafe-method-title">{item.label}</div>
                <span className={`cafe-status-badge ${item.enabled ? "is-succeeded" : "is-unknown"}`}>
                  {item.enabled ? "ready" : "unavailable"}
                </span>
              </div>
              {item.enabled ? (
                <div className="cafe-note" style={{ marginTop: "8px" }}>
                  Items: {item.itemCount ?? "n/a"}
                  {item.source ? ` | Source: ${item.source}` : ""}
                </div>
              ) : null}
              <div className="cafe-note" style={{ marginTop: "8px" }}>
                {item.message}
              </div>
              <IntegrationPreview item={item} />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default ExplorerModule;
