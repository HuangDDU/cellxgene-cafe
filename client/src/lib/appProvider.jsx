import React, { createContext, useEffect, useCallback, useRef } from "react";
import { Provider } from "react-redux";

import cafeStore from "./cafeStore";
import { fetchContext, fetchManifest, prefetchModuleData } from "./api";
import { getBridgeState, subscribeBridgeState } from "./hostBridge";
import {
  setCafeManifest,
  setCellxgeneLayoutChoice,
  setCafeTrajectoryName,
  setCafeTrajectoryPreview,
} from "../reducers/actions";

export const AppContext = createContext(null);

// Cache for pre-fetched context responses keyed by "trajectory|layout"
function createContextStore() {
  const store = {};
  return {
    get(t, l) { return store[`${t || ""}|${l || ""}`] || null; },
    set(t, l, d) { if (d) store[`${t || ""}|${l || ""}`] = d; },
    async ensure(t, l) { const k = `${t || ""}|${l || ""}`; if (store[k]) return store[k]; const d = await fetchContext({ trajectory: t, layout: l }); store[k] = d; return d; },
  };
}

// Merge a context API response into the trajectory/cellxgene Redux slices.
// This is the only place context data enters the store — no context.data blob.
function mergeContextIntoStore(data) {
  if (!data) return;
  const cur = data.current || {};
  cafeStore.dispatch(setCafeTrajectoryName(
    cur.trajectory || "",
    data.trajectories || [],
  ));
  cafeStore.dispatch(setCafeTrajectoryPreview(data.plot?.preview || null));
  cafeStore.dispatch(setCellxgeneLayoutChoice(
    cur.layout || "",
    null,
    data.layouts || [],
  ));
}

export function CafeAppProvider({ children }) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const syncedLayoutRef = useRef("");
  const syncedTrajectoryRef = useRef("");
  const contextStore = useRef(createContextStore()).current;

  const reloadContext = useCallback(async (nextParams = {}) => {
    const t = nextParams.trajectory || "", l = nextParams.layout || "";
    const cached = contextStore.get(t, l);
    if (cached) {
      mergeContextIntoStore(cached);
      syncedTrajectoryRef.current = cached?.current?.trajectory || t;
      syncedLayoutRef.current = cached?.current?.layout || l;
      return;
    }
    try {
      const data = await contextStore.ensure(t, l);
      mergeContextIntoStore(data);
      syncedTrajectoryRef.current = data?.current?.trajectory || t;
      syncedLayoutRef.current = data?.current?.layout || l;
    } catch (err) { setError(err?.message || "Failed to refresh context"); }
  }, [contextStore]);

  const loadBootstrap = useCallback(async (params = {}) => {
    setLoading(true); setError("");
    try {
      const [manifestData, contextData] = await Promise.all([fetchManifest(), fetchContext(params)]);
      const defaultModules = [
        { key: "plot", label: "Plot", enabled: true },
        { key: "data", label: "Data", enabled: true },
        { key: "method", label: "Method", enabled: true },
        { key: "explorer", label: "Explorer", enabled: true },
        { key: "agent", label: "Agent", enabled: true },
      ];
      const modules = (manifestData?.modules || []).map((m) => {
        const def = defaultModules.find((d) => d.key === m.key);
        return { ...m, label: m.label || def?.label || m.key, enabled: m.enabled ?? def?.enabled ?? false };
      });
      if (!modules.length) modules.push(...defaultModules);
      cafeStore.dispatch(setCafeManifest(manifestData, modules));
      // Merge context into trajectory + cellxgene slices (not a separate blob)
      mergeContextIntoStore(contextData);
      contextStore.set(contextData?.current?.trajectory, contextData?.current?.layout, contextData);
      syncedLayoutRef.current = contextData?.current?.layout || "";
      syncedTrajectoryRef.current = contextData?.current?.trajectory || "";
      setLoading(false);
      prefetchModuleData({
        trajectory: contextData?.current?.trajectory || "",
        layout: contextData?.current?.layout || "",
      });
    } catch (err) { setError(err?.message || "Failed to load CAFE plugin data"); setLoading(false); }
  }, [contextStore]);

  // Sync bridge state → cafeStore (only on actual changes)
  useEffect(() => {
    loadBootstrap();
    const unsubscribe = subscribeBridgeState((nextState) => {
      const state = nextState || getBridgeState();
      const cur = cafeStore.getState();
      const nl = state?.cellxgene?.layoutChoice?.current;
      if (nl && nl !== cur?.cellxgene?.layoutChoice?.current) {
        cafeStore.dispatch(setCellxgeneLayoutChoice(nl, state.cellxgene.layoutChoice.currentDimNames));
      }
      const nt = state?.trajectory?.trajectoryName;
      if (nt && nt !== cur?.trajectory?.trajectoryName) {
        cafeStore.dispatch(setCafeTrajectoryName(nt, state.trajectory.available));
      }
    });
    return () => unsubscribe();
  }, [loadBootstrap]);

  // When store trajectory/layout changes, reload context
  useEffect(() => {
    const state = cafeStore.getState();
    const bl = state?.cellxgene?.layoutChoice?.current || "";
    const bt = state?.trajectory?.trajectoryName || "";
    if (!state?.trajectory?.preview) return; // context not loaded yet
    const sl = syncedLayoutRef.current, st = syncedTrajectoryRef.current;
    if ((bl && bl !== sl) || (bt && bt !== st)) {
      reloadContext({ trajectory: bt !== st ? bt : st, layout: bl !== sl ? bl : sl });
    }
  });

  const value = { loading, error, reloadContext, loadBootstrap };

  return (
    <Provider store={cafeStore}>
      <AppContext.Provider value={value}>{children}</AppContext.Provider>
    </Provider>
  );
}
