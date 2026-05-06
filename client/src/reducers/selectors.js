import { initialCellxgeneState } from "./cellxgene";
import { initialTrajectoryState } from "./trajectory";

export function createDefaultCafeBridgeState() {
  return {
    cellxgene: { ...initialCellxgeneState },
    trajectory: { ...initialTrajectoryState },
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
  const cellxgeneState = state.cellxgene || defaultState.cellxgene;
  const trajectoryState = state.trajectory || defaultState.trajectory;
  const layoutChoice = cellxgeneState.layoutChoice || defaultState.cellxgene.layoutChoice;
  const anno = state.annoMatrix || {};

  return {
    cellxgene: cellxgeneState,
    trajectory: trajectoryState,
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
