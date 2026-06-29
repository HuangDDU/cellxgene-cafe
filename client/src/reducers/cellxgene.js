import { CELLXGENE_LAYOUT_CHOICE_SET } from "./actions";

export const initialCellxgeneState = {
  layoutChoice: {
    current: "",
    available: [],
    currentDimNames: [],
  },
};

export default function cellxgene(state = initialCellxgeneState, action) {
  switch (action.type) {
    case CELLXGENE_LAYOUT_CHOICE_SET:
      return {
        ...state,
        layoutChoice: {
          ...state.layoutChoice,
          current: action.layoutChoice ?? state.layoutChoice.current,
          available: action.available ?? state.layoutChoice.available,
          currentDimNames: action.currentDimNames ?? state.layoutChoice.currentDimNames,
        },
      };
    default:
      return state;
  }
}
