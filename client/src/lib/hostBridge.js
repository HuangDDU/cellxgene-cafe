const UPDATE_EVENT = "cafe:trajectory:update";

function defaultBridgeState() {
  return {
    layoutChoice: { current: "" },
    trajectoryChoice: { current: "", available: [] },
    trajectory: {
      showTrajectory: false,
      anchorTrajectory: false,
      trajectoryType: "milestone",
      nodeSize: 2.5,
      edgeWidth: 1
    }
  };
}

export function getBridgeState() {
  const bridge = window.CafeHostBridge;
  if (!bridge || typeof bridge.getState !== "function") {
    return defaultBridgeState();
  }

  try {
    return bridge.getState() || defaultBridgeState();
  } catch (error) {
    console.error("Failed to read CafeHostBridge state", error);
    return defaultBridgeState();
  }
}

export function subscribeBridgeState(listener) {
  const bridge = window.CafeHostBridge;
  if (!bridge || typeof bridge.subscribe !== "function") {
    return () => {};
  }

  try {
    return bridge.subscribe(listener);
  } catch (error) {
    console.error("Failed to subscribe CafeHostBridge", error);
    return () => {};
  }
}

export function applyTrajectoryPatch(patch) {
  const bridge = window.CafeHostBridge;
  if (bridge && typeof bridge.updateTrajectory === "function") {
    bridge.updateTrajectory(patch);
    return;
  }

  window.dispatchEvent(new CustomEvent(UPDATE_EVENT, { detail: patch }));
}
