/**
 * Tests for the cafeStore: dispatch, getState, subscribe, and integration
 * with the cellxgene + trajectory reducers.
 *
 * We import the module, then immediately reset the store state before each test
 * by dispatching a full state replacement through the store's internal API.
 */
import cafeStore from "../../src/lib/cafeStore";

// The cafeStore is a singleton created at module import time.
// We rely on the store being usable as-is since it initializes with defaults.
// Each test dispatches actions and asserts resulting state.

describe("cafeStore", () => {
  it("has expected initial state shape", () => {
    const state = cafeStore.getState();
    expect(state).toHaveProperty("cellxgene");
    expect(state).toHaveProperty("trajectory");
    expect(state).toHaveProperty("host");
    expect(state.trajectory.trajectoryName).toBe("");
    expect(state.trajectory.showTrajectory).toBe(false);
    expect(state.trajectory.nodeSize).toBe(2.5);
    expect(state.cellxgene.layoutChoice.current).toBe("");
  });

  it("dispatch updates state via trajectory reducer", () => {
    cafeStore.dispatch({
      type: "cafe/trajectory/name/set",
      trajectoryName: "ref",
      available: ["ref", "palantir"],
    });
    const state = cafeStore.getState();
    expect(state.trajectory.trajectoryName).toBe("ref");
    expect(state.trajectory.available).toEqual(["ref", "palantir"]);
  });

  it("dispatch updates state via cellxgene reducer", () => {
    cafeStore.dispatch({
      type: "cellxgene/layoutChoice/set",
      layoutChoice: "umap",
      currentDimNames: ["UMAP_1", "UMAP_2"],
    });
    const state = cafeStore.getState();
    expect(state.cellxgene.layoutChoice.current).toBe("umap");
    expect(state.cellxgene.layoutChoice.currentDimNames).toEqual(["UMAP_1", "UMAP_2"]);
  });

  it("dispatch returns the action", () => {
    const action = { type: "cafe/trajectory/show", showTrajectory: true };
    const result = cafeStore.dispatch(action);
    expect(result).toBe(action);
  });

  it("dispatch ignores non-object actions", () => {
    const before = cafeStore.getState();
    cafeStore.dispatch(null);
    cafeStore.dispatch("string");
    cafeStore.dispatch(42);
    const after = cafeStore.getState();
    expect(after).toEqual(before);
  });

  it("subscribe notifies listeners on dispatch", () => {
    const listener = jest.fn();
    const unsubscribe = cafeStore.subscribe(listener);

    // subscribe calls listener immediately
    expect(listener).toHaveBeenCalledTimes(1);

    cafeStore.dispatch({ type: "cafe/trajectory/show", showTrajectory: true });
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    cafeStore.dispatch({ type: "cafe/trajectory/show", showTrajectory: false });
    expect(listener).toHaveBeenCalledTimes(2); // not called again
  });

  it("subscribe rejects non-function listener", () => {
    const unsub = cafeStore.subscribe(null);
    expect(typeof unsub).toBe("function");
    unsub();
  });

  it("getState returns a snapshot each call", () => {
    const s1 = cafeStore.getState();
    cafeStore.dispatch({ type: "cafe/trajectory/nodeSize", nodeSize: 8 });
    const s2 = cafeStore.getState();
    expect(s2.trajectory.nodeSize).toBe(8);
    expect(s1.trajectory.nodeSize).toBe(2.5); // original default
  });

  it("multiple dispatches accumulate correctly", () => {
    cafeStore.dispatch({ type: "cafe/trajectory/name/set", trajectoryName: "test", available: ["test"] });
    cafeStore.dispatch({ type: "cafe/trajectory/show", showTrajectory: true });
    cafeStore.dispatch({ type: "cafe/trajectory/anchor", anchorTrajectory: true });
    cafeStore.dispatch({ type: "cafe/trajectory/type", trajectoryType: "waypoint" });
    cafeStore.dispatch({ type: "cafe/trajectory/nodeSize", nodeSize: 7 });
    cafeStore.dispatch({ type: "cafe/trajectory/edgeWidth", edgeWidth: 3 });

    const state = cafeStore.getState();
    expect(state.trajectory.trajectoryName).toBe("test");
    expect(state.trajectory.showTrajectory).toBe(true);
    expect(state.trajectory.anchorTrajectory).toBe(true);
    expect(state.trajectory.trajectoryType).toBe("waypoint");
    expect(state.trajectory.nodeSize).toBe(7);
    expect(state.trajectory.edgeWidth).toBe(3);
  });

  it("sets window globals when window is defined", () => {
    expect(window.__CAFE_REDUX_STORE__).toBe(cafeStore);
    expect(window.__REDUX_STORE__).toBe(cafeStore);
  });
});
