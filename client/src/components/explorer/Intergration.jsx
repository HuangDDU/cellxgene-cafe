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

function IntegrationPreview({ item }) {
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

export default function Intergration({ integrations }) {
  return (
    <CardSection title="Integration" defaultOpen={false} badge={`${integrations.length} sources`}>
      {!integrations.length ? (
        <div className="cafe-note">No integration results are available yet.</div>
      ) : (
        <div className="cafe-explorer-integration-grid">
          {integrations.map((item) => (
            <CardSection
              key={item.key}
              title={item.label}
              defaultOpen={false}
              badge={item.enabled ? "ready" : "unavailable"}
              className="cafe-explorer-integration-card"
            >
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
            </CardSection>
          ))}
        </div>
      )}
    </CardSection>
  );
}
