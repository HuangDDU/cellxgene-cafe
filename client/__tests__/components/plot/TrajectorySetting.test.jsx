import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import { AppContext } from "../../../src/lib/appProvider";
import TrajectorySetting from "../../../src/components/plot/DynamicPanel/TrajectorySetting";

jest.mock("../../../src/lib/hostBridge", () => ({
  dispatchCafeAction: jest.fn(),
}));

const { dispatchCafeAction } = require("../../../src/lib/hostBridge");

function renderWithContext(overrides = {}) {
  const contextValue = {
    bridgeState: {
      trajectory: {
        trajectoryName: "ref",
        available: ["ref", "palantir"],
        showTrajectory: false,
        trajectoryType: "milestone",
        nodeSize: 2.5,
        edgeWidth: 1,
        ...overrides.trajectory,
      },
      cellxgene: {
        layoutChoice: {
          current: "umap",
          available: ["umap", "tsne", "pca"],
          currentDimNames: ["UMAP_1", "UMAP_2"],
          ...overrides.layoutChoice,
        },
      },
    },
    context: {
      current: { trajectory: "ref", layout: "umap" },
      trajectories: ["ref", "palantir"],
      layouts: ["umap", "tsne", "pca"],
      ...overrides.context,
    },
  };

  return render(
    <AppContext.Provider value={contextValue}>
      <TrajectorySetting />
    </AppContext.Provider>,
  );
}

describe("TrajectorySetting", () => {
  beforeEach(() => {
    dispatchCafeAction.mockClear();
  });

  it("renders the heading", () => {
    renderWithContext();
    expect(screen.getByText("Trajectory Setting")).toBeInTheDocument();
  });

  describe("Method/Trajectory dropdown", () => {
    it("renders with current trajectory selected", () => {
      renderWithContext();
      const select = screen.getByLabelText("Method / Trajectory");
      expect(select.value).toBe("ref");
    });

    it("shows all trajectory options", () => {
      renderWithContext();
      const options = screen.getAllByRole("option");
      const values = options.map((o) => o.value);
      expect(values).toContain("ref");
      expect(values).toContain("palantir");
    });

    it("dispatches setCafeTrajectoryName on change", () => {
      renderWithContext();
      const select = screen.getByLabelText("Method / Trajectory");
      fireEvent.change(select, { target: { value: "palantir" } });
      expect(dispatchCafeAction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "cafe/trajectory/name/set",
          trajectoryName: "palantir",
        }),
      );
    });
  });

  describe("Embedding Layout dropdown", () => {
    it("renders with current layout selected", () => {
      renderWithContext();
      const select = screen.getByLabelText("Embedding Layout");
      expect(select.value).toBe("umap");
    });

    it("dispatches setCellxgeneLayoutChoice on change", () => {
      renderWithContext();
      const select = screen.getByLabelText("Embedding Layout");
      fireEvent.change(select, { target: { value: "tsne" } });
      expect(dispatchCafeAction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "cellxgene/layoutChoice/set",
          layoutChoice: "tsne",
        }),
      );
    });
  });

  describe("Plot Mode radios", () => {
    it("milestone is checked by default", () => {
      renderWithContext();
      const milestoneRadio = screen.getByLabelText(/milestone/);
      expect(milestoneRadio).toBeChecked();
    });

    it("waypoint is unchecked by default", () => {
      renderWithContext();
      const waypointRadios = screen.getAllByRole("radio");
      const waypointRadio = waypointRadios.find((r) => r.value === "on" && !r.checked);
      expect(waypointRadio).not.toBeChecked();
    });

    it("dispatches setCafeTrajectoryType on waypoint click", () => {
      renderWithContext();
      const waypointLabel = screen.getByText(/waypoint/);
      fireEvent.click(waypointLabel);
      expect(dispatchCafeAction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "cafe/trajectory/type",
          trajectoryType: "waypoint",
        }),
      );
    });
  });

  describe("Node size slider", () => {
    it("renders with default value 2.5", () => {
      renderWithContext();
      const slider = screen.getByLabelText("Milestone node size");
      expect(slider.value).toBe("2.5");
    });

    it("dispatches setCafeTrajectoryNodeSize on change", () => {
      renderWithContext();
      const slider = screen.getByLabelText("Milestone node size");
      fireEvent.change(slider, { target: { value: "5.5" } });
      expect(dispatchCafeAction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "cafe/trajectory/nodeSize",
          nodeSize: 5.5,
        }),
      );
    });
  });

  describe("Edge width slider", () => {
    it("renders with default value 1", () => {
      renderWithContext();
      const slider = screen.getByLabelText("Milestone edge width");
      expect(slider.value).toBe("1");
    });

    it("dispatches setCafeTrajectoryEdgeWidth on change", () => {
      renderWithContext();
      const slider = screen.getByLabelText("Milestone edge width");
      fireEvent.change(slider, { target: { value: "3" } });
      expect(dispatchCafeAction).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "cafe/trajectory/edgeWidth",
          edgeWidth: 3,
        }),
      );
    });
  });
});
