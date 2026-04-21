import React, { useEffect, useMemo, useState } from "react";

import { fetchContext, fetchManifest } from "./lib/api";
import {
  dispatchCafeAction,
  getBridgeState,
  subscribeBridgeState,
} from "./lib/hostBridge";
import {
  setCafeLayoutChoice,
  setCafeTrajectoryAnchor,
  setCafeTrajectoryEdgeWidth,
  setCafeTrajectoryNodeSize,
  setCafeTrajectoryType,
  setCafeTrajectoryVisible,
  setCafeTrajectoryChoice,
} from "./reducers/cafe/actions";
import TabNav from "./components/TabNav";
import PlotModule from "./modules/plot/PlotModule";
import DataModule from "./modules/data/DataModule";
import MethodModule from "./modules/method/MethodModule";
import ExplorerModule from "./modules/explorer/ExplorerModule";
import AgentModule from "./modules/agent/AgentModule";

const moduleOrder = [
  { key: "plot", label: "Plot" },
  { key: "data", label: "Data" },
  { key: "method", label: "Method" },
  { key: "explorer", label: "Explorer" },
  { key: "agent", label: "Agent" },
];

function readReduxDebugState() {
  const store = window.__CAFE_REDUX_STORE__ || window.__REDUX_STORE__ || null;
  const bridge = window.CafeHostBridge || null;

  return {
    hasStore: !!store,
    hasBridge: !!bridge,
    storeState: store?.getState ? store.getState() : null,
    bridgeState: bridge?.getState ? bridge.getState() : null,
    updatedAt: new Date().toLocaleTimeString(),
  };
}

function App() {
  const [manifest, setManifest] = useState(null);
  const [context, setContext] = useState(null);
  const [activeTab, setActiveTab] = useState("plot");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(getBridgeState());

  const loadBootstrap = async (params = {}) => {
    setLoading(true);
    setError("");
    try {
      const [manifestData, contextData] = await Promise.all([
        fetchManifest(),
        fetchContext(params),
      ]);
      setManifest(manifestData);
      setContext(contextData);
      setActiveTab(manifestData.defaultTab || "plot");
    } catch (err) {
      setError(err?.message || "Failed to load CAFE plugin data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBootstrap();
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeBridgeState((nextState) => {
      setBridgeState(nextState || getBridgeState());
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (process.env.NODE_ENV === "production") {
      return undefined;
    }

    const store = window.__CAFE_REDUX_STORE__ || window.__REDUX_STORE__;
      });
    }
    return moduleOrder.map((item) => ({
      ...item,
      enabled: enabledByKey[item.key] ?? false,
    }));
  }, [manifest]);

  const syncBridgeState = () => setBridgeState(getBridgeState());

  const onSetLayoutChoice = (layoutChoice) => {
    dispatchCafeAction(setCafeLayoutChoice(layoutChoice));
    syncBridgeState();
  };

  const onSetTrajectoryChoice = (trajectoryChoice) => {
    dispatchCafeAction(setCafeTrajectoryChoice(trajectoryChoice));
    syncBridgeState();
  };

  const onSetTrajectoryVisible = (showTrajectory) => {
    dispatchCafeAction(setCafeTrajectoryVisible(showTrajectory));
    syncBridgeState();
  };

  const onSetTrajectoryAnchor = (anchorTrajectory) => {
    dispatchCafeAction(setCafeTrajectoryAnchor(anchorTrajectory));
    syncBridgeState();
  };

  const onSetTrajectoryType = (trajectoryType) => {
    dispatchCafeAction(setCafeTrajectoryType(trajectoryType));
    syncBridgeState();
  };

  const onSetTrajectoryNodeSize = (nodeSize) => {
    dispatchCafeAction(setCafeTrajectoryNodeSize(nodeSize));
    syncBridgeState();
  };

  const onSetTrajectoryEdgeWidth = (edgeWidth) => {
    dispatchCafeAction(setCafeTrajectoryEdgeWidth(edgeWidth));
    syncBridgeState();
  };

  const onRefreshContext = async (nextParams = {}) => {
    try {
      const data = await fetchContext(nextParams);
      setContext(data);
    } catch (err) {
      setError(err?.message || "Failed to refresh context");
    }
  };

  const renderModule = () => {
    if (activeTab === "plot") {
      return (
        <PlotModule
          context={context}
          bridgeState={bridgeState}
          onSetLayoutChoice={onSetLayoutChoice}
          onSetTrajectoryChoice={onSetTrajectoryChoice}
          onSetTrajectoryVisible={onSetTrajectoryVisible}
          onSetTrajectoryAnchor={onSetTrajectoryAnchor}
          onSetTrajectoryType={onSetTrajectoryType}
          onSetTrajectoryNodeSize={onSetTrajectoryNodeSize}
          onSetTrajectoryEdgeWidth={onSetTrajectoryEdgeWidth}
          onRefreshContext={onRefreshContext}
        />
      );
    }
    if (activeTab === "data") {
      return <DataModule context={context} />;
    }
    if (activeTab === "method") {
      return <MethodModule context={context} />;
    }
    if (activeTab === "explorer") {
      return <ExplorerModule context={context} />;
    }
    if (activeTab === "agent") {
      return <AgentModule context={context} />;
    }
    return null;
  };

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
        <button type="button" className="cafe-refresh-btn" onClick={() => loadBootstrap()}>
          Refresh
        </button>
      </div>

      {error ? <div className="cafe-error">{error}</div> : null}

      <TabNav items={modules} activeKey={activeTab} onChange={setActiveTab} />

      <div className="cafe-body">{renderModule()}</div>




      {null}
    </div>
  );
}

export default App;
