export function installCafeHostBridge(store, hostActions = {}) {
  if (!store || typeof store.getState !== "function" || typeof store.subscribe !== "function") {
    return;
  }

  const notifySubscribers = new Set();

  const buildHostState = () => {
    const state = store.getState() || {};
    const layoutChoice = state.layoutChoice || { current: "", available: [], currentDimNames: [] };
    const annoMatrix = state.annoMatrix || {};

    return {
      layoutChoice,
      host: {
        nObs: Number.isFinite(annoMatrix.nObs) ? annoMatrix.nObs : null,
        nVar: Number.isFinite(annoMatrix.nVar) ? annoMatrix.nVar : null,
        currentLayout: layoutChoice.current || "",
        availableLayouts: Array.isArray(layoutChoice.available) ? layoutChoice.available : [],
        currentDimNames: Array.isArray(layoutChoice.currentDimNames)
          ? layoutChoice.currentDimNames
          : [],
      },
    };
  };

  const notify = () => {
    const nextState = buildHostState();
    notifySubscribers.forEach((listener) => {
      try {
        listener(nextState);
      } catch (error) {
        console.error("CafeHostBridge listener failed", error);
      }
    });
  };

  window.CafeHostBridge = {
    getState() {
      return buildHostState();
    },
    subscribe(listener) {
      if (typeof listener !== "function") {
        return () => {};
      }

      notifySubscribers.add(listener);
      listener(buildHostState());
      return () => notifySubscribers.delete(listener);
    },
    dispatch(action) {
      if (!action || typeof action !== "object") {
        return;
      }

      if (action.type === "set layout choice" && typeof hostActions.layoutChoiceAction === "function") {
        store.dispatch(hostActions.layoutChoiceAction(action.layoutChoice));
        notify();
      }
    },
  };

  window.__CAFE_HOST_BRIDGE_READY__ = true;

  store.subscribe(() => {
    notify();
  });
}
