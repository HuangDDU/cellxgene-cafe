export const CELLXGENE_LAYOUT_CHOICE_SET = "cellxgene/layoutChoice/set";

export const CAFE_TRAJECTORY_NAME_SET = "cafe/trajectory/name/set";
export const CAFE_TRAJECTORY_UPDATE = "cafe/trajectory/update";
export const CAFE_TRAJECTORY_VISIBILITY_SET = "cafe/trajectory/show";
export const CAFE_TRAJECTORY_ANCHOR_SET = "cafe/trajectory/anchor";
export const CAFE_TRAJECTORY_TYPE_SET = "cafe/trajectory/type";
export const CAFE_TRAJECTORY_NODE_SIZE_SET = "cafe/trajectory/nodeSize";
export const CAFE_TRAJECTORY_EDGE_WIDTH_SET = "cafe/trajectory/edgeWidth";
export const CAFE_TRAJECTORY_PREVIEW_SET = "cafe/trajectory/preview/set";

export const CAFE_MANIFEST_SET = "cafe/manifest/set";
export const CAFE_CONTEXT_SET = "cafe/context/set";
export const CAFE_CONTEXT_PATCH = "cafe/context/patch";
export const CAFE_ACTIVE_TAB_SET = "cafe/activeTab/set";
export const CAFE_MODULES_SET = "cafe/modules/set";

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

export function setCafeTrajectoryPreview(preview) {
  return { type: CAFE_TRAJECTORY_PREVIEW_SET, preview };
}

export function setCafeManifest(manifest, modules) {
  return { type: CAFE_MANIFEST_SET, manifest, modules };
}

export function setCafeContext(context) {
  return { type: CAFE_CONTEXT_SET, context };
}

export function patchCafeContext(patch) {
  return { type: CAFE_CONTEXT_PATCH, patch };
}

export function setCafeActiveTab(activeTab) {
  return { type: CAFE_ACTIVE_TAB_SET, activeTab };
}

export function setCafeModules(modules) {
  return { type: CAFE_MODULES_SET, modules };
}
