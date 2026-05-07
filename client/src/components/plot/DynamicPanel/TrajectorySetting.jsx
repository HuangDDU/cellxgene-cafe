import React from "react";

import { AppContext } from "../../../lib/appProvider";
import { dispatchCafeAction } from "../../../lib/hostBridge";
import {
  setCellxgeneLayoutChoice,
  setCafeTrajectoryName,
  setCafeTrajectoryType,
  setCafeTrajectoryNodeSize,
  setCafeTrajectoryEdgeWidth,
} from "../../../reducers/actions";

import "./index.css";

export default class TrajectorySetting extends React.Component {
  static contextType = AppContext;

  render() {
    const { context, bridgeState } = this.context;

    const trajectoryState = bridgeState?.trajectory || {};
    const layoutChoice = bridgeState?.cellxgene?.layoutChoice || {};

    const currentTrajectory = trajectoryState.trajectoryName || context?.current?.trajectory || "";
    const currentLayout = layoutChoice.current || context?.current?.layout || "";
    const trajectoryOptions = context?.trajectories || [];
    const layoutOptions = context?.layouts || [];

    return (
      <div className="cafe-dynamics-controls-panel">
        <h4 className="cafe-subsection-title">Trajectory Setting</h4>
        <div className="cafe-dynamics-control-grid">
          <div className="cafe-dynamics-field-row">
            <label htmlFor="trajectory-method">Method / Trajectory</label>
            <select
              id="trajectory-method"
              value={currentTrajectory}
              onChange={(e) => dispatchCafeAction(setCafeTrajectoryName(e.target.value))}
            >
              {trajectoryOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>

          <div className="cafe-dynamics-field-row">
            <label htmlFor="trajectory-layout">Embedding Layout</label>
            <select
              id="trajectory-layout"
              value={currentLayout}
              onChange={(e) => dispatchCafeAction(setCellxgeneLayoutChoice(e.target.value))}
            >
              {layoutOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="cafe-switch-row cafe-dynamics-switches">
          <div className="cafe-dynamics-mode-row">
            <span className="cafe-dynamics-mode-label">Plot Mode:</span>
            <div className="cafe-dynamics-mode-options">
              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(trajectoryState.trajectoryType || "milestone") === "milestone"}
                  onChange={() => dispatchCafeAction(setCafeTrajectoryType("milestone"))}
                />{" "}
                milestone
              </label>
              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(trajectoryState.trajectoryType || "milestone") === "waypoint"}
                  onChange={() => dispatchCafeAction(setCafeTrajectoryType("waypoint"))}
                />{" "}
                waypoint
              </label>
            </div>
          </div>
        </div>

        <div className="cafe-dynamics-sliders">
          <div className="cafe-dynamics-slider-row">
            <label htmlFor="trajectory-node-size">Milestone node size</label>
            <input
              id="trajectory-node-size"
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={trajectoryState.nodeSize ?? 2.5}
              onChange={(e) =>
                dispatchCafeAction(setCafeTrajectoryNodeSize(Number(e.target.value)))
              }
            />
            <span className="cafe-dynamics-slider-value">
              {Number(trajectoryState.nodeSize ?? 2.5).toFixed(1)}
            </span>
          </div>

          <div className="cafe-dynamics-slider-row">
            <label htmlFor="trajectory-edge-width">Milestone edge width</label>
            <input
              id="trajectory-edge-width"
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={trajectoryState.edgeWidth ?? 1}
              onChange={(e) =>
                dispatchCafeAction(setCafeTrajectoryEdgeWidth(Number(e.target.value)))
              }
            />
            <span className="cafe-dynamics-slider-value">
              {Number(trajectoryState.edgeWidth ?? 1).toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    );
  }
}
