import React from "react";
import { connect } from "react-redux";

import "./index.css";

function scaleCoords(nodes, width, height, pad) {
  if (!nodes.length) return { sx: (x) => x, sy: (y) => y };
  const xs = nodes.map((n) => Number(n.x || 0)), ys = nodes.map((n) => Number(n.y || 0));
  const minX = Math.min(...xs), maxX = Math.max(...xs), xSpan = (maxX - minX) || 1;
  const minY = Math.min(...ys), maxY = Math.max(...ys), ySpan = (maxY - minY) || 1;
  return { sx: (x) => pad + ((Number(x || 0) - minX) / xSpan) * (width - pad * 2), sy: (y) => height - pad - ((Number(y || 0) - minY) / ySpan) * (height - pad * 2) };
}

function MilestoneSVG({ preview, width, height, nodeSize, edgeWidth }) {
  const nodes = preview?.nodes || [], edges = preview?.edges || [];
  if (!nodes.length) return <div className="cafe-note">No milestone data.</div>;
  const pad = 16, { sx, sy } = scaleCoords(nodes, width, height, pad);
  const nodeById = {}; nodes.forEach((n) => { nodeById[String(n.id)] = n; });
  const r = Math.max(3, 5 * nodeSize);
  return (
    <svg width={width} height={height} style={{ background: "#f8fbff", border: "1px solid #d8e1ec", borderRadius: "4px" }}>
      {edges.map((e) => { const src = nodeById[e.source], tgt = nodeById[e.target]; if (!src || !tgt) return null; return <line key={String(e.id || `${e.source}_${e.target}`)} x1={sx(src.x)} y1={sy(src.y)} x2={sx(tgt.x)} y2={sy(tgt.y)} stroke="#4a6a8a" strokeWidth={Math.max(1, edgeWidth * 1.5)} opacity={0.85} />; })}
      {nodes.map((n) => (<g key={String(n.id)}><circle cx={sx(n.x)} cy={sy(n.y)} r={r} fill={n.color || "#7eb5df"} stroke="#1f3d5d" strokeWidth={1.2} /><text x={sx(n.x) + r + 3} y={sy(n.y) - r - 2} fontSize={Math.max(8, r * 1.6)} fill="#2f4d6f">{n.label || n.id}</text></g>))}
    </svg>
  );
}

function WaypointSVG({ preview, width, height, nodeSize, edgeWidth }) {
  const nodes = preview?.nodes || [], segments = preview?.waypointSegments || {};
  if (!nodes.length && !Object.keys(segments).length) return <div className="cafe-note">No waypoint data.</div>;
  const allPts = nodes.length ? nodes : Object.values(segments).flatMap((pts) => (pts || []));
  const pad = 16, { sx, sy } = scaleCoords(allPts, width, height, pad);
  const r = Math.max(3, 5 * nodeSize), sw = Math.max(1, edgeWidth * 1.2), ms = 0.8;
  return (
    <svg width={width} height={height} style={{ background: "#f8fbff", border: "1px solid #d8e1ec", borderRadius: "4px" }}>
      <defs><marker id="wp-arrow" markerWidth={6 * ms} markerHeight={4 * ms} refX={6 * ms} refY={2 * ms} orient="auto"><path d={`M0,0 L${6 * ms},${2 * ms} L0,${4 * ms} Z`} fill="#333" /></marker></defs>
      {Object.entries(segments).map(([groupId, pts]) => { if (!pts || pts.length < 2) return null; const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(" "), end = pts.length - 1; return (<g key={groupId}><path d={d} fill="none" stroke="#556677" strokeWidth={sw} /><path d={`M ${sx(pts[end].x).toFixed(1)} ${sy(pts[end].y).toFixed(1)} L ${sx(pts[end - 1].x).toFixed(1)} ${sy(pts[end - 1].y).toFixed(1)}`} fill="none" stroke="#333" strokeWidth={sw} markerEnd="url(#wp-arrow)" /></g>); })}
      {nodes.map((n) => (<g key={String(n.id)}><circle cx={sx(n.x)} cy={sy(n.y)} r={r} fill={n.color || "#7eb5df"} stroke="#1f3d5d" strokeWidth={1.2} /><text x={sx(n.x) + r + 3} y={sy(n.y) - r - 2} fontSize={Math.max(8, r * 1.6)} fill="#2f4d6f">{n.label || n.id}</text></g>))}
    </svg>
  );
}

@connect((state) => ({
  preview: state.trajectory?.preview || {},
  trajectoryType: state.trajectory?.trajectoryType || "milestone",
  nodeSize: Number(state.trajectory?.nodeSize ?? 2.5),
  edgeWidth: Number(state.trajectory?.edgeWidth ?? 1),
}))
export default class TrajectoryPreview extends React.Component {
  constructor(props) {
    super(props);
    this.state = { open: true };
  }

  render() {
    const { preview, trajectoryType, nodeSize, edgeWidth } = this.props;
    const { open } = this.state;
    const nodes = preview?.nodes || [], W = 340, H = 280;
    return (
      <div className="cafe-dynamics-preview-panel">
        <button
          type="button"
          className="cafe-dynamics-panel-header"
          aria-expanded={open}
          onClick={() => this.setState((state) => ({ open: !state.open }))}
        >
          <span className="cafe-card-chevron">{open ? "▾" : "▸"}</span>
          <span className="cafe-subsection-title">Trajectory Preview</span>
        </button>
        {open ? (
          <div className="cafe-dynamics-panel-body">
            {!nodes.length ? <div className="cafe-note">No preview data for current trajectory/layout.</div>
              : trajectoryType === "waypoint" ? <WaypointSVG preview={preview} width={W} height={H} nodeSize={nodeSize} edgeWidth={edgeWidth} />
              : <MilestoneSVG preview={preview} width={W} height={H} nodeSize={nodeSize} edgeWidth={edgeWidth} />}
          </div>
        ) : null}
      </div>
    );
  }
}
