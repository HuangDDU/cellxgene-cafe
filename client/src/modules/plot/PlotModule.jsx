import React, { useMemo, useState } from "react";

import { buildStaticPlotUrl } from "../../lib/api";
import PreviewNetwork from "./PreviewNetwork";

function PlotModule({ context, bridgeState, onPatchPlotState, onRefreshContext }) {
  const plotState = bridgeState?.trajectory || {};
  const trajectoryChoice = bridgeState?.trajectoryChoice || {};
  const layoutChoice = bridgeState?.layoutChoice || {};

  const [staticView, setStaticView] = useState("trajectory");
  const [imageSeed, setImageSeed] = useState(0);

  const trajectoryOptions = context?.trajectories || [];
  const layoutOptions = context?.layouts || [];

  const currentTrajectory = trajectoryChoice.current || context?.current?.trajectory || "";
  const currentLayout = layoutChoice.current || context?.current?.layout || "";
  const preview = context?.plot?.preview || { nodes: [], edges: [], waypointSegments: {} };

  const staticImageUrl = useMemo(
    () =>
      buildStaticPlotUrl({
        view: staticView,
        trajectory: currentTrajectory,
        layout: currentLayout,
        t: imageSeed,
      }),
    [staticView, currentTrajectory, currentLayout, imageSeed]
  );

  const onTrajectoryChange = (event) => {
    const value = event.target.value;
    onPatchPlotState({ trajectoryChoice: value });
    onRefreshContext({ trajectory: value, layout: currentLayout });
  };

  const onLayoutChange = (event) => {
    const value = event.target.value;
    onPatchPlotState({ layoutChoice: value });
    onRefreshContext({ trajectory: currentTrajectory, layout: value });
  };

  const refreshStaticPlot = () => {
    setImageSeed((seed) => seed + 1);
  };

  return (
    <div>
      <div className="cafe-card cafe-dynamics-card">
        <h4>Dynamics</h4>
        <div className="cafe-note" style={{ marginBottom: "10px" }}>
          在 Cellxgene 主面板上动态展示轨迹（和原本交互逻辑一致）。
        </div>

        <div className="cafe-dynamics-layout">
          <div className="cafe-dynamics-controls-panel">
            <div className="cafe-dynamics-control-grid">
              <div className="cafe-field">
                <label htmlFor="trajectory-method">Method / Trajectory</label>
                <select id="trajectory-method" value={currentTrajectory} onChange={onTrajectoryChange}>
                  {trajectoryOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="cafe-field">
                <label htmlFor="trajectory-layout">Embedding Layout</label>
                <select id="trajectory-layout" value={currentLayout} onChange={onLayoutChange}>
                  {layoutOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="cafe-switch-row cafe-dynamics-switches">
              <label>
                <input
                  type="checkbox"
                  checked={!!plotState.showTrajectory}
                  onChange={(event) => onPatchPlotState({ showTrajectory: event.target.checked })}
                />{" "}
                Show
              </label>

              <label>
                <input
                  type="checkbox"
                  checked={!!plotState.anchorTrajectory}
                  onChange={(event) => onPatchPlotState({ anchorTrajectory: event.target.checked })}
                />{" "}
                Anchor
              </label>

              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(plotState.trajectoryType || "milestone") === "milestone"}
                  onChange={() => onPatchPlotState({ trajectoryType: "milestone" })}
                />{" "}
                milestone
              </label>

              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(plotState.trajectoryType || "milestone") === "waypoint"}
                  onChange={() => onPatchPlotState({ trajectoryType: "waypoint" })}
                />{" "}
                waypoint
              </label>
            </div>

            <div className="cafe-dynamics-sliders">
              <div className="cafe-field">
                <label>Milestone node size: {Number(plotState.nodeSize ?? 2.5).toFixed(1)}</label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.1"
                  value={plotState.nodeSize ?? 2.5}
                  onChange={(event) => onPatchPlotState({ nodeSize: Number(event.target.value) })}
                />
              </div>

              <div className="cafe-field">
                <label>Milestone edge width: {Number(plotState.edgeWidth ?? 1).toFixed(1)}</label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.1"
                  value={plotState.edgeWidth ?? 1}
                  onChange={(event) => onPatchPlotState({ edgeWidth: Number(event.target.value) })}
                />
              </div>
            </div>

            <div className="cafe-dynamics-refresh-row">
              <button
                type="button"
                className="cafe-btn"
                onClick={() => onRefreshContext({ trajectory: currentTrajectory, layout: currentLayout })}
              >
                Refresh Plot Context
              </button>
              <span className="cafe-note">动态可视化会同步主面板轨迹绘制。</span>
            </div>
          </div>

          <div className="cafe-dynamics-preview-panel">
            <h4 className="cafe-subsection-title">Trajectory Preview</h4>
            <PreviewNetwork preview={preview} />
          </div>
        </div>
      </div>

      <div className="cafe-card">
        <h4>Static</h4>
        <div className="cafe-note" style={{ marginBottom: "10px" }}>
          后端分别调用 cafe.plot.plot_trajectory / cafe.plot.plot_graph / cafe.plot.plot_stream 并返回图片。
        </div>

        <div className="cafe-switch-row" style={{ marginBottom: "10px" }}>
          <span className="cafe-note">Static View:</span>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "trajectory" ? "is-active" : ""}`}
            onClick={() => setStaticView("trajectory")}
          >
            Trajectory
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "graph" ? "is-active" : ""}`}
            onClick={() => setStaticView("graph")}
          >
            Graph
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "stream" ? "is-active" : ""}`}
            onClick={() => setStaticView("stream")}
          >
            Stream
          </button>
        </div>

        <div style={{ marginBottom: "10px" }}>
          <button type="button" className="cafe-btn" onClick={refreshStaticPlot}>
            Refresh Static Figure
          </button>
        </div>

        <div className="cafe-static-image-wrap">
          <img
            className="cafe-static-image"
            src={staticImageUrl}
            alt="Static trajectory visualization"
          />
        </div>
      </div>
    </div>
  );
}

export default PlotModule;
