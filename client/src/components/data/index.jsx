import React from "react";

import { fetchDataSummary } from "../../lib/api";

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatResourceUsage(resourceUsage) {
  if (!resourceUsage || !Object.keys(resourceUsage).length) return "n/a";
  return Object.entries(resourceUsage).map(([k, v]) => `${k}: ${v}`).join(" | ");
}

function KeyList({ items }) {
  if (!items?.length) return <div className="cafe-note">No items.</div>;
  return (
    <div className="cafe-key-list">
      {items.map((item) => <span key={item} className="cafe-key-pill">{item}</span>)}
    </div>
  );
}

function InfoGrid({ items }) {
  return (
    <div className="cafe-info-grid">
      {items.map(({ label, value }) => (
        <div key={label} className="cafe-info-item">
          <div className="cafe-info-label">{label}</div>
          <div className="cafe-info-value">{value || "n/a"}</div>
        </div>
      ))}
    </div>
  );
}

export default class Data extends React.Component {
  constructor(props) {
    super(props);
    this.state = { summary: null, loading: true, error: "" };
    this._cancelled = false;
  }

  componentDidMount() { this._loadSummary(); }
  componentWillUnmount() { this._cancelled = true; }

  async _loadSummary() {
    this.setState({ loading: true, error: "" });
    try {
      const nextSummary = await fetchDataSummary();
      if (!this._cancelled) this.setState({ summary: nextSummary, loading: false });
    } catch (err) {
      if (!this._cancelled) this.setState({ error: err?.message || "Failed to load Data module summary", loading: false });
    }
  }

  render() {
    const { summary, loading, error } = this.state;
    if (loading) return <div className="cafe-loading">Loading dataset summary...</div>;
    if (error) return <div className="cafe-error">{error}</div>;

    const dataset = summary?.dataset || {};
    const fateAnnData = summary?.fateAnnData || {};
    const structure = fateAnnData.structure || {};
    const embeddings = summary?.embeddings || {};
    const source = summary?.source || {};
    const exportsInfo = summary?.exports || {};
    const trajectories = summary?.trajectories || [];
    const colorMappings = summary?.colorMappings || [];

    const structRows = [
      ["obs columns", structure.obsColumns],
      ["var columns", structure.varColumns],
      ["layers", structure.layers],
      ["obsm", structure.obsm],
      ["obsp", structure.obsp],
      ["varm", structure.varm],
      ["uns keys", structure.unsKeys],
      ["cafe keys", structure.cafeKeys],
    ];

    return (
      <div>
        <div className="cafe-card">
          <h4>Overview</h4>
          <InfoGrid items={[
            { label: "Dataset", value: dataset.name },
            { label: "Dataset ID", value: dataset.id },
            { label: "Shape", value: `${dataset?.shape?.nObs || 0} obs x ${dataset?.shape?.nVars || 0} vars` },
            { label: "Matrix", value: `${dataset?.matrix?.dtype || "unknown"}${dataset?.matrix?.sparse ? " | sparse" : " | dense"}` },
            { label: "Default Embedding", value: embeddings.default },
            { label: "Current Model", value: fateAnnData.modelName },
          ]} />
          <div className="cafe-switch-row" style={{ marginTop: "10px" }}>
            <a className="cafe-btn cafe-link-btn" href={exportsInfo.h5adUrl || "#"}>Export H5AD</a>
            <a className="cafe-btn cafe-link-btn" href={exportsInfo.trajectoryPackageUrl || "#"}>Export Trajectory Package</a>
          </div>
        </div>

        <div className="cafe-card">
          <h4>FateAnnData Structure</h4>
          <div className="cafe-data-section">
            <div className="cafe-data-subtitle">prior_information</div>
            <pre className="cafe-json-block">{JSON.stringify(fateAnnData.priorInformation || {}, null, 2)}</pre>
          </div>
          <div className="cafe-data-structure-grid">
            {structRows.map(([label, items]) => (
              <div key={label}>
                <div className="cafe-data-subtitle">{label}</div>
                <KeyList items={items} />
              </div>
            ))}
          </div>
        </div>

        <div className="cafe-card">
          <h4>Trajectories</h4>
          {!trajectories.length ? (
            <div className="cafe-note">No trajectory history is available for the current dataset.</div>
          ) : (
            <div className="cafe-table-wrap">
              <table className="cafe-table">
                <thead>
                  <tr>
                    <th>ID</th><th>Wrapper</th><th>Layouts</th><th>Milestones</th>
                    <th>Edges</th><th>Waypoints</th><th>Metrics</th><th>Resource</th>
                  </tr>
                </thead>
                <tbody>
                  {trajectories.map((traj) => (
                    <tr key={traj.id}>
                      <td>{traj.displayName || traj.id}</td>
                      <td>{traj.wrapperType || "n/a"}</td>
                      <td>{traj.layoutNames?.join(", ") || "n/a"}</td>
                      <td>{traj.milestoneCount ?? 0}</td>
                      <td>{traj.edgeCount ?? 0}</td>
                      <td>{traj.waypointCount ?? 0}</td>
                      <td>{traj.metricKeys?.length ?? 0}</td>
                      <td>{formatResourceUsage(traj.resourceUsage)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="cafe-card">
          <h4>Embeddings</h4>
          <div className="cafe-data-section">
            <div className="cafe-data-subtitle">AnnData obsm basis</div>
            <KeyList items={embeddings.available} />
          </div>
          <div className="cafe-data-section">
            <div className="cafe-data-subtitle">Trajectory layout basis</div>
            <KeyList items={embeddings.trajectoryLayouts} />
          </div>
        </div>

        <div className="cafe-card">
          <h4>Color Mappings</h4>
          {!colorMappings.length ? (
            <div className="cafe-note">No color mappings were found in the current dataset summary.</div>
          ) : (
            <div className="cafe-color-grid">
              {colorMappings.map((mapping) => (
                <div key={mapping.key} className="cafe-color-card">
                  <div className="cafe-color-card-head">
                    <div className="cafe-color-key">{mapping.key}</div>
                    <div className="cafe-note">{mapping.kind} | {mapping.size} items</div>
                  </div>
                  {!mapping.items?.length ? (
                    <div className="cafe-note">No sampled colors.</div>
                  ) : (
                    <div className="cafe-color-swatch-list">
                      {mapping.items.map((item) => (
                        <div key={`${mapping.key}-${item.label}`} className="cafe-color-swatch-item">
                          <span className="cafe-color-swatch" style={{ background: item.color }} />
                          <span className="cafe-color-label">{item.label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="cafe-card">
          <h4>Source</h4>
          <InfoGrid items={[
            { label: "Title", value: source.title },
            { label: "Engine", value: source.engine },
            { label: "Dataset Path", value: source.datasetPath },
            { label: "Dataset File", value: source.datasetFileName },
            { label: "Dataset Exists", value: String(source.datasetFileExists) },
            { label: "Dataset Size", value: formatFileSize(source.datasetFileSize) },
            { label: "uns.filename", value: source.unsFilename },
          ]} />
        </div>
      </div>
    );
  }
}
