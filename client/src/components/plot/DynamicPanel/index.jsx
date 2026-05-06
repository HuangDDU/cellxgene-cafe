import React from "react";

import { AppContext } from "../../../lib/appProvider";
import { dispatchCafeAction } from "../../../lib/hostBridge";
import { setCafeTrajectoryVisible } from "../../../reducers/actions";

import TrajectoryPreview from "./TrajectoryPreview";
import TrajectorySetting from "./TrajectorySetting";

import "./index.css";

export default class DynamicPanel extends React.Component {
  static contextType = AppContext;

  render() {
    const { bridgeState } = this.context;
    const trajectoryState = bridgeState?.trajectory || {};

    return (
      <div className="cafe-card cafe-dynamics-card">
        <div className="cafe-dynamics-header">
          <h4>Dynamics</h4>
          <label className="cafe-dynamics-show-toggle">
            <input
              type="checkbox"
              checked={!!trajectoryState.showTrajectory}
              onChange={(e) => dispatchCafeAction(setCafeTrajectoryVisible(e.target.checked))}
            />
            Show
          </label>
        </div>
        <div className="cafe-note cafe-dynamics-note">
          Display trajectory dynamically on cellxgene main panel.
        </div>

        <div className="cafe-dynamics-layout">
          <TrajectorySetting />
          <TrajectoryPreview />
        </div>
      </div>
    );
  }
}
