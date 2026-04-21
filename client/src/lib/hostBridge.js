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

let fallbackState = defaultBridgeState();

function hasHostBridge() {
  const bridge = window.CafeHostBridge;
  return !!(bridge && typeof bridge.getState === "function");
}

function mergeFallbackPatch(state, patch) {
  if (!patch || typeof patch !== "object") {
    return state;
  }

  const next = {
    ...state,
    layoutChoice: { ...(state.layoutChoice || {}) },
    trajectoryChoice: { ...(state.trajectoryChoice || {}) },
    trajectory: { ...(state.trajectory || {}) },
  };

  if (Object.prototype.hasOwnProperty.call(patch, "layoutChoice")) {
    if (typeof patch.layoutChoice === "string") {
      next.layoutChoice.current = patch.layoutChoice;
    } else if (patch.layoutChoice && typeof patch.layoutChoice === "object") {
      next.layoutChoice = { ...next.layoutChoice, ...patch.layoutChoice };
    }
  }

  if (Object.prototype.hasOwnProperty.call(patch, "trajectoryChoice")) {
    if (typeof patch.trajectoryChoice === "string") {
      next.trajectoryChoice.current = patch.trajectoryChoice;
    } else if (patch.trajectoryChoice && typeof patch.trajectoryChoice === "object") {
      next.trajectoryChoice = { ...next.trajectoryChoice, ...patch.trajectoryChoice };
    }
  }

  if (patch.trajectory && typeof patch.trajectory === "object") {
    next.trajectory = { ...next.trajectory, ...patch.trajectory };
  }

  const trajectoryKeys = [
    "showTrajectory",
    "anchorTrajectory",
    "trajectoryType",
    "nodeSize",
    "edgeWidth",
  ];

  trajectoryKeys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(patch, key)) {
      next.trajectory[key] = patch[key];
    }
  });

  return next;
}

export function getBridgeState() {
  const bridge = window.CafeHostBridge;
  if (!hasHostBridge()) {
    return fallbackState;
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
  if (!hasHostBridge() || typeof bridge.subscribe !== "function") {
    const handler = () => listener(fallbackState);
    window.addEventListener(UPDATE_EVENT, handler);
    return () => window.removeEventListener(UPDATE_EVENT, handler);
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

  fallbackState = mergeFallbackPatch(fallbackState, patch);
  window.dispatchEvent(new CustomEvent(UPDATE_EVENT, { detail: fallbackState }));
}
