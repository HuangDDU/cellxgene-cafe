export function createDefaultCafeBridgeState() {
  return {
    layoutChoice: { current: "", available: [], currentDimNames: [] },
    trajectoryChoice: { current: "", available: [], currentDimNames: [] },
    trajectory: {
      showTrajectory: false,
      anchorTrajectory: false,
      trajectoryType: "milestone",
      nodeSize: 2.5,
      edgeWidth: 1,
    },
    host: {
      nObs: null,
      nVar: null,
      currentLayout: "",
      availableLayouts: [],
      currentDimNames: [],
    },
  };
}

export function selectCafeBridgeState(state = {}) {
  const defaultState = createDefaultCafeBridgeState();
  const cafeState = state.cafe || {};
  const layoutChoice = state.layoutChoice || defaultState.layoutChoice;
  const anno = state.annoMatrix || {};

  return {
    layoutChoice,
    trajectoryChoice: cafeState.trajectoryChoice || defaultState.trajectoryChoice,
    trajectory: cafeState.trajectory || defaultState.trajectory,
    host: {
      nObs: Number.isFinite(anno.nObs) ? anno.nObs : null,
      nVar: Number.isFinite(anno.nVar) ? anno.nVar : null,
      currentLayout: layoutChoice.current || "",
      availableLayouts: Array.isArray(layoutChoice.available) ? layoutChoice.available : [],
      currentDimNames: Array.isArray(layoutChoice.currentDimNames)
        ? layoutChoice.currentDimNames
        : [],
    },
  };
}
