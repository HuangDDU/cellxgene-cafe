import cellxgeneReducer, { initialCellxgeneState } from "../../src/reducers/cellxgene";
import { CELLXGENE_LAYOUT_CHOICE_SET } from "../../src/reducers/actions";

describe("cellxgene reducer", () => {
  it("returns initial state for unknown action", () => {
    const state = cellxgeneReducer(undefined, { type: "@@INIT" });
    expect(state).toEqual(initialCellxgeneState);
  });

  it("does not mutate state on unknown action", () => {
    const prev = cellxgeneReducer(undefined, { type: "@@INIT" });
    const next = cellxgeneReducer(prev, { type: "unknown/action" });
    expect(next).toBe(prev);
  });

  describe("CELLXGENE_LAYOUT_CHOICE_SET", () => {
    it("sets layoutChoice.current", () => {
      const state = cellxgeneReducer(undefined, {
        type: CELLXGENE_LAYOUT_CHOICE_SET,
        layoutChoice: "umap",
      });
      expect(state.layoutChoice.current).toBe("umap");
    });

    it("sets currentDimNames", () => {
      const state = cellxgeneReducer(undefined, {
        type: CELLXGENE_LAYOUT_CHOICE_SET,
        layoutChoice: "umap",
        currentDimNames: ["UMAP_1", "UMAP_2"],
      });
      expect(state.layoutChoice.currentDimNames).toEqual(["UMAP_1", "UMAP_2"]);
    });

    it("preserves available when changing layout", () => {
      const prev = {
        layoutChoice: { current: "pca", available: ["pca", "umap", "tsne"], currentDimNames: [] },
      };
      const state = cellxgeneReducer(prev, {
        type: CELLXGENE_LAYOUT_CHOICE_SET,
        layoutChoice: "tsne",
        currentDimNames: ["tSNE_1", "tSNE_2"],
      });
      expect(state.layoutChoice.current).toBe("tsne");
      expect(state.layoutChoice.available).toEqual(["pca", "umap", "tsne"]);
      expect(state.layoutChoice.currentDimNames).toEqual(["tSNE_1", "tSNE_2"]);
    });

    it("falls back to existing current when layoutChoice not provided", () => {
      const prev = {
        layoutChoice: {
          current: "umap",
          available: [],
          currentDimNames: [],
        },
      };
      const state = cellxgeneReducer(prev, {
        type: CELLXGENE_LAYOUT_CHOICE_SET,
        currentDimNames: ["UMAP_1"],
      });
      expect(state.layoutChoice.current).toBe("umap");
      expect(state.layoutChoice.currentDimNames).toEqual(["UMAP_1"]);
    });
  });
});
