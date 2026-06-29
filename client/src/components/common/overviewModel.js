function formatNumber(value) {
  return Number.isFinite(value) ? value.toLocaleString() : "";
}

export function formatShape(shape = {}) {
  const nObs = Number(shape.nObs);
  const nVars = Number(shape.nVars);

  if (!Number.isFinite(nObs) || !Number.isFinite(nVars)) {
    return "n/a";
  }

  return `${formatNumber(nObs)} cells x ${formatNumber(nVars)} genes`;
}

export function buildOverviewItems({
  manifest = null,
  trajectory = {},
  cellxgene = {},
  datasetSummary = null,
} = {}) {
  const datasetName = manifest?.dataset?.name || datasetSummary?.dataset?.name || "dataset";
  const shape = datasetSummary?.dataset?.shape;
  const currentTrajectory = trajectory.trajectoryName || "n/a";
  const currentLayout = cellxgene?.layoutChoice?.current || "n/a";
  const mode = trajectory.trajectoryType || "milestone";
  const overlay = trajectory.showTrajectory ? "shown" : "hidden";
  const trajectoryCount = Array.isArray(trajectory.available) ? trajectory.available.length : 0;

  const items = [
    { label: "Dataset", value: datasetName },
  ];

  if (shape) {
    items.push({ label: "Shape", value: formatShape(shape) });
  }

  items.push(
    { label: "Trajectory", value: currentTrajectory },
    { label: "Layout", value: currentLayout },
    { label: "Mode", value: mode },
    { label: "Overlay", value: overlay },
    { label: "Trajectories", value: `${trajectoryCount} available` },
  );

  return items;
}
