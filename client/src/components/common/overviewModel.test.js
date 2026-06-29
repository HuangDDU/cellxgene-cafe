import { buildOverviewItems, formatShape } from "./overviewModel";

describe("overviewModel", () => {
  test("formats dataset shape when obs and vars are present", () => {
    expect(formatShape({ nObs: 12500, nVars: 2400 })).toBe("12,500 cells x 2,400 genes");
  });

  test("builds compact overview items from plugin state", () => {
    const items = buildOverviewItems({
      manifest: { dataset: { name: "pancreas_fadata" } },
      trajectory: {
        trajectoryName: "ref",
        available: ["ref", "method_a"],
        trajectoryType: "milestone",
        showTrajectory: true,
      },
      cellxgene: {
        layoutChoice: { current: "umap", available: ["umap", "pca"] },
      },
      datasetSummary: {
        dataset: { shape: { nObs: 12500, nVars: 2400 } },
      },
    });

    expect(items).toEqual([
      { label: "Dataset", value: "pancreas_fadata" },
      { label: "Shape", value: "12,500 cells x 2,400 genes" },
      { label: "Trajectory", value: "ref" },
      { label: "Layout", value: "umap" },
      { label: "Mode", value: "milestone" },
      { label: "Overlay", value: "shown" },
      { label: "Trajectories", value: "2 available" },
    ]);
  });
});
