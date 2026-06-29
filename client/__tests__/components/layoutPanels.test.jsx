import "@testing-library/jest-dom";
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import { Provider } from "react-redux";

import Data from "../../src/components/data";
import Explorer from "../../src/components/explorer";
import Method from "../../src/components/method";
import Plot from "../../src/components/plot";
import Agent from "../../src/components/agent";
import {
  fetchCafeCache,
  fetchDataSummary,
  fetchExplorerSummary,
  fetchMethodCatalog,
} from "../__mocks__/api";

jest.mock("../../src/lib/api", () => require("../__mocks__/api"));

jest.mock("../../src/components/plot/DynamicPanel", () => () => <div>Dynamics</div>);
jest.mock("../../src/components/plot/StaticPanel", () => () => <div>Static</div>);

function renderWithStore(ui, overrides = {}) {
  const state = {
    context: { manifest: { version: "test" } },
    trajectory: {
      trajectoryName: "ref",
      available: ["ref"],
      trajectoryType: "milestone",
      showTrajectory: true,
    },
    cellxgene: { layoutChoice: { current: "umap" } },
    ...overrides,
  };
  const store = {
    getState: () => state,
    subscribe: () => () => {},
    dispatch: jest.fn(),
  };
  return render(<Provider store={store}>{ui}</Provider>);
}

describe("module layout panels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not render the Plot Current Selection panel", () => {
    renderWithStore(<Plot />);
    expect(screen.queryByText("Current Selection")).not.toBeInTheDocument();
    expect(screen.getByText("Dynamics")).toBeInTheDocument();
    expect(screen.getByText("Static")).toBeInTheDocument();
  });

  it("does not render the Data Dataset Overview panel", async () => {
    fetchDataSummary.mockResolvedValue({
      dataset: {},
      fateAnnData: {},
      trajectories: [],
      exports: {},
      embeddings: {},
      colorMappings: [],
      source: {},
    });
    fetchCafeCache.mockResolvedValue({ cacheDir: "", subdirs: {}, trajFiles: [] });

    renderWithStore(<Data />);

    await waitFor(() => expect(screen.getByText("Prior Knowledge")).toBeInTheDocument());
    expect(screen.queryByText("Dataset Overview")).not.toBeInTheDocument();
  });

  it("renders Method sections as collapsible cards with organized parameter groups", async () => {
    fetchMethodCatalog.mockResolvedValue({
      methods: [{
        key: "slingshot",
        label: "Slingshot",
        description: "Infer lineages",
        status: "ready",
        defaultRuntime: "python",
        availableRuntimes: [{ key: "python", label: "Python" }],
        schema: [
          { name: "cluster_key", label: "Cluster key", inputKind: "text", required: true },
          { name: "allow_breaks", label: "Allow breaks", inputKind: "boolean", default: false },
        ],
      }],
    });

    renderWithStore(<Method />);

    await waitFor(() => expect(screen.getByText("Method")).toBeInTheDocument());
    const parameterCard = screen.getByText("Parameters").closest(".cafe-card");

    expect(screen.getAllByText(/[▾▸]/).length).toBeGreaterThanOrEqual(2);
    expect(within(parameterCard).getAllByText("Runtime").length).toBeGreaterThanOrEqual(1);
    expect(within(parameterCard).getByText("Method Parameters")).toBeInTheDocument();
    expect(within(parameterCard).getByLabelText("Cluster key *")).toBeInTheDocument();
  });

  it("renders Explorer as three compact collapsible modules without redundant overview tabs", async () => {
    fetchExplorerSummary.mockResolvedValue({
      benchmark: {
        rows: [{ id: "ref", edge_flip: 1 }],
        metricKeys: ["edge_flip"],
      },
      driverGenes: {
        available: true,
        sourceKeys: ["drivers"],
        items: [{ trajectoryId: "ref", rank: 1, gene: "GATA3", score: 0.8, sourceKey: "drivers" }],
      },
      geneSelection: { matches: ["GATA3"] },
      geneTrends: {
        available: true,
        series: [{ trajectoryId: "ref", gene: "GATA3", points: [{ x: 0, y: 1 }, { x: 1, y: 2 }] }],
      },
      integrations: [{ key: "grn", label: "GRN", enabled: true, itemCount: 1, message: "ready", items: [] }],
    });

    renderWithStore(<Explorer active />);

    await waitFor(() => expect(screen.getByText("Benchmark")).toBeInTheDocument());
    expect(screen.queryByText("Explorer Overview")).not.toBeInTheDocument();
    expect(screen.queryByText("Explorer")).not.toBeInTheDocument();
    expect(screen.queryByText("Comparison")).not.toBeInTheDocument();
    expect(screen.queryByText("Trends")).not.toBeInTheDocument();
    expect(screen.queryByText("Drivers")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refresh" })).not.toBeInTheDocument();
    expect(screen.getByText("Driver Gene")).toBeInTheDocument();
    expect(screen.getByText("Integration")).toBeInTheDocument();
  });

  it("keeps Agent templates inside the Conversation panel", () => {
    renderWithStore(<Agent />);

    expect(screen.queryByText("Analysis Templates")).not.toBeInTheDocument();
    const conversationCard = screen.getByText("Conversation").closest(".cafe-card");
    expect(within(conversationCard).getByText("Trajectory Overview")).toBeInTheDocument();
    expect(within(conversationCard).getByText("Driver Gene Analysis")).toBeInTheDocument();
  });
});
