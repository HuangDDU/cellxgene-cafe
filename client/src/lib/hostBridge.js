// This js file bridge is responsible for syncing state between the cafe plugin and the host cellxgene app.

import cafeStore from "./cafeStore";
import {
  CELLXGENE_LAYOUT_CHOICE_SET,
  CAFE_TRAJECTORY_NAME_SET,
  CAFE_TRAJECTORY_UPDATE,
  CAFE_TRAJECTORY_VISIBILITY_SET,
  CAFE_TRAJECTORY_ANCHOR_SET,
  CAFE_TRAJECTORY_TYPE_SET,
  CAFE_TRAJECTORY_NODE_SIZE_SET,
  CAFE_TRAJECTORY_EDGE_WIDTH_SET,
} from "../reducers/actions";
import { createDefaultCafeBridgeState } from "../reducers/selectors";

function hasHostBridge() {
  const bridge = window.CafeHostBridge;
  return !!(bridge && typeof bridge.getState === "function");
}

export function createBridgeState() {
  const localState = cafeStore.getState() || createDefaultCafeBridgeState();
  const hostState = hasHostBridge() ? window.CafeHostBridge.getState() : {};

  return {
    ...localState,
    host: hostState?.host || {
      nObs: null,
      nVar: null,
      currentLayout: localState.cellxgene?.layoutChoice?.current || "",
      availableLayouts: localState.cellxgene?.layoutChoice?.available || [],
      currentDimNames: localState.cellxgene?.layoutChoice?.currentDimNames || [],
    },
  };
}

function syncLayoutFromHost() {
  if (!hasHostBridge()) {
    return;
  }

  const hostState = window.CafeHostBridge.getState() || {};
  const nextLayout = hostState?.layoutChoice?.current || "";
  const currentLayout = cafeStore.getState()?.cellxgene?.layoutChoice?.current || "";
  if (!nextLayout || nextLayout === currentLayout) {
    return;
  }

  cafeStore.dispatch({
    type: CELLXGENE_LAYOUT_CHOICE_SET,
    layoutChoice: nextLayout,
    currentDimNames: hostState?.layoutChoice?.currentDimNames || [],
  });
}

export function getBridgeState() {
  syncLayoutFromHost();
  return createBridgeState();
}

export function subscribeBridgeState(listener) {
  if (typeof listener !== "function") {
    return () => {};
  }

  const notify = () => listener(createBridgeState());
  const unsubscribeStore = cafeStore.subscribe(notify);
  let unsubscribeHost = () => {};

  if (hasHostBridge() && typeof window.CafeHostBridge.subscribe === "function") {
    unsubscribeHost = window.CafeHostBridge.subscribe(() => {
      syncLayoutFromHost();
      notify();
    });
  }

  notify();
  return () => {
    unsubscribeStore();
    unsubscribeHost();
  };
}

export function applyTrajectoryPatch(patch) {
  if (!patch || typeof patch !== "object") {
    return;
  }

  const hostBridge = window.CafeHostBridge;
  if (Object.prototype.hasOwnProperty.call(patch, "layoutChoice") && hostBridge) {
    hostBridge.dispatch({
      type: "set layout choice",
      layoutChoice: patch.layoutChoice,
    });
  }

  cafeStore.dispatch({
    type: CAFE_TRAJECTORY_UPDATE,
    patch,
  });
}

export function dispatchCafeAction(action) {
  if (!action || typeof action !== "object") {
    return;
  }

  cafeStore.dispatch(action);

  if (!hasHostBridge()) {
    return;
  }

  // Bidirectional sync: propagate plugin actions to host Redux
  if (action.type === CELLXGENE_LAYOUT_CHOICE_SET) {
    window.CafeHostBridge.dispatch({
      type: "set layout choice",
      layoutChoice: action.layoutChoice,
    });
  }

  if (action.type === CAFE_TRAJECTORY_NAME_SET) {
    window.CafeHostBridge.dispatch({
      type: "cafe/trajectoryChoice/set",
      trajectoryChoice: action.trajectoryName,
      available: action.available,
    });
  }

  if (action.type === CAFE_TRAJECTORY_VISIBILITY_SET) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/show", showTrajectory: action.showTrajectory });
  }

  if (action.type === CAFE_TRAJECTORY_ANCHOR_SET) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/anchor", anchorTrajectory: action.anchorTrajectory });
  }

  if (action.type === CAFE_TRAJECTORY_TYPE_SET) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/type", trajectoryType: action.trajectoryType });
  }

  if (action.type === CAFE_TRAJECTORY_NODE_SIZE_SET) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/nodeSize", nodeSize: action.nodeSize });
  }

  if (action.type === CAFE_TRAJECTORY_EDGE_WIDTH_SET) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/edgeWidth", edgeWidth: action.edgeWidth });
  }

  if (action.type === CAFE_TRAJECTORY_UPDATE) {
    window.CafeHostBridge.dispatch({ type: "cafe/trajectory/update", patch: action.patch });
  }
}
