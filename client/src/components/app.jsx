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

export function ModuleDispatcherBase({ activeTab }) {
  if (activeTab === "data") return <Data />;
  if (activeTab === "method") return <Method />;
  if (activeTab === "explorer") return <Explorer active />;
  if (activeTab === "agent") return <Agent />;
  return <Plot />;
}

const ModuleDispatcher = connect((state) => ({
  activeTab: state.context?.activeTab,
}))(ModuleDispatcherBase);

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
