import {
  CAFE_TRAJECTORY_NAME_SET,
  CAFE_TRAJECTORY_PREVIEW_SET,
  CAFE_TRAJECTORY_UPDATE,
  CAFE_TRAJECTORY_VISIBILITY_SET,
  CAFE_TRAJECTORY_ANCHOR_SET,
  CAFE_TRAJECTORY_TYPE_SET,
  CAFE_TRAJECTORY_NODE_SIZE_SET,
  CAFE_TRAJECTORY_EDGE_WIDTH_SET,
} from "./actions";

export const initialTrajectoryState = {
  trajectoryName: "",
  available: [],
  preview: null,
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

  const next = { ...state };

  if (patch.trajectory && typeof patch.trajectory === "object") {
    Object.assign(next, patch.trajectory);
  }

  const keys = [
    "trajectoryName",
    "showTrajectory",
    "anchorTrajectory",
    "trajectoryType",
    "nodeSize",
    "edgeWidth",
  ];

  keys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(patch, key)) {
      next[key] = patch[key];
    }
  });

  return next;
}

export default function trajectory(state = initialTrajectoryState, action) {
  switch (action.type) {
    case CAFE_TRAJECTORY_NAME_SET:
      return {
        ...state,
        trajectoryName: action.trajectoryName ?? state.trajectoryName,
        available: Array.isArray(action.available) ? action.available : state.available,
      };
    case CAFE_TRAJECTORY_UPDATE:
      return applyPatch(state, action.patch);
    case CAFE_TRAJECTORY_VISIBILITY_SET:
      return { ...state, showTrajectory: action.showTrajectory ?? state.showTrajectory };
    case CAFE_TRAJECTORY_ANCHOR_SET:
      return { ...state, anchorTrajectory: action.anchorTrajectory ?? state.anchorTrajectory };
    case CAFE_TRAJECTORY_TYPE_SET:
      return { ...state, trajectoryType: action.trajectoryType ?? state.trajectoryType };
    case CAFE_TRAJECTORY_NODE_SIZE_SET:
      return { ...state, nodeSize: action.nodeSize ?? state.nodeSize };
    case CAFE_TRAJECTORY_EDGE_WIDTH_SET:
      return { ...state, edgeWidth: action.edgeWidth ?? state.edgeWidth };
    case CAFE_TRAJECTORY_PREVIEW_SET:
      return { ...state, preview: action.preview ?? null };
    default:
      return state;
  }
}
