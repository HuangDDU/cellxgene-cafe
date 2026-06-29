import React from "react";

import { CardSection, EmptyState, InfoGrid, StatusBadge } from "../common";
import { fetchDataSummary, fetchCafeCache, importTrajectory } from "../../lib/api";

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
  componentWillUnmount() { this._cancelled = true; }

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
        <CardSection title="Prior Knowledge" defaultOpen={hasPriorInfo} badge={hasPriorInfo ? "fate-specific" : null}>
          {!hasPriorInfo ? <EmptyState>No prior knowledge recorded.</EmptyState>
            : <pre className="cafe-json-block">{JSON.stringify(priorInfo, null, 2)}</pre>}
        </CardSection>

        <CardSection title="Trajectory History" defaultOpen badge={`${trajectories.length} trajectories`}>
          {!trajectories.length ? <EmptyState>No trajectory history available.</EmptyState> : (<>
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
        </CardSection>

        <CardSection title="Cafe Cache" defaultOpen={!!cacheData?.cacheDir} badge={cacheLoading ? "..." : cacheData?.cacheDir ? "active" : "none"}>
          {importMsg && <div className={importMsg.startsWith("Import failed") ? "cafe-error" : "cafe-success"} style={{ marginBottom: 10 }}>{importMsg}</div>}
          {!cacheData ? <EmptyState>{cacheLoading ? "Loading..." : "Error loading cache."}</EmptyState>
          : !cacheData.cacheDir ? <EmptyState>{cacheData.message || "No cafe cache directory found. Set CAFE_RESULT_DIR in .env or compute trajectories first."}</EmptyState>
          : (<div>
            <div className="cafe-note" style={{ marginBottom: 8 }}>Path: {cacheData.cacheDir}</div>
            <InfoGrid
              className="cafe-cache-grid"
              items={Object.entries(cacheData.subdirs || {}).map(([key, value]) => ({
                label: key,
                value: `${value.length} files`,
              }))}
            />
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
                    <td>{imported ? <StatusBadge status="imported" /> : <StatusBadge status="pending" />}</td>
                    <td><button type="button" className="cafe-btn" disabled={imported} onClick={() => this._handleImport(f.name, false)}>{imported ? "Imported" : "Import"}</button></td>
                  </tr>);
                })}</tbody>
              </table></div>
            </div>)}
          </div>)}
        </CardSection>

        <CardSection title="Model" defaultOpen={false}>
          <InfoGrid items={[
            { label: "Dataset", value: dataset.name },
            { label: "Shape", value: `${dataset?.shape?.nObs || 0} obs x ${dataset?.shape?.nVars || 0} vars` },
            { label: "Matrix", value: `${dataset?.matrix?.dtype || "unknown"}${dataset?.matrix?.sparse ? " | sparse" : ""}` },
            { label: "Default Embedding", value: embeddings.default },
            { label: "Current Model", value: fateAnnData.modelName },
          ]} />
        </CardSection>

        <CardSection title="Embeddings" defaultOpen={false}>
          <div className="cafe-data-section"><div className="cafe-data-subtitle">AnnData obsm basis</div>
            <div className="cafe-key-list">{(embeddings.available || []).map((item) => <span key={item} className="cafe-key-pill">{item}</span>)}</div>
          </div>
          <div className="cafe-data-section"><div className="cafe-data-subtitle">Trajectory layout basis</div>
            <div className="cafe-key-list">{(embeddings.trajectoryLayouts || []).map((item) => <span key={item} className="cafe-key-pill">{item}</span>)}</div>
          </div>
        </CardSection>

        <CardSection title="Color Mappings" defaultOpen={false}>
          {!colorMappings.length ? <EmptyState>No color mappings found.</EmptyState>
            : <div className="cafe-color-grid">{colorMappings.map((m) => (<div key={m.key} className="cafe-color-card">
              <div className="cafe-color-card-head"><div className="cafe-color-key">{m.key}</div><div className="cafe-note">{m.kind} | {m.size} items</div></div>
              <div className="cafe-color-swatch-list">{(m.items || []).map((item) => (<div key={`${m.key}-${item.label}`} className="cafe-color-swatch-item">
                <span className="cafe-color-swatch" style={{ background: item.color }} /><span className="cafe-color-label">{item.label}</span>
              </div>))}</div>
            </div>))}</div>}
        </CardSection>

        <CardSection title="Source" defaultOpen={false}>
          <InfoGrid items={[
            { label: "Title", value: source.title },
            { label: "Engine", value: source.engine },
            { label: "Dataset Path", value: source.datasetPath },
            { label: "Dataset File", value: source.datasetFileName },
          ]} />
        </CardSection>
      </div>
    );
  }
}

export default Data;
