import React from "react";
import { connect } from "react-redux";

import { AppContext } from "../lib/appProvider";
import { setCafeActiveTab } from "../reducers/actions";

import TabNav from "./TabNav";
import Plot from "./plot";
import Data from "./data";
import Method from "./method";
import Explorer from "./explorer";
import Agent from "./agent";

@connect((state) => ({
  manifest: state.context?.manifest,
  datasetName: state.context?.manifest?.dataset?.name || "dataset",
}))
class CafeHeader extends React.Component {
  render() {
    const { manifest, datasetName } = this.props;
    return (
      <div className="cafe-header">
        <div>
          <div className="cafe-title">Cafe Plugin</div>
          <div className="cafe-subtitle">{manifest?.dataset?.name || datasetName}</div>
        </div>
        <button type="button" className="cafe-refresh-btn" onClick={() => window.location.reload()}>
          Refresh
        </button>
      </div>
    );
  }
}

const TabNavContainer = connect(
  (state) => ({ items: state.context?.modules || [], activeKey: state.context?.activeTab || "plot" }),
  (dispatch) => ({ onChange: (key) => dispatch(setCafeActiveTab(key)) })
)(TabNav);

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
        <CafeHeader />
        {error ? <div className="cafe-error">{error}</div> : null}
        <TabNavContainer />
        <div className="cafe-body"><ModuleDispatcher /></div>
      </div>
    );
  }
}
