import React from "react";
import { connect } from "react-redux";

import { buildStaticPlotUrl } from "../../../lib/api";
import { CardSection } from "../../common";

import "./index.css";

@connect((state) => ({
  currentTrajectory: state.trajectory?.trajectoryName || "",
  currentLayout: state.cellxgene?.layoutChoice?.current || "umap",
}))
export default class StaticPanel extends React.Component {
  constructor(props) { super(props); this.state = { staticView: "trajectory", imageSeed: 0 }; }

  render() {
    const { currentTrajectory, currentLayout } = this.props;
    const { staticView, imageSeed } = this.state;
    const url = buildStaticPlotUrl({ view: staticView, trajectory: currentTrajectory, layout: currentLayout, t: imageSeed });

    return (
      <CardSection title="Static" defaultOpen badge={staticView} className="cafe-static-card">
        <div className="cafe-note cafe-static-note">Static figures rendered by cafe.plot.</div>
        <div className="cafe-switch-row cafe-static-switches">
          <span className="cafe-note">Static View:</span>
          {["trajectory", "graph", "stream"].map((v) => (
            <button key={v} type="button" className={`cafe-chip-btn ${staticView === v ? "is-active" : ""}`}
              onClick={() => this.setState({ staticView: v })}>{v.charAt(0).toUpperCase() + v.slice(1)}</button>
          ))}
        </div>
        <div className="cafe-static-refresh-row">
          <button type="button" className="cafe-btn" onClick={() => this.setState((s) => ({ imageSeed: s.imageSeed + 1 }))}>Refresh</button>
        </div>
        <div className="cafe-static-image-wrap"><img className="cafe-static-image" src={url} alt="Static" /></div>
      </CardSection>
    );
  }
}
