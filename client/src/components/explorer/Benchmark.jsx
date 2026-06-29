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

export default function Benchmark({
  metricKeys,
  rows,
  searchText,
  sortMetric,
  sortDirection,
  onSearchTextChange,
  onSortMetricChange,
  onSortDirectionChange,
}) {
  return (
    <CardSection title="Benchmark" defaultOpen badge={`${rows.length} rows`}>
      {!rows.length ? (
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
                onChange={(e) => onSearchTextChange(e.target.value)}
                placeholder="Filter by trajectory id"
              />
            </div>
            <div className="cafe-field">
              <label htmlFor="explorer-sort">Sort by</label>
              <select
                id="explorer-sort"
                value={sortMetric || "id"}
                onChange={(e) => onSortMetricChange(e.target.value)}
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
                onChange={(e) => onSortDirectionChange(e.target.value)}
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
                {rows.map((row) => (
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
    </CardSection>
  );
}
