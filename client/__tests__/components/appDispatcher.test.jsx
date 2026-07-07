import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("../../src/components/plot", () => () => <div>Plot Module</div>);
jest.mock("../../src/components/data", () => () => <div>Data Module</div>);
jest.mock("../../src/components/method", () => () => <div>Method Module</div>);
jest.mock("../../src/components/explorer", () => () => <div>Explorer Module</div>);
jest.mock("../../src/components/agent", () => () => <div>Agent Module</div>);

import { ModuleDispatcherBase } from "../../src/components/app";

describe("ModuleDispatcher", () => {
  it("mounts only the active tab module", () => {
    render(<ModuleDispatcherBase activeTab="plot" />);

    expect(screen.getByText("Plot Module")).toBeInTheDocument();
    expect(screen.queryByText("Data Module")).not.toBeInTheDocument();
    expect(screen.queryByText("Method Module")).not.toBeInTheDocument();
    expect(screen.queryByText("Explorer Module")).not.toBeInTheDocument();
    expect(screen.queryByText("Agent Module")).not.toBeInTheDocument();
  });
});
