export const CELLXGENE_LAYOUT_CHOICE_SET = "cellxgene/layoutChoice/set";

export const CAFE_TRAJECTORY_NAME_SET = "cafe/trajectory/name/set";
export const CAFE_TRAJECTORY_UPDATE = "cafe/trajectory/update";
export const CAFE_TRAJECTORY_VISIBILITY_SET = "cafe/trajectory/show";
export const CAFE_TRAJECTORY_ANCHOR_SET = "cafe/trajectory/anchor";
export const CAFE_TRAJECTORY_TYPE_SET = "cafe/trajectory/type";
export const CAFE_TRAJECTORY_NODE_SIZE_SET = "cafe/trajectory/nodeSize";
export const CAFE_TRAJECTORY_EDGE_WIDTH_SET = "cafe/trajectory/edgeWidth";

export function setCellxgeneLayoutChoice(layoutChoice, currentDimNames) {
  return {
    type: CELLXGENE_LAYOUT_CHOICE_SET,
    layoutChoice,
    currentDimNames,
  };
}

export function setCafeTrajectoryName(trajectoryName, available) {
  return {
    type: CAFE_TRAJECTORY_NAME_SET,
    trajectoryName,
    available,
  };
}

export function updateCafeTrajectory(patch) {
  return {
    type: CAFE_TRAJECTORY_UPDATE,
    patch,
  };
}

export function setCafeTrajectoryVisible(showTrajectory) {
  return {
    type: CAFE_TRAJECTORY_VISIBILITY_SET,
    showTrajectory,
  };
}

export function setCafeTrajectoryAnchor(anchorTrajectory) {
  return {
    type: CAFE_TRAJECTORY_ANCHOR_SET,
    anchorTrajectory,
  };
}

export function setCafeTrajectoryType(trajectoryType) {
  return {
    type: CAFE_TRAJECTORY_TYPE_SET,
    trajectoryType,
  };
}

export function setCafeTrajectoryNodeSize(nodeSize) {
  return {
    type: CAFE_TRAJECTORY_NODE_SIZE_SET,
    nodeSize,
  };
}

export function setCafeTrajectoryEdgeWidth(edgeWidth) {
  return {
    type: CAFE_TRAJECTORY_EDGE_WIDTH_SET,
    edgeWidth,
  };
}
