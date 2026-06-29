import React from "react";

import { CardSection } from "../common";

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "n/a";
    return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(3);
  }
  return String(value);
}

function normalizeTrendPoints(points) {
  if (!points?.length) return [];
  const ys = points.map((p) => Number(p.y));
  const minY = Math.min(...ys);
  const span = Math.max(...ys) - minY || 1;
  return points.map((p) => ({ x: Number(p.x), y: (Number(p.y) - minY) / span }));
}

function Sparkline({ points }) {
  if (!points?.length) return <div className="cafe-note">No points.</div>;
  const W = 220;
  const H = 80;
  const xs = points.map((p) => Number(p.x));
  const ys = points.map((p) => Number(p.y));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const xSpan = maxX - minX || 1;
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const ySpan = maxY - minY || 1;
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

function MultiTrendChart({ seriesList, scaleMode }) {
  const palette = ["#2f6f9f", "#d67344", "#4d8f4a", "#8b5fbf", "#c2577b", "#4f8f99"];
  const prepared = (seriesList || [])
    .filter((s) => s.points?.length)
    .map((s, i) => ({
      ...s,
      color: palette[i % palette.length],
      points: scaleMode === "normalized" ? normalizeTrendPoints(s.points) : s.points,
    }));
  if (!prepared.length) return <div className="cafe-note">No comparison series.</div>;

  const W = 520;
  const H = 220;
  const P = 20;
  const xs = prepared.flatMap((s) => s.points.map((p) => Number(p.x)));
  const ys = prepared.flatMap((s) => s.points.map((p) => Number(p.y)));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const xSpan = maxX - minX || 1;
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const ySpan = maxY - minY || 1;

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

export default function DriverGene({
  driverGenes,
  geneSelection,
  geneTrends,
  selectedGenes,
  geneQueryInput,
  trendScale,
  onGeneQueryInputChange,
  onGeneSearch,
  onClearSearch,
  onAddGene,
  onRemoveGene,
  onTrendScaleChange,
}) {
  const series = geneTrends.series || [];
  return (
    <CardSection
      title="Driver Gene"
      defaultOpen={false}
      badge={`${driverGenes.items?.length || 0} genes / ${selectedGenes.length} selected`}
    >
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
                      <button type="button" className="cafe-chip-btn" onClick={() => onAddGene(item.gene)}>
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

      <div className="cafe-data-section">
        <div className="cafe-data-subtitle">Gene Trends</div>
        <div className="cafe-explorer-toolbar">
          <div className="cafe-field">
            <label htmlFor="explorer-gene-query">Search gene</label>
            <input
              id="explorer-gene-query"
              type="text"
              value={geneQueryInput}
              onChange={(e) => onGeneQueryInputChange(e.target.value)}
              placeholder="e.g. GATA3"
            />
          </div>
          <div className="cafe-form-actions">
            <button type="button" className="cafe-btn" onClick={onGeneSearch}>
              Search
            </button>
            <button type="button" className="cafe-btn" onClick={onClearSearch}>
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
                  onClick={() => onRemoveGene(gene)}
                >
                  {gene} x
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
                    onClick={() => (selected ? onRemoveGene(gene) : onAddGene(gene))}
                  >
                    {selected ? `${gene} selected` : gene}
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
              onClick={() => onTrendScaleChange(s)}
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
              <div className="cafe-data-subtitle">Trend Overview</div>
              <MultiTrendChart seriesList={series} scaleMode={trendScale} />
            </div>
            <div className="cafe-explorer-trend-grid">
              {series.map((item) => (
                <div key={`${item.trajectoryId}-${item.gene}-${item.lineage}`} className="cafe-explorer-trend-card">
                  <div className="cafe-method-title">{item.gene}</div>
                  <div className="cafe-note">
                    {item.trajectoryId}
                    {item.lineage ? ` | ${item.lineage}` : ""}
                    {item.sourceKey ? ` | ${item.sourceKey}` : ""}
                  </div>
                  <Sparkline
                    points={trendScale === "normalized" ? normalizeTrendPoints(item.points || []) : item.points || []}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </CardSection>
  );
}
