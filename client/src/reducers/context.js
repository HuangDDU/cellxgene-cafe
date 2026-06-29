import {
  CAFE_CONTEXT_SET,
  CAFE_CONTEXT_PATCH,
  CAFE_MANIFEST_SET,
  CAFE_ACTIVE_TAB_SET,
  CAFE_MODULES_SET,
} from "./actions";

export const initialContextState = {
  manifest: null,
  data: null,
  activeTab: "plot",
  modules: [
    { key: "plot", label: "Plot", enabled: true },
    { key: "data", label: "Data", enabled: true },
    { key: "method", label: "Method", enabled: true },
    { key: "explorer", label: "Explorer", enabled: true },
    { key: "agent", label: "Agent", enabled: true },
  ],
};

export default function context(state = initialContextState, action) {
  switch (action.type) {
    case CAFE_MANIFEST_SET:
      return {
        ...state,
        manifest: action.manifest,
        modules: action.modules || state.modules,
      };
    case CAFE_CONTEXT_SET:
      return { ...state, data: action.context };
    case CAFE_CONTEXT_PATCH:
      return {
        ...state,
        data: state.data ? { ...state.data, ...action.patch } : action.patch,
      };
    case CAFE_ACTIVE_TAB_SET:
      return { ...state, activeTab: action.activeTab };
    case CAFE_MODULES_SET:
      return { ...state, modules: action.modules };
    default:
      return state;
  }
}
