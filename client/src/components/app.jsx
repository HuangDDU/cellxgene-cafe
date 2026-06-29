import React from "react";
import { connect } from "react-redux";

import { AppContext } from "../lib/appProvider";
import { setCafeActiveTab } from "../reducers/actions";
import { InfoGrid } from "./common";
import { buildOverviewItems } from "./common/overviewModel";

import TabNav from "./TabNav";
import Plot from "./plot";
import Data from "./data";
import Method from "./method";
import Explorer from "./explorer";
import Agent from "./agent";

const TabNavContainer = connect(
  (state) => ({ items: state.context?.modules || [], activeKey: state.context?.activeTab || "plot" }),
  (dispatch) => ({ onChange: (key) => dispatch(setCafeActiveTab(key)) })
)(TabNav);

const CafeOverviewStrip = connect((state) => ({
  manifest: state.context?.manifest,
  trajectory: state.trajectory,
  cellxgene: state.cellxgene,
}))(({ manifest, trajectory, cellxgene }) => (
  <div className="cafe-overview-strip">
    <InfoGrid
      className="cafe-overview-grid"
      items={buildOverviewItems({ manifest, trajectory, cellxgene })}
    />
  </div>
));

const ModuleDispatcher = connect((state) => ({
  activeTab: state.context?.activeTab,
}))(({ activeTab }) => (
  <div>
    <div style={{ display: activeTab === "plot" ? "block" : "none" }}><Plot /></div>
    <div style={{ display: activeTab === "data" ? "block" : "none" }}><Data /></div>
    <div style={{ display: activeTab === "method" ? "block" : "none" }}><Method /></div>
    <div style={{ display: activeTab === "explorer" ? "block" : "none" }}><Explorer /></div>
    <div style={{ display: activeTab === "agent" ? "block" : "none" }}><Agent /></div>
  </div>
));

export default class App extends React.Component {
  static contextType = AppContext;

  render() {
    const { error } = this.context;
    return (
      <div className="cafe-app">
        {error ? <div className="cafe-error">{error}</div> : null}
        <CafeOverviewStrip />
        <TabNavContainer />
        <div className="cafe-body"><ModuleDispatcher /></div>
      </div>
    );
  }
}
