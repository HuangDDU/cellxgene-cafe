import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";

import { AppContext } from "../../../src/lib/appProvider";
import StaticPanel from "../../../src/components/plot/StaticPanel";

jest.mock(
  "../../../src/lib/api",
  () => ({
    buildStaticPlotUrl: jest.fn(
      (params) =>
        `/mock/plot/static?view=${params.view}&trajectory=${params.trajectory}&layout=${params.layout}&t=${params.t}`,
    ),
  }),
);

// Access the mock for assertions
const apiMock = require("../../../src/lib/api");

function renderWithContext(overrides = {}) {
  const state = {
    trajectory: {
      trajectoryName: "ref",
      showTrajectory: false,
      trajectoryType: "milestone",
      nodeSize: 2.5,
      edgeWidth: 1,
      ...overrides.trajectory,
    },
    cellxgene: {
      layoutChoice: {
        current: "umap",
        available: ["umap", "tsne"],
        currentDimNames: [],
        ...overrides.layoutChoice,
      },
    },
  };
  const contextValue = {
    bridgeState: {
      trajectory: state.trajectory,
      cellxgene: state.cellxgene,
    },
    context: {
      current: { trajectory: "ref", layout: "umap" },
      plot: { preview: { nodes: [], edges: [], waypointSegments: {} } },
      ...overrides.context,
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
        <StaticPanel />
      </AppContext.Provider>
    </Provider>,
  );
}

describe("StaticPanel", () => {
  it("renders the heading", () => {
    renderWithContext();
    expect(screen.getByText("Static")).toBeInTheDocument();
  });

  it("renders Trajectory button as active by default", () => {
    renderWithContext();
    const trajBtn = screen.getByText("Trajectory");
    expect(trajBtn.className).toContain("is-active");
  });

  it("switches active view on button click", () => {
    renderWithContext();
    const graphBtn = screen.getByText("Graph");
    fireEvent.click(graphBtn);
    expect(graphBtn.className).toContain("is-active");
  });

  it("renders Stream view button", () => {
    renderWithContext();
    expect(screen.getByText("Stream")).toBeInTheDocument();
  });

  it("renders a refresh button", () => {
    renderWithContext();
    expect(screen.getByText("Refresh")).toBeInTheDocument();
  });

  it("renders an image with a plot URL", () => {
    renderWithContext();
    const img = screen.getByAltText("Static");
    expect(img).toBeInTheDocument();
    expect(img.src).toContain("/mock/plot/static");
    expect(img.src).toContain("view=trajectory");
  });

  it("image URL updates when switching view", () => {
    renderWithContext();
    const graphBtn = screen.getByText("Graph");
    fireEvent.click(graphBtn);
    const img = screen.getByAltText("Static");
    expect(img.src).toContain("view=graph");
  });
});
