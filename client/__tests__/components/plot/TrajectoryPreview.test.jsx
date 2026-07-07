import "@testing-library/jest-dom";
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "react-redux";

import TrajectoryPreview from "../../../src/components/plot/DynamicPanel/TrajectoryPreview";

function renderWithState(overrides = {}) {
  const state = {
    trajectory: {
      trajectoryType: "milestone",
      nodeSize: 2.5,
      edgeWidth: 1,
      preview: {
        nodes: [
          { id: "M1", label: "M1", x: 0.2, y: 0.3 },
          { id: "M2", label: "M2", x: 0.8, y: 0.7 },
        ],
        edges: [{ id: "M1-M2", source: "M1", target: "M2" }],
        waypointSegments: {},
      },
      ...overrides.trajectory,
    },
  };
  const store = {
    getState: () => state,
    subscribe: () => () => {},
    dispatch: jest.fn(),
  };

  return render(
    <Provider store={store}>
      <TrajectoryPreview />
    </Provider>,
  );
}

describe("TrajectoryPreview", () => {
  it("collapses and expands the preview body from the heading button", () => {
    const { container } = renderWithState();
    const toggle = screen.getByRole("button", { name: /Trajectory Preview/ });

    expect(container.querySelector("svg")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector("svg")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
