import React from "react";

import { fetchContext, fetchManifest } from "./lib/api";
import {
  dispatchCafeAction,
  getBridgeState,
  subscribeBridgeState,
} from "./lib/hostBridge";
import {
  setCafeLayoutChoice,
  setCafeTrajectoryAnchor,
  setCafeTrajectoryChoice,
  setCafeTrajectoryEdgeWidth,
  setCafeTrajectoryNodeSize,
  setCafeTrajectoryType,
  setCafeTrajectoryVisible,
} from "./reducers/cafe/actions";
import TabNav from "./components/TabNav";
import Plot from "./components/plot";
import Data from "./components/data";
import Method from "./components/method";
import Explorer from "./components/explorer";
import Agent from "./components/agent";

const moduleOrder = [
  { key: "plot", label: "Plot" },
  { key: "data", label: "Data" },
  { key: "method", label: "Method" },
  { key: "explorer", label: "Explorer" },
  { key: "agent", label: "Agent" },
];

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      manifest: null,
      context: null,
      activeTab: "plot",
      loading: true,
      error: "",
      bridgeState: getBridgeState(),
    };
    this.unsubscribeBridge = null;
  }

  componentDidMount() {
    this.loadBootstrap();
    this.unsubscribeBridge = subscribeBridgeState((nextState) => {
      this.setState({ bridgeState: nextState || getBridgeState() });
    });
  }

  componentWillUnmount() {
    if (typeof this.unsubscribeBridge === "function") {
      this.unsubscribeBridge();
      this.unsubscribeBridge = null;
    }
  }

  getModules() {
    const { manifest } = this.state;
    if (!manifest?.modules) {
      return moduleOrder.map((item) => ({
        ...item,
        enabled: true,
      }));
    }

    const enabledByKey = {};
    manifest.modules.forEach((item) => {
      enabledByKey[item.key] = !!item.enabled;
    });

    return moduleOrder.map((item) => ({
      ...item,
      enabled: enabledByKey[item.key] ?? false,
    }));
  }

  loadBootstrap = async (params = {}) => {
    this.setState({ loading: true, error: "" });
    try {
      const [manifestData, contextData] = await Promise.all([
        fetchManifest(),
        fetchContext(params),
      ]);
      this.setState({
        manifest: manifestData,
        context: contextData,
        activeTab: manifestData.defaultTab || "plot",
        loading: false,
      });
    } catch (err) {
      this.setState({
        error: err?.message || "Failed to load CAFE plugin data",
        loading: false,
      });
    }
  };

  syncBridgeState = () => {
    this.setState({ bridgeState: getBridgeState() });
  };

  onSetLayoutChoice = (layoutChoice) => {
    dispatchCafeAction(setCafeLayoutChoice(layoutChoice));
    this.syncBridgeState();
  };

  onSetTrajectoryChoice = (trajectoryChoice) => {
    dispatchCafeAction(setCafeTrajectoryChoice(trajectoryChoice));
    this.syncBridgeState();
  };

  onSetTrajectoryVisible = (showTrajectory) => {
    dispatchCafeAction(setCafeTrajectoryVisible(showTrajectory));
    this.syncBridgeState();
  };

  onSetTrajectoryAnchor = (anchorTrajectory) => {
    dispatchCafeAction(setCafeTrajectoryAnchor(anchorTrajectory));
    this.syncBridgeState();
  };

  onSetTrajectoryType = (trajectoryType) => {
    dispatchCafeAction(setCafeTrajectoryType(trajectoryType));
    this.syncBridgeState();
  };

  onSetTrajectoryNodeSize = (nodeSize) => {
    dispatchCafeAction(setCafeTrajectoryNodeSize(nodeSize));
    this.syncBridgeState();
  };

  onSetTrajectoryEdgeWidth = (edgeWidth) => {
    dispatchCafeAction(setCafeTrajectoryEdgeWidth(edgeWidth));
    this.syncBridgeState();
  };

  onRefreshContext = async (nextParams = {}) => {
    try {
      const data = await fetchContext(nextParams);
      this.setState({ context: data });
    } catch (err) {
      this.setState({ error: err?.message || "Failed to refresh context" });
    }
  };

  renderModule() {
    const { activeTab, context, bridgeState } = this.state;

    if (activeTab === "plot") {
      return (
        <Plot
          context={context}
          bridgeState={bridgeState}
          onSetLayoutChoice={this.onSetLayoutChoice}
          onSetTrajectoryChoice={this.onSetTrajectoryChoice}
          onSetTrajectoryVisible={this.onSetTrajectoryVisible}
          onSetTrajectoryAnchor={this.onSetTrajectoryAnchor}
          onSetTrajectoryType={this.onSetTrajectoryType}
          onSetTrajectoryNodeSize={this.onSetTrajectoryNodeSize}
          onSetTrajectoryEdgeWidth={this.onSetTrajectoryEdgeWidth}
          onRefreshContext={this.onRefreshContext}
        />
      );
    }
    if (activeTab === "data") {
      return <Data context={context} />;
    }
    if (activeTab === "method") {
      return <Method context={context} />;
    }
    if (activeTab === "explorer") {
      return <Explorer context={context} />;
    }
    if (activeTab === "agent") {
      return <Agent context={context} />;
    }
    return null;
  }

  render() {
    const { manifest, context, activeTab, loading, error } = this.state;
    const modules = this.getModules();

    if (loading) {
      return <div className="cafe-loading">Loading CAFE plugin...</div>;
    }

    return (
      <div className="cafe-app">
        <div className="cafe-header">
          <div>
            <div className="cafe-title">CellFateExplorer Plugin</div>
            <div className="cafe-subtitle">
              {context?.dataset?.name || manifest?.dataset?.name || "dataset"}
            </div>
          </div>
          <button
            type="button"
            className="cafe-refresh-btn"
            onClick={() => this.loadBootstrap()}
          >
            Refresh
          </button>
        </div>

        {error ? <div className="cafe-error">{error}</div> : null}

        <TabNav
          items={modules}
          activeKey={activeTab}
          onChange={(nextTab) => this.setState({ activeTab: nextTab })}
        />

        <div className="cafe-body">{this.renderModule()}</div>
      </div>
    );
  }
}

export default App;
