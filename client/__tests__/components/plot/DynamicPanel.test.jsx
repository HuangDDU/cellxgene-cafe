import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import { AppContext } from "../../../src/lib/appProvider";
import DynamicPanel from "../../../src/components/plot/DynamicPanel";

// Mock the dispatch to verify it is called with correct actions
jest.mock("../../../src/lib/hostBridge", () => ({
  dispatchCafeAction: jest.fn(),
}));

// Mock child components to isolate DynamicPanel
jest.mock("../../../src/components/plot/DynamicPanel/TrajectorySetting", () => () => (
  <div data-testid="trajectory-setting" />
));
jest.mock("../../../src/components/plot/DynamicPanel/TrajectoryPreview", () => () => (
  <div data-testid="trajectory-preview" />
));

const { dispatchCafeAction } = require("../../../src/lib/hostBridge");

function renderWithContext(bridgeStateOverrides = {}) {
  const contextValue = {
    bridgeState: {
      trajectory: {
        trajectoryName: "ref",
        available: ["ref"],
        showTrajectory: false,
        anchorTrajectory: false,
        trajectoryType: "milestone",
        nodeSize: 2.5,
        edgeWidth: 1,
        ...bridgeStateOverrides,
      },
      cellxgene: {
        layoutChoice: { current: "umap", available: [], currentDimNames: [] },
      },
    },
    context: {
      current: { trajectory: "ref", layout: "umap" },
      trajectories: ["ref", "palantir"],
      layouts: ["umap", "tsne"],
    },
  };

  return render(
    <AppContext.Provider value={contextValue}>
      <DynamicPanel />
    </AppContext.Provider>,
  );
}

describe("DynamicPanel", () => {
  beforeEach(() => {
    dispatchCafeAction.mockClear();
  });

  it("renders Dynamics header", () => {
    renderWithContext();
    expect(screen.getByText("Dynamics")).toBeInTheDocument();
  });

  it("renders the note text", () => {
    renderWithContext();
    expect(
      screen.getByText(/Display trajectory dynamically on cellxgene main panel/),
    ).toBeInTheDocument();
  });

  it("renders TrajectorySetting and TrajectoryPreview", () => {
    renderWithContext();
    expect(screen.getByTestId("trajectory-setting")).toBeInTheDocument();
    expect(screen.getByTestId("trajectory-preview")).toBeInTheDocument();
  });

  it("checkbox is unchecked when showTrajectory is false", () => {
    renderWithContext({ showTrajectory: false });
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).not.toBeChecked();
  });

  it("checkbox is checked when showTrajectory is true", () => {
    renderWithContext({ showTrajectory: true });
    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toBeChecked();
  });

  it("dispatches setCafeTrajectoryVisible(true) on check", () => {
    renderWithContext({ showTrajectory: false });
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(dispatchCafeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "cafe/trajectory/show",
        showTrajectory: true,
      }),
    );
  });

  it("dispatches setCafeTrajectoryVisible(false) on uncheck", () => {
    renderWithContext({ showTrajectory: true });
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(dispatchCafeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "cafe/trajectory/show",
        showTrajectory: false,
      }),
    );
  });
});
