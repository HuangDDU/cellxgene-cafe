import React from "react";
import { connect } from "react-redux";

import { fetchDataSummary, fetchCafeCache, importTrajectory } from "../../lib/api";

function formatTime(ts) {
  if (!ts) return "n/a";
  return new Date(ts * 1000).toLocaleString();
}

function CollapsibleCard({ title, defaultOpen, badge, children }) {
  const [open, setOpen] = React.useState(defaultOpen !== false);
  return (
    <div className="cafe-card">
      <div className="cafe-card-header" onClick={() => setOpen(!open)}>
        <span className="cafe-card-chevron">{open ? "▾" : "▸"}</span>
        <h4>{title}</h4>
        {badge ? <span className="cafe-card-badge">{badge}</span> : null}
      </div>
      {open && <div className="cafe-card-body">{children}</div>}
    </div>
  );
}

const Info = ({ label, value }) => (
  <div className="cafe-info-item">
    <div className="cafe-info-label">{label}</div>
    <div className="cafe-info-value">{value ?? "n/a"}</div>
  </div>
);

class Data extends React.Component {
  constructor(props) {
    super(props);
    this.state = { summary: null, loading: true, error: "", cacheData: null, cacheLoading: false, importMsg: "" };
    this._cancelled = false;
  }

  componentDidMount() {
    this._loadSummary();
    this._loadCache();
  }
  componentWillUnmount() { this._cancelled = false; }

  async _loadSummary() {
    this.setState({ loading: true, error: "" });
    try {
      const summary = await fetchDataSummary();
      if (!this._cancelled) this.setState({ summary, loading: false });
    } catch (err) {
      if (!this._cancelled) this.setState({ error: err?.message || "Failed", loading: false });
    }
  }
  async _loadCache() {
    this.setState({ cacheLoading: true });
    try {
      const data = await fetchCafeCache();
      if (!this._cancelled) this.setState({ cacheData: data, cacheLoading: false });
    } catch { if (!this._cancelled) this.setState({ cacheLoading: false }); }
  }
  _handleImport = async (name, importAll) => {
    this.setState({ importMsg: "" });
    try {
      const result = await importTrajectory(name, importAll);
      if (!this._cancelled) {
        this.setState({ importMsg: `Imported ${result.imported || 0} trajectory files` });
        this._loadCache(); this._loadSummary();
      }
    } catch (err) {
      if (!this._cancelled) this.setState({ importMsg: `Import failed: ${err?.message}` });
    }
  };

