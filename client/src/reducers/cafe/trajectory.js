const initialState = {
  showTrajectory: false,
  anchorTrajectory: false,
  trajectoryType: "milestone",
  nodeSize: 2.5,
  edgeWidth: 1,
};

function applyPatch(state, patch) {
  if (!patch || typeof patch !== "object") {
    return state;
  }

  const next = {
    ...state,
  };

  if (patch.trajectory && typeof patch.trajectory === "object") {
    Object.assign(next, patch.trajectory);
  }

  const keys = ["showTrajectory", "anchorTrajectory", "trajectoryType", "nodeSize", "edgeWidth"];

  keys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(patch, key)) {
      next[key] = patch[key];
    }
  });

  return next;
}

export default function trajectory(state = initialState, action) {
  switch (action.type) {
    case "cafe/trajectory/update":
      return applyPatch(state, action.patch);
    case "cafe/trajectory/show":
      return {
        ...state,
        showTrajectory: action.showTrajectory ?? state.showTrajectory,
      };
    case "cafe/trajectory/anchor":
      return {
        ...state,
        anchorTrajectory: action.anchorTrajectory ?? state.anchorTrajectory,
      };
    case "cafe/trajectory/type":
      return {
        ...state,
        trajectoryType: action.trajectoryType ?? state.trajectoryType,
      };
    case "cafe/trajectory/nodeSize":
      return {
        ...state,
        nodeSize: action.nodeSize ?? state.nodeSize,
      };
    case "cafe/trajectory/edgeWidth":
      return {
        ...state,
        edgeWidth: action.edgeWidth ?? state.edgeWidth,
      };
    default:
      return state;
  }
}
