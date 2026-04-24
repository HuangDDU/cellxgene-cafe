import React, { useEffect, useMemo, useState } from "react";

import { fetchContext, fetchManifest } from "./lib/api";
import {
  applyTrajectoryPatch,
  getBridgeState,
  subscribeBridgeState,
} from "./lib/hostBridge";
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

function App() {
  const [manifest, setManifest] = useState(null);
  const [context, setContext] = useState(null);
  const [activeTab, setActiveTab] = useState("plot");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(getBridgeState());
  const [dataRefreshToken, setDataRefreshToken] = useState(0);

  const loadBootstrap = async (params = {}, options = {}) => {
    const preserveActiveTab = options.preserveActiveTab ?? false;
    setLoading(true);
    setError("");
    try {
      const [manifestData, contextData] = await Promise.all([
        fetchManifest(),
        fetchContext(params),
      ]);
      setManifest(manifestData);
      setContext(contextData);
      if (!preserveActiveTab) {
        setActiveTab(manifestData.defaultTab || "plot");
      }
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
    if (!context) {
      return;
    }
    const nextTrajectory = bridgeState?.trajectoryChoice?.current || "";
    const nextLayout = bridgeState?.layoutChoice?.current || "";
    const currentTrajectory = context?.current?.trajectory || "";
    const currentLayout = context?.current?.layout || "";
    if (nextTrajectory === currentTrajectory && nextLayout === currentLayout) {
      return;
    }
    onRefreshContext({
      trajectory: nextTrajectory || currentTrajectory,
      layout: nextLayout || currentLayout,
    });
  }, [bridgeState?.trajectoryChoice?.current, bridgeState?.layoutChoice?.current]);

  const modules = useMemo(() => {
    const enabledByKey = {};
    if (manifest?.modules) {
      manifest.modules.forEach((item) => {
        enabledByKey[item.key] = !!item.enabled;
      });
    }
    return moduleOrder.map((item) => ({
      ...item,
      enabled: enabledByKey[item.key] ?? false,
    }));
  }, [manifest]);

  const onPatchPlotState = (patch) => {
    applyTrajectoryPatch(patch);
    setBridgeState((prev) => ({
      ...prev,
      trajectory: {
        ...prev.trajectory,
        ...patch,
      },
      trajectoryChoice: {
        ...prev.trajectoryChoice,
        current: patch.trajectoryChoice ?? prev.trajectoryChoice?.current,
      },
      layoutChoice: {
        ...prev.layoutChoice,
        current: patch.layoutChoice ?? prev.layoutChoice?.current,
      },
    }));
  };

  const onRefreshContext = async (nextParams = {}) => {
    try {
      const data = await fetchContext(nextParams);
      setContext(data);
    } catch (err) {
      setError(err?.message || "Failed to refresh context");
    }
  };

  const onMethodJobSucceeded = async (job) => {
    const nextTrajectory = job?.result?.trajectoryId || job?.jobId || "";
    const nextLayoutOptions = job?.result?.trajectorySummary?.layoutNames || [];
    const currentLayout = bridgeState?.layoutChoice?.current || context?.current?.layout || "";
    const nextLayout = nextLayoutOptions.includes(currentLayout)
      ? currentLayout
      : nextLayoutOptions[0] || currentLayout || "";

    if (nextTrajectory) {
      const patch = { trajectoryChoice: nextTrajectory };
      if (nextLayout) {
        patch.layoutChoice = nextLayout;
      }
      onPatchPlotState(patch);
    }

    await loadBootstrap(
      {
        trajectory: nextTrajectory,
        layout: nextLayout,
      },
      { preserveActiveTab: true }
    );
    setDataRefreshToken((value) => value + 1);
  };

  const renderModule = () => {
    if (activeTab === "plot") {
      return (
        <PlotModule
          context={context}
          bridgeState={bridgeState}
          onPatchPlotState={onPatchPlotState}
          onRefreshContext={onRefreshContext}
        />
      );
    }
    if (activeTab === "data") {
      return <DataModule context={context} refreshToken={dataRefreshToken} />;
    }
    if (activeTab === "method") {
      return <MethodModule context={context} onJobSucceeded={onMethodJobSucceeded} />;
    }
    if (activeTab === "explorer") {
      return <ExplorerModule context={context} refreshToken={dataRefreshToken} />;
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
        <button
          type="button"
          className="cafe-refresh-btn"
          onClick={() => loadBootstrap({}, { preserveActiveTab: true })}
        >
          Refresh
        </button>
      </div>

      {error ? <div className="cafe-error">{error}</div> : null}

      <TabNav items={modules} activeKey={activeTab} onChange={setActiveTab} />

      <div className="cafe-body">{renderModule()}</div>
    </div>
  );
}

export default App;
