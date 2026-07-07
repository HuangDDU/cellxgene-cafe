import fs from "fs";
import path from "path";

function loadDrawSVGTrajectory() {
  return loadScriptFunction("drawSVGTrajectory", "function renderOverlay");
}

function loadOverlayTargetFunctions() {
  const htmlPath = path.resolve(__dirname, "../../../scripts/inject_client.html");
  const html = fs.readFileSync(htmlPath, "utf8");
  const start = html.indexOf("function hostGraphTarget");
  const end = html.indexOf("function clearOverlay", start);
  if (start < 0 || end < 0) {
    throw new Error("Unable to extract host overlay target functions from inject_client.html");
  }
  const source = html.slice(start, end);
  return Function(`
    const overlayRootId = "cafe-host-trajectory-overlay";
    ${source};
    return { hostGraphTarget, ensureOverlayRoot };
  `)();
}

function loadScriptFunction(functionName, nextMarker) {
  const htmlPath = path.resolve(__dirname, "../../../scripts/inject_client.html");
  const html = fs.readFileSync(htmlPath, "utf8");
  const start = html.indexOf(`function ${functionName}`);
  const end = html.indexOf(nextMarker, start);
  if (start < 0 || end < 0) {
    throw new Error(`Unable to extract ${functionName} from inject_client.html`);
  }
  const source = html.slice(start, end);
  return Function(`${source}; return ${functionName};`)();
}

function loadRenderOverlayHarness(showTrajectory) {
  const htmlPath = path.resolve(__dirname, "../../../scripts/inject_client.html");
  const html = fs.readFileSync(htmlPath, "utf8");
  const start = html.indexOf("function renderOverlay");
  const end = html.indexOf("async function refreshOverlayContext", start);
  if (start < 0 || end < 0) {
    throw new Error("Unable to extract renderOverlay from inject_client.html");
  }
  const source = html.slice(start, end);
  const calls = { clear: 0, ensure: 0 };
  const renderOverlay = Function("calls", `
    const bridgeState = { trajectory: { showTrajectory: ${JSON.stringify(showTrajectory)}, trajectoryType: "milestone" } };
    const bridgeContext = { current: { trajectory: "scvelo", layout: "umap" }, plot: { preview: {} } };
    let overlayImageSignature = "";
    function clearOverlay() { calls.clear += 1; }
    function ensureOverlayRoot() {
      calls.ensure += 1;
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("width", "800");
      svg.setAttribute("height", "600");
      svg.style.display = "";
      return svg;
    }
    function hasVectorOverlayData() { return false; }
    function overlayStaticImageUrl() { return "/api/cafe/plot/static?overlay=1"; }
    function drawOverlayImage() {}
    function overlayDataSignature() { return "sig"; }
    function drawSVGTrajectory() {}
    ${source}
    return renderOverlay;
  `)(calls);
  return { calls, renderOverlay };
}

describe("host trajectory overlay", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
  });

  it("does not leave noisy debug logging in the injected host overlay script", () => {
    const htmlPath = path.resolve(__dirname, "../../../scripts/inject_client.html");
    const html = fs.readFileSync(htmlPath, "utf8");

    expect(html).not.toMatch(/console\.(log|debug)\(/);
  });

  it("does not scan the host graph while trajectory display is disabled", () => {
    const { calls, renderOverlay } = loadRenderOverlayHarness(false);

    renderOverlay();

    expect(calls.clear).toBe(1);
    expect(calls.ensure).toBe(0);
  });

  it("creates an overlay over the main graph canvas when the legacy svg group is absent", () => {
    const { ensureOverlayRoot } = loadOverlayTargetFunctions();
    const canvas = document.createElement("canvas");
    Object.defineProperty(canvas, "getBoundingClientRect", {
      value: () => ({ left: 10, top: 20, width: 800, height: 600 }),
    });
    document.body.appendChild(canvas);

    const overlay = ensureOverlayRoot();

    expect(overlay).not.toBeNull();
    expect(overlay.getAttribute("id")).toBe("cafe-host-trajectory-overlay");
    expect(overlay.style.left).toBe("10px");
    expect(overlay.style.top).toBe("20px");
    expect(overlay.getAttribute("width")).toBe("800");
    expect(overlay.getAttribute("height")).toBe("600");
  });

  it("draws normalized milestone coordinates in the host scatter coordinate frame", () => {
    const drawSVGTrajectory = loadDrawSVGTrajectory();
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");

    drawSVGTrajectory(svg, {
      nodes: [
        { id: "M1", x: 0.2, y: 0.3 },
        { id: "M2", x: 0.8, y: 0.7 },
      ],
      edges: [],
      waypointSegments: {},
    }, 1000, 500);

    const circles = Array.from(svg.querySelectorAll("circle"));
    expect(circles).toHaveLength(2);
    expect(Number(circles[0].getAttribute("cx"))).toBeCloseTo(200);
    expect(Number(circles[0].getAttribute("cy"))).toBeCloseTo(350);
    expect(Number(circles[1].getAttribute("cx"))).toBeCloseTo(800);
    expect(Number(circles[1].getAttribute("cy"))).toBeCloseTo(150);
  });

  it("changes the redraw signature when trajectory coordinates change", () => {
    const overlayDataSignature = loadScriptFunction("overlayDataSignature", "function drawSVGTrajectory");
    const first = overlayDataSignature({
      nodes: [{ id: "M1", x: 0.2, y: 0.3 }],
      edges: [],
      waypointSegments: {},
    }, "milestone", 1000, 500);
    const second = overlayDataSignature({
      nodes: [{ id: "M1", x: 0.7, y: 0.8 }],
      edges: [],
      waypointSegments: {},
    }, "milestone", 1000, 500);

    expect(first).not.toEqual(second);
  });

  it("detects waypoint-only previews as vector overlay data", () => {
    const hasVectorOverlayData = loadScriptFunction("hasVectorOverlayData", "function overlayStaticImageUrl");

    expect(hasVectorOverlayData({
      nodes: [],
      waypointSegments: { branch: [{ x: 0.1, y: 0.2 }, { x: 0.3, y: 0.4 }] },
    })).toBe(true);
    expect(hasVectorOverlayData({ nodes: [], waypointSegments: {} })).toBe(false);
  });

  it("builds a transparent static plot fallback URL when vector preview data is unavailable", () => {
    const htmlPath = path.resolve(__dirname, "../../../scripts/inject_client.html");
    const html = fs.readFileSync(htmlPath, "utf8");
    const start = html.indexOf("function apiUrl");
    const end = html.indexOf("function drawOverlayImage", start);
    if (start < 0 || end < 0) {
      throw new Error("Unable to extract static overlay URL helpers from inject_client.html");
    }
    const source = html.slice(start, end);
    const overlayStaticImageUrl = Function(`
      ${source};
      return overlayStaticImageUrl;
    `)();

    const url = overlayStaticImageUrl(
      { current: { trajectory: "scvelo", layout: "umap" } },
      { trajectoryChoice: { current: "" }, layoutChoice: { current: "" } },
    );

    expect(url).toContain("/api/cafe/plot/static?");
    expect(url).toContain("view=trajectory");
    expect(url).toContain("trajectory=scvelo");
    expect(url).toContain("layout=umap");
    expect(url).toContain("overlay=1");
  });
});
