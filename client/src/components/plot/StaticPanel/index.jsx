import React from "react";

import { AppContext } from "../../../lib/appProvider";
import { buildStaticPlotUrl } from "../../../lib/api";

import "./index.css";

export default class StaticPanel extends React.Component {
  static contextType = AppContext;

  constructor(props) {
    super(props);
    this.state = {
      staticView: "trajectory",
      imageSeed: 0,
    };
  }

  render() {
    const { context, bridgeState } = this.context;
    const { staticView, imageSeed } = this.state;

    const trajectoryState = bridgeState?.trajectory || {};
    const layoutChoice = bridgeState?.cellxgene?.layoutChoice || {};

    const currentTrajectory = trajectoryState.trajectoryName || context?.current?.trajectory || "";
    const currentLayout = layoutChoice.current || context?.current?.layout || "";

    const staticImageUrl = buildStaticPlotUrl({
      view: staticView,
      trajectory: currentTrajectory,
      layout: currentLayout,
      t: imageSeed,
    });

    return (
      <div className="cafe-card cafe-static-card">
        <h4>Static</h4>
        <div className="cafe-note cafe-static-note">
          后端分别调用 cafe.plot.plot_trajectory / cafe.plot.plot_graph / cafe.plot.plot_stream
          并返回图片。
        </div>

        <div className="cafe-switch-row cafe-static-switches">
          <span className="cafe-note">Static View:</span>
          {["trajectory", "graph", "stream"].map((view) => (
            <button
              key={view}
              type="button"
              className={`cafe-chip-btn ${staticView === view ? "is-active" : ""}`}
              onClick={() => this.setState({ staticView: view })}
            >
              {view.charAt(0).toUpperCase() + view.slice(1)}
            </button>
          ))}
        </div>

        <div className="cafe-static-refresh-row">
          <button
            type="button"
            className="cafe-btn"
            onClick={() => this.setState((s) => ({ imageSeed: s.imageSeed + 1 }))}
          >
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
    );
  }
}
