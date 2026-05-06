import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from "react";
import { fetchContext, fetchManifest } from "./api";
import { getBridgeState, subscribeBridgeState, createBridgeState } from "./hostBridge";

export const AppContext = createContext(null);

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useAppContext must be used within a CafeAppProvider");
  }
  return context;
}

const moduleOrder = [
  { key: "plot", label: "Plot" },
  { key: "data", label: "Data" },
  { key: "method", label: "Method" },
  { key: "explorer", label: "Explorer" },
  { key: "agent", label: "Agent" },
];

export function CafeAppProvider({ children }) {
  const [manifest, setManifest] = useState(null);
  const [context, setContext] = useState(null);
  const [activeTab, setActiveTab] = useState("plot");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [bridgeState, setBridgeState] = useState(() => createBridgeState());

  // Track the layout/trajectory values that were last used to fetch context.
  // This lets us detect host-initiated changes vs plugin-initiated changes.
  const syncedLayoutRef = useRef("");
  const syncedTrajectoryRef = useRef("");

  const loadBootstrap = useCallback(async (params = {}) => {
    setLoading(true);
    setError("");
    try {
      const [manifestData, contextData] = await Promise.all([
        fetchManifest(),
        fetchContext(params),
      ]);
      setManifest(manifestData);
      setContext(contextData);
      setActiveTab(manifestData?.defaultTab || "plot");

      const ctxLayout = contextData?.current?.layout || "";
      const ctxTrajectory = contextData?.current?.trajectory || "";
      syncedLayoutRef.current = ctxLayout;
      syncedTrajectoryRef.current = ctxTrajectory;

      setLoading(false);
    } catch (err) {
      setError(err?.message || "Failed to load CAFE plugin data");
      setLoading(false);
    }
  }, []);

  const reloadContext = useCallback(async (nextParams = {}) => {
    try {
      const data = await fetchContext(nextParams);
      setContext(data);

      const ctxLayout = data?.current?.layout || "";
      const ctxTrajectory = data?.current?.trajectory || "";
      syncedLayoutRef.current = ctxLayout;
      syncedTrajectoryRef.current = ctxTrajectory;
    } catch (err) {
      setError(err?.message || "Failed to refresh context");
    }
  }, []);

  // Subscribe to bridge state changes.
  useEffect(() => {
    loadBootstrap();
    const unsubscribe = subscribeBridgeState((nextState) => {
      setBridgeState(nextState || getBridgeState());
    });
    return () => unsubscribe();
  }, [loadBootstrap]);

  // When bridge layout or trajectory changes (plugin-driven or host-driven),
  // reload the context so that Preview / Static figures update.
  useEffect(() => {
    const bridgeLayout = bridgeState?.cellxgene?.layoutChoice?.current || "";
    const bridgeTrajectory = bridgeState?.trajectory?.trajectoryName || "";
    const syncedLayout = syncedLayoutRef.current;
    const syncedTrajectory = syncedTrajectoryRef.current;

    if (!context) return; // bootstrap not finished yet

    const layoutChanged = bridgeLayout && bridgeLayout !== syncedLayout;
    const trajectoryChanged = bridgeTrajectory && bridgeTrajectory !== syncedTrajectory;

    if (layoutChanged || trajectoryChanged) {
      reloadContext({
        trajectory: trajectoryChanged ? bridgeTrajectory : syncedTrajectory,
        layout: layoutChanged ? bridgeLayout : syncedLayout,
      });
    }
  }, [
    bridgeState?.cellxgene?.layoutChoice?.current,
    bridgeState?.trajectory?.trajectoryName,
    context,
    reloadContext,
  ]);

  const modules = useMemo(() => {
    if (!manifest?.modules) {
      return moduleOrder.map((item) => ({ ...item, enabled: true }));
    }
    const enabledByKey = {};
    manifest.modules.forEach((item) => {
      enabledByKey[item.key] = !!item.enabled;
    });
    return moduleOrder.map((item) => ({
      ...item,
      enabled: enabledByKey[item.key] ?? false,
    }));
  }, [manifest]);

  const value = {
    manifest,
    context,
    activeTab,
    loading,
    error,
    bridgeState,
    modules,
    setActiveTab,
    reloadContext,
    loadBootstrap,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
