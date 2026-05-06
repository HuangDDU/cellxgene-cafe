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
          currentDimNames: action.currentDimNames ?? state.layoutChoice.currentDimNames,
        },
      };
    default:
      return state;
  }
}
