import React from "react";
import { connect } from "react-redux";

import { dispatchCafeAction } from "../../../lib/hostBridge";
import {
  setCellxgeneLayoutChoice,
  setCafeTrajectoryName,
  setCafeTrajectoryType,
  setCafeTrajectoryNodeSize,
  setCafeTrajectoryEdgeWidth,
} from "../../../reducers/actions";

import "./index.css";

const norm = (s) => String(s || "").replace(/^X_/i, "").toLowerCase().trim();

@connect((state) => {
  const t = state.trajectory || {};
  const lc = state.cellxgene?.layoutChoice || {};
  const raw = lc.available || [];
  const layoutMap = new Map();
  raw.forEach((n) => { const k = norm(n); if (k) layoutMap.set(k, n); });
  const layouts = Array.from(layoutMap.values());
  if (!layouts.length) layouts.push("umap", "pca");

  return {
    currentTrajectory: t.trajectoryName || "",
    currentLayout: lc.current || layouts[0] || "umap",
    trajectoryOptions: t.available || [],
    layoutOptions: layouts,
    trajectoryType: t.trajectoryType || "milestone",
    nodeSize: t.nodeSize ?? 2.5,
    edgeWidth: t.edgeWidth ?? 1,
  };
})
export default class TrajectorySetting extends React.Component {
  render() {
    const { currentTrajectory, currentLayout, trajectoryOptions, layoutOptions, trajectoryType, nodeSize, edgeWidth } = this.props;
    return (
      <div className="cafe-dynamics-controls-panel">
        <h4 className="cafe-subsection-title">Trajectory Setting</h4>
        <div className="cafe-dynamics-control-grid">
          <div className="cafe-dynamics-field-row">
            <label htmlFor="trajectory-method">Method / Trajectory</label>
            <select id="trajectory-method" value={currentTrajectory}
              onChange={(e) => dispatchCafeAction(setCafeTrajectoryName(e.target.value))}>
              {trajectoryOptions.map((item) => (<option key={item} value={item}>{item}</option>))}
            </select>
          </div>
          <div className="cafe-dynamics-field-row">
            <label htmlFor="trajectory-layout">Embedding Layout</label>
            <select id="trajectory-layout" value={currentLayout}
              onChange={(e) => dispatchCafeAction(setCellxgeneLayoutChoice(e.target.value))}>
              {layoutOptions.map((item) => (<option key={item} value={item}>{item}</option>))}
            </select>
          </div>
        </div>
        <div className="cafe-switch-row cafe-dynamics-switches">
          <span className="cafe-dynamics-mode-label">Plot Mode:</span>
          <label><input type="radio" name="trajectoryType" checked={trajectoryType === "milestone"}
            onChange={() => dispatchCafeAction(setCafeTrajectoryType("milestone"))} /> milestone</label>
          <label><input type="radio" name="trajectoryType" checked={trajectoryType === "waypoint"}
            onChange={() => dispatchCafeAction(setCafeTrajectoryType("waypoint"))} /> waypoint</label>
        </div>
        <div className="cafe-dynamics-sliders">
          <div className="cafe-dynamics-slider-row">
            <label htmlFor="trajectory-node-size">Milestone node size</label>
            <input id="trajectory-node-size" type="range" min="0" max="10" step="0.1" value={nodeSize}
              onChange={(e) => dispatchCafeAction(setCafeTrajectoryNodeSize(Number(e.target.value)))} />
            <span className="cafe-dynamics-slider-value">{nodeSize.toFixed(1)}</span>
          </div>
          <div className="cafe-dynamics-slider-row">
            <label htmlFor="trajectory-edge-width">Milestone edge width</label>
            <input id="trajectory-edge-width" type="range" min="0" max="10" step="0.1" value={edgeWidth}
              onChange={(e) => dispatchCafeAction(setCafeTrajectoryEdgeWidth(Number(e.target.value)))} />
            <span className="cafe-dynamics-slider-value">{edgeWidth.toFixed(1)}</span>
          </div>
        </div>
      </div>
    );
  }
}
