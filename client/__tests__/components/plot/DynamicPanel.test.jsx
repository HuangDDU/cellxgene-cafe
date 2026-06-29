import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";

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
  const state = {
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
  };
  const contextValue = {
    bridgeState: {
      trajectory: state.trajectory,
      cellxgene: state.cellxgene,
    },
    context: {
      current: { trajectory: "ref", layout: "umap" },
      trajectories: ["ref", "palantir"],
      layouts: ["umap", "tsne"],
    },
  };
  const store = {
    getState: () => state,
    subscribe: () => () => {},
    dispatch: jest.fn(),
  };

  return render(
    <Provider store={store}>
      <AppContext.Provider value={contextValue}>
        <DynamicPanel />
      </AppContext.Provider>
    </Provider>,
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

  it("places Show toggle on the same row as the note text", () => {
    renderWithContext();
    const row = screen.getByText(/Display trajectory dynamically on cellxgene main panel/).closest(".cafe-dynamics-note-row");
    expect(row).toBeInTheDocument();
    expect(row).toContainElement(screen.getByText("Show"));
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
