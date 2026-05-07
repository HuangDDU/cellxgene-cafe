import React from "react";

import { AppContext } from "../lib/appProvider";

import TabNav from "./TabNav";
import Plot from "./plot";
import Data from "./data";
import Method from "./method";
import Explorer from "./explorer";
import Agent from "./agent";

class CafeHeader extends React.Component {
  render() {
    const { manifest, context, onRefresh } = this.props;

    return (
      <div className="cafe-header">
        <div>
          <div className="cafe-title">CellFateExplorer Plugin</div>
          <div className="cafe-subtitle">
            {context?.dataset?.name || manifest?.dataset?.name || "dataset"}
          </div>
        </div>
        <button type="button" className="cafe-refresh-btn" onClick={onRefresh}>
          Refresh
        </button>
      </div>
    );
  }
}

class ModuleDispatcher extends React.Component {
  render() {
    const { activeTab, context, reloadContext } = this.props;

    switch (activeTab) {
      case "plot":
        return <Plot />;
      case "data":
        return <Data context={context} />;
      case "method":
        return <Method context={context} />;
      case "explorer":
        return <Explorer context={context} />;
      case "agent":
        return <Agent context={context} />;
      default:
        return null;
    }
  }
}

export default class App extends React.Component {
  static contextType = AppContext;

  render() {
    const {
      manifest,
      context,
      activeTab,
      loading,
      error,
      modules,
      setActiveTab,
      loadBootstrap,
      reloadContext,
    } = this.context;

    if (loading) {
      return <div className="cafe-loading">Loading CAFE plugin...</div>;
    }

    return (
      <div className="cafe-app">
        <CafeHeader manifest={manifest} context={context} onRefresh={() => loadBootstrap()} />

        {error ? <div className="cafe-error">{error}</div> : null}

        <TabNav items={modules} activeKey={activeTab} onChange={setActiveTab} />

        <div className="cafe-body">
          <ModuleDispatcher activeTab={activeTab} context={context} reloadContext={reloadContext} />
        </div>
      </div>
    );
  }
}
