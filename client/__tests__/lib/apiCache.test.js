describe("api module request cache", () => {
  let getMock;
  let postMock;

  beforeEach(() => {
    jest.resetModules();
    getMock = jest.fn();
    postMock = jest.fn();
    jest.doMock("axios", () => ({
      create: jest.fn(() => ({
        get: getMock,
        post: postMock,
      })),
    }));
  });

  afterEach(() => {
    jest.dontMock("axios");
  });

  it("deduplicates concurrent GET requests with the same cache key", async () => {
    getMock.mockResolvedValue({ data: { dataset: { name: "demo" } } });

    const { fetchDataSummary } = require("../../src/lib/api");
    const [first, second] = await Promise.all([
      fetchDataSummary(),
      fetchDataSummary(),
    ]);

    expect(getMock).toHaveBeenCalledTimes(1);
    expect(getMock).toHaveBeenCalledWith("/data/summary");
    expect(first).toEqual({ dataset: { name: "demo" } });
    expect(second).toBe(first);
  });

  it("prefetches first-click module data with a lightweight Explorer request", async () => {
    getMock.mockResolvedValue({ data: {} });

    const { prefetchModuleData } = require("../../src/lib/api");
    await prefetchModuleData({ trajectory: "ref", layout: "umap" });

    expect(getMock).toHaveBeenCalledWith("/data/summary");
    expect(getMock).toHaveBeenCalledWith("/data/cafe-cache");
    expect(getMock).toHaveBeenCalledWith("/method/catalog");
    expect(getMock).toHaveBeenCalledWith("/explorer/summary", {
      params: {
        trajectory: "ref",
        layout: "umap",
        includeHeavy: "0",
      },
    });
  });
});
