import trajectoryReducer, { initialTrajectoryState } from "../../src/reducers/trajectory";
import {
  CAFE_TRAJECTORY_NAME_SET,
  CAFE_TRAJECTORY_UPDATE,
  CAFE_TRAJECTORY_VISIBILITY_SET,
  CAFE_TRAJECTORY_ANCHOR_SET,
  CAFE_TRAJECTORY_TYPE_SET,
  CAFE_TRAJECTORY_NODE_SIZE_SET,
  CAFE_TRAJECTORY_EDGE_WIDTH_SET,
} from "../../src/reducers/actions";

describe("trajectory reducer", () => {
  it("returns initial state for unknown action", () => {
    const state = trajectoryReducer(undefined, { type: "@@INIT" });
    expect(state).toEqual(initialTrajectoryState);
  });

  it("does not mutate state on unknown action", () => {
    const prev = trajectoryReducer(undefined, { type: "@@INIT" });
    const next = trajectoryReducer(prev, { type: "unknown/action" });
    expect(next).toBe(prev);
  });

  describe("CAFE_TRAJECTORY_NAME_SET", () => {
    it("sets trajectoryName and available", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_NAME_SET,
        trajectoryName: "ref",
        available: ["ref", "palantir"],
      });
      expect(state.trajectoryName).toBe("ref");
      expect(state.available).toEqual(["ref", "palantir"]);
    });

    it("preserves other state fields", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_NAME_SET,
        trajectoryName: "palantir",
        available: ["palantir"],
      });
      expect(state.showTrajectory).toBe(initialTrajectoryState.showTrajectory);
      expect(state.trajectoryType).toBe(initialTrajectoryState.trajectoryType);
    });

    it("falls back to existing available when not an array", () => {
      const prev = { ...initialTrajectoryState, available: ["existing"] };
      const state = trajectoryReducer(prev, {
        type: CAFE_TRAJECTORY_NAME_SET,
        trajectoryName: "new",
        available: null,
      });
      expect(state.available).toEqual(["existing"]);
    });
  });

  describe("CAFE_TRAJECTORY_VISIBILITY_SET", () => {
    it("toggles showTrajectory to true", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_VISIBILITY_SET,
        showTrajectory: true,
      });
      expect(state.showTrajectory).toBe(true);
    });

    it("toggles showTrajectory to false", () => {
      const prev = { ...initialTrajectoryState, showTrajectory: true };
      const state = trajectoryReducer(prev, {
        type: CAFE_TRAJECTORY_VISIBILITY_SET,
        showTrajectory: false,
      });
      expect(state.showTrajectory).toBe(false);
    });
  });

  describe("CAFE_TRAJECTORY_ANCHOR_SET", () => {
    it("sets anchor to true", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_ANCHOR_SET,
        anchorTrajectory: true,
      });
      expect(state.anchorTrajectory).toBe(true);
    });
  });

  describe("CAFE_TRAJECTORY_TYPE_SET", () => {
    it("changes trajectoryType", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_TYPE_SET,
        trajectoryType: "waypoint",
      });
      expect(state.trajectoryType).toBe("waypoint");
    });

    it("defaults to milestone", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_TYPE_SET,
      });
      expect(state.trajectoryType).toBe("milestone");
    });
  });

  describe("CAFE_TRAJECTORY_NODE_SIZE_SET", () => {
    it("updates node size", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_NODE_SIZE_SET,
        nodeSize: 5.5,
      });
      expect(state.nodeSize).toBe(5.5);
    });
  });

  describe("CAFE_TRAJECTORY_EDGE_WIDTH_SET", () => {
    it("updates edge width", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_EDGE_WIDTH_SET,
        edgeWidth: 3,
      });
      expect(state.edgeWidth).toBe(3);
    });
  });

  describe("CAFE_TRAJECTORY_UPDATE (patch)", () => {
    it("patches top-level trajectory fields", () => {
      const state = trajectoryReducer(undefined, {
        type: CAFE_TRAJECTORY_UPDATE,
        patch: { showTrajectory: true, nodeSize: 4 },
      });
      expect(state.showTrajectory).toBe(true);
      expect(state.nodeSize).toBe(4);
    });

    it("patches from nested trajectory object", () => {
      const prev = { ...initialTrajectoryState, showTrajectory: true };
      const state = trajectoryReducer(prev, {
        type: CAFE_TRAJECTORY_UPDATE,
        patch: { trajectory: { showTrajectory: false } },
      });
      expect(state.showTrajectory).toBe(false);
    });

    it("ignores null patch", () => {
      const prev = trajectoryReducer(undefined, { type: "@@INIT" });
      const state = trajectoryReducer(prev, {
        type: CAFE_TRAJECTORY_UPDATE,
        patch: null,
      });
      expect(state).toBe(prev);
    });

    it("ignores string patch", () => {
      const prev = trajectoryReducer(undefined, { type: "@@INIT" });
      const state = trajectoryReducer(prev, {
        type: CAFE_TRAJECTORY_UPDATE,
        patch: "invalid",
      });
      expect(state).toBe(prev);
    });
  });
});