  render() {
    const { summary, loading, error, cacheData, cacheLoading, importMsg } = this.state;
    if (loading) return <div className="cafe-loading">Loading dataset summary...</div>;
    if (error) return <div className="cafe-error">{error}</div>;

    const dataset = summary?.dataset || {};
    const fateAnnData = summary?.fateAnnData || {};
    const priorInfo = fateAnnData.priorInformation || {};
    const trajectories = summary?.trajectories || [];
    const exportsInfo = summary?.exports || {};
    const embeddings = summary?.embeddings || {};
    const colorMappings = summary?.colorMappings || [];
    const source = summary?.source || {};
    const hasPriorInfo = priorInfo && Object.keys(priorInfo).length > 0;

    return (
      <div>
        <CollapsibleCard title="Prior Knowledge" defaultOpen={hasPriorInfo} badge={hasPriorInfo ? "fate-specific" : null}>
          {!hasPriorInfo ? <div className="cafe-note">No prior knowledge recorded.</div>
            : <pre className="cafe-json-block">{JSON.stringify(priorInfo, null, 2)}</pre>}
        </CollapsibleCard>

        <CollapsibleCard title="Trajectory History" defaultOpen badge={`${trajectories.length} trajectories`}>
          {!trajectories.length ? <div className="cafe-note">No trajectory history available.</div> : (<>
            <div className="cafe-switch-row" style={{ marginBottom: 10 }}>
              <a className="cafe-btn cafe-btn-primary" href={exportsInfo.h5adUrl || "#"}>Export H5AD</a>
              <a className="cafe-btn cafe-btn-primary" href={exportsInfo.trajectoryPackageUrl || "#"}>Export Trajectory Package</a>
            </div>
            <div className="cafe-table-wrap"><table className="cafe-table">
              <thead><tr><th>ID</th><th>Wrapper</th><th>Layouts</th><th>Milestones</th><th>Edges</th><th>Waypoints</th><th>Metrics</th><th>Resource</th></tr></thead>
              <tbody>{trajectories.map((traj) => (<tr key={traj.id}>
                <td>{traj.displayName || traj.id}</td><td>{traj.wrapperType || "n/a"}</td><td>{traj.layoutNames?.join(", ") || "n/a"}</td>
                <td>{traj.milestoneCount ?? 0}</td><td>{traj.edgeCount ?? 0}</td><td>{traj.waypointCount ?? 0}</td>
                <td>{traj.metricKeys?.length ?? 0}</td>
                <td>{traj.resourceUsage ? Object.entries(traj.resourceUsage).map(([k, v]) => `${k}: ${v}`).join(" | ") : "n/a"}</td>
              </tr>))}</tbody>
            </table></div>
          </>)}
        </CollapsibleCard>

        <CollapsibleCard title="Cafe Cache" defaultOpen={!!cacheData?.cacheDir} badge={cacheLoading ? "..." : cacheData?.cacheDir ? "active" : "none"}>
          {importMsg && <div className={importMsg.startsWith("Import failed") ? "cafe-error" : "cafe-success"} style={{ marginBottom: 10 }}>{importMsg}</div>}
          {!cacheData ? <div className="cafe-note">{cacheLoading ? "Loading..." : "Error loading cache."}</div>
          : !cacheData.cacheDir ? <div className="cafe-note">{cacheData.message || "No cafe cache directory found. Set CAFE_RESULT_DIR in .env or compute trajectories first."}</div>
          : (<div>
            <div className="cafe-note" style={{ marginBottom: 8 }}>Path: {cacheData.cacheDir}</div>
            <div className="cafe-info-grid" style={{ marginBottom: 10 }}>
              {(cacheData.subdirs && Object.entries(cacheData.subdirs).map(([k, v]) => (
                <Info key={k} label={k} value={`${v.length} files`} />
              )))}
            </div>
            {/* Trajectory History import */}
            {(cacheData.trajFiles && cacheData.trajFiles.length > 0) && (<div style={{ marginTop: 10 }}>
              <div className="cafe-data-subtitle">Trajectory History (.pkl)</div>
              <div className="cafe-switch-row" style={{ marginBottom: 8 }}>
                <button type="button" className="cafe-btn cafe-btn-primary"
                  onClick={() => this._handleImport("", true)}>Import All</button>
              </div>
              <div className="cafe-table-wrap"><table className="cafe-table">
                <thead><tr><th>File</th><th>Status</th><th></th></tr></thead>
                <tbody>{(cacheData.trajFiles || []).map((f) => {
                  const imported = (cacheData.imported || []).some((n) => f.name.includes(n) || n.includes(f.name.replace(".pkl", "")));
                  return (<tr key={f.name}>
                    <td>{f.name}</td>
                    <td>{imported ? <span className="cafe-status-badge is-succeeded">imported</span> : <span className="cafe-status-badge is-unknown">pending</span>}</td>
                    <td><button type="button" className="cafe-btn" disabled={imported} onClick={() => this._handleImport(f.name, false)}>{imported ? "Imported" : "Import"}</button></td>
                  </tr>);
                })}</tbody>
              </table></div>
            </div>)}
          </div>)}
        </CollapsibleCard>

        <CollapsibleCard title="Model" defaultOpen={false}>
          <div className="cafe-info-grid">
            <Info label="Dataset" value={dataset.name} />
            <Info label="Shape" value={`${dataset?.shape?.nObs || 0} obs × ${dataset?.shape?.nVars || 0} vars`} />
            <Info label="Matrix" value={`${dataset?.matrix?.dtype || "unknown"}${dataset?.matrix?.sparse ? " | sparse" : ""}`} />
            <Info label="Default Embedding" value={embeddings.default} />
            <Info label="Current Model" value={fateAnnData.modelName} />
          </div>
        </CollapsibleCard>

        <CollapsibleCard title="Embeddings" defaultOpen={false}>
          <div className="cafe-data-section"><div className="cafe-data-subtitle">AnnData obsm basis</div>
            <div className="cafe-key-list">{(embeddings.available || []).map((item) => <span key={item} className="cafe-key-pill">{item}</span>)}</div>
          </div>
          <div className="cafe-data-section"><div className="cafe-data-subtitle">Trajectory layout basis</div>
            <div className="cafe-key-list">{(embeddings.trajectoryLayouts || []).map((item) => <span key={item} className="cafe-key-pill">{item}</span>)}</div>
          </div>
        </CollapsibleCard>

        <CollapsibleCard title="Color Mappings" defaultOpen={false}>
          {!colorMappings.length ? <div className="cafe-note">No color mappings found.</div>
            : <div className="cafe-color-grid">{colorMappings.map((m) => (<div key={m.key} className="cafe-color-card">
              <div className="cafe-color-card-head"><div className="cafe-color-key">{m.key}</div><div className="cafe-note">{m.kind} | {m.size} items</div></div>
              <div className="cafe-color-swatch-list">{(m.items || []).map((item) => (<div key={`${m.key}-${item.label}`} className="cafe-color-swatch-item">
                <span className="cafe-color-swatch" style={{ background: item.color }} /><span className="cafe-color-label">{item.label}</span>
              </div>))}</div>
            </div>))}</div>}
        </CollapsibleCard>

        <CollapsibleCard title="Source" defaultOpen={false}>
          <div className="cafe-info-grid">
            <Info label="Title" value={source.title} /><Info label="Engine" value={source.engine} />
            <Info label="Dataset Path" value={source.datasetPath} /><Info label="Dataset File" value={source.datasetFileName} />
          </div>
        </CollapsibleCard>
      </div>
    );
  }
}

export default connect()(Data);
