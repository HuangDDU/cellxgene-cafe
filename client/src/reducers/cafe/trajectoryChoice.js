function bestDefaultTrajectory(available) {
  if (!Array.isArray(available) || available.length === 0) {
    return "";
  }

  return available.includes("ref") ? "ref" : available[0];
}

function extractAvailableTrajectories(annoMatrix) {
  const fromCafeUns = Object.keys(annoMatrix?.uns?.cafe?.trajectory_history_dict || {}).sort();

  if (fromCafeUns.length > 0) {
    return fromCafeUns;
  }

  return Object.keys(
    annoMatrix?.schema?.annotations?.obsByName?.milestone?.categories || {},
  ).sort();
}

const initialState = {
  available: [],
  current: "",
  currentDimNames: [],
};

export default function trajectoryChoice(state = initialState, action) {
  switch (action.type) {
    case "initial data load complete": {
      const available = extractAvailableTrajectories(action.annoMatrix);
      const current = bestDefaultTrajectory(available);
      return {
        ...state,
        available,
        current,
        currentDimNames: [],
      };
    }
    case "cafe/trajectoryChoice/bootstrap":
      return {
        ...state,
        ...(action.payload || {}),
      };
    case "cafe/layoutChoice/set":
      return {
        ...state,
        currentDimNames: action.currentDimNames ?? state.currentDimNames,
      };
    case "cafe/trajectoryChoice/set":
      return {
        ...state,
        current: action.trajectoryChoice ?? state.current,
        available: Array.isArray(action.available) ? action.available : state.available,
      };
    default:
      return state;
  }
}
