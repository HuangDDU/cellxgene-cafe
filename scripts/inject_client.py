import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
HOST_DIR = Path(os.environ.get("CELLXGENE_HOST_ROOT", str(BASE_DIR.parent / "cellxgene"))).resolve()
TARGET_FILES = [
  HOST_DIR / "client/index_template.html",
  HOST_DIR / "server/common/web/templates/index.html",
]

INJECTION_HTML = """
<!-- CAFE-PLUGIN-INJECTION START -->
<link href="https://cdn.jsdelivr.net/npm/jspanel4@4.16.1/dist/jspanel.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/jspanel4@4.16.1/dist/jspanel.min.js"></script>
<script src="static/cafe-plugin.js?v=20260424-plotfix"></script>
<script>
(function () {
  const launcherId = "cafe-plugin-launcher";
  const panelId = "cafe-plugin-panel";
  const rootId = "cafe-plugin-root";
  const overlayRootId = "cafe-host-trajectory-overlay";
  const hostBridgeEvent = "cafe:hostbridge:state";
  const trajectoryUpdateEvent = "cafe:trajectory:update";
  function defaultBridgeState() {
    return {
      layoutChoice: { current: "" },
      trajectoryChoice: { current: "", available: [] },
      trajectory: {
        showTrajectory: false,
        anchorTrajectory: false,
        trajectoryType: "milestone",
        nodeSize: 2.5,
        edgeWidth: 1
      }
    };
  }

  const bridgeState = defaultBridgeState();
  const bridgeListeners = new Set();
  let bridgeContext = null;
  let currentFetchId = 0;
  let layoutObserver = null;
  let graphPollHandle = null;
  let overlayImageSignature = "";

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function notifyBridge() {
    const snapshot = deepClone(bridgeState);
    bridgeListeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch (error) {
        console.error("CAFE host bridge listener failed.", error);
      }
    });
    window.dispatchEvent(new CustomEvent(hostBridgeEvent, { detail: snapshot }));
  }

  function normalizeLayoutName(value) {
    const text = String(value || "").trim();
    if (!text) {
      return "";
    }
    const compact = text
      .split(/[:：]/)[0]
      .trim()
      .split(/\\s+/)[0]
      .trim();
    if (!compact) {
      return "";
    }
    return compact.startsWith("X_") ? compact.slice(2) : compact;
  }

  function hostLayoutChoice() {
    const button = document.querySelector('[data-testid="layout-choice"]');
    if (!button) {
      return "";
    }
    const text = String(button.textContent || "").trim();
    if (!text) {
      return "";
    }
    return normalizeLayoutName(text);
  }

  function syncHostLayoutChoice() {
    const nextLayout = hostLayoutChoice();
    if (!nextLayout || bridgeState.layoutChoice.current === nextLayout) {
      return false;
    }
    bridgeState.layoutChoice.current = nextLayout;
    return true;
  }

  function applyBridgePatch(patch) {
    if (!patch || typeof patch !== "object") {
      return;
    }

    if (patch.trajectoryChoice !== undefined) {
      if (typeof patch.trajectoryChoice === "string") {
        bridgeState.trajectoryChoice.current = patch.trajectoryChoice;
      } else if (patch.trajectoryChoice && typeof patch.trajectoryChoice === "object") {
        bridgeState.trajectoryChoice = {
          ...bridgeState.trajectoryChoice,
          ...patch.trajectoryChoice
        };
      }
    }

    if (patch.layoutChoice !== undefined) {
      if (typeof patch.layoutChoice === "string") {
        bridgeState.layoutChoice.current = normalizeLayoutName(patch.layoutChoice);
      } else if (patch.layoutChoice && typeof patch.layoutChoice === "object") {
        bridgeState.layoutChoice = {
          ...bridgeState.layoutChoice,
          ...patch.layoutChoice,
          current: normalizeLayoutName(patch.layoutChoice.current || bridgeState.layoutChoice.current)
        };
      }
    }

    bridgeState.trajectory = {
      ...bridgeState.trajectory,
      ...Object.fromEntries(
        Object.entries(patch).filter(([key]) =>
          ["showTrajectory", "anchorTrajectory", "trajectoryType", "nodeSize", "edgeWidth"].includes(key)
        )
      )
    };
  }

  function apiUrl(path, params) {
    const query = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      const text = String(value || "").trim();
      if (text) {
        query.set(key, text);
      }
    });
    const suffix = query.toString();
    return suffix ? `/api/cafe${path}?${suffix}` : `/api/cafe${path}`;
  }

  function ensureOverlayRoot() {
    const modelGroup = document.getElementById("model-transformation-group");
    const svgRoot = modelGroup && modelGroup.ownerSVGElement ? modelGroup.ownerSVGElement : null;
    if (!modelGroup || !svgRoot) {
      return null;
    }
    let overlayRoot = document.getElementById(overlayRootId);
    if (!overlayRoot || overlayRoot.parentNode !== document.body) {
      if (overlayRoot && overlayRoot.parentNode) {
        overlayRoot.parentNode.removeChild(overlayRoot);
      }
      overlayRoot = document.createElement("img");
      overlayRoot.setAttribute("id", overlayRootId);
      overlayRoot.setAttribute("alt", "CAFE trajectory overlay");
      overlayRoot.style.position = "fixed";
      overlayRoot.style.left = "0";
      overlayRoot.style.top = "0";
      overlayRoot.style.width = "0";
      overlayRoot.style.height = "0";
      overlayRoot.style.objectFit = "fill";
      overlayRoot.style.objectPosition = "center center";
      overlayRoot.style.pointerEvents = "none";
      overlayRoot.style.zIndex = "30";
      overlayRoot.style.display = "none";
      overlayRoot.onload = function () {
        updateOverlayFrame(overlayRoot, modelGroup, svgRoot);
        const rect = overlayRoot.getBoundingClientRect();
        console.debug("CAFE overlay image loaded", {
          src: overlayRoot.currentSrc || overlayRoot.src,
          width: rect.width,
          height: rect.height,
          naturalWidth: overlayRoot.naturalWidth,
          naturalHeight: overlayRoot.naturalHeight
        });
      };
      overlayRoot.onerror = function () {
        console.error("CAFE overlay image failed to load", {
          src: overlayRoot.currentSrc || overlayRoot.src
        });
      };
      document.body.appendChild(overlayRoot);
    }
    updateOverlayFrame(overlayRoot, modelGroup, svgRoot);
    return overlayRoot;
  }

  function updateOverlayFrame(overlayRoot, modelGroup, svgRoot) {
    if (!overlayRoot || !modelGroup || !svgRoot) {
      return;
    }
    let rect = modelGroup.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      rect = svgRoot.getBoundingClientRect();
    }
    overlayRoot.style.left = rect.left + "px";
    overlayRoot.style.top = rect.top + "px";
    overlayRoot.style.width = rect.width + "px";
    overlayRoot.style.height = rect.height + "px";
  }

  function clearOverlay() {
    const overlayRoot = ensureOverlayRoot();
    if (!overlayRoot) {
      return;
    }
    overlayRoot.removeAttribute("src");
    overlayRoot.style.display = "none";
  }

  function asFiniteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function normalizePreviewData(preview) {
    const nodes = Array.isArray(preview?.nodes) ? preview.nodes : [];
    const edges = Array.isArray(preview?.edges) ? preview.edges : [];
    const waypointSegments = preview?.waypointSegments || {};
    return {
      nodes: nodes
        .map((node) => ({
          id: String(node?.id || ""),
          x: asFiniteNumber(node?.x),
          y: asFiniteNumber(node?.y),
          color: node?.color || "#9aa7b0"
        }))
        .filter((node) => node.id && node.x !== null && node.y !== null),
      edges: edges
        .map((edge) => ({
          id: String(edge?.id || ""),
          source: String(edge?.source || ""),
          target: String(edge?.target || "")
        }))
        .filter((edge) => edge.source && edge.target),
      waypointSegments: Object.fromEntries(
        Object.entries(waypointSegments).map(([groupId, points]) => [
          groupId,
          (Array.isArray(points) ? points : [])
            .map((point) => ({
              x: asFiniteNumber(point?.x),
              y: asFiniteNumber(point?.y),
              percentage: asFiniteNumber(point?.percentage) ?? 0
            }))
            .filter((point) => point.x !== null && point.y !== null)
        ])
      )
    };
  }

  function normalizeOverlayData(overlaySpec) {
    const milestonePositions = Array.isArray(overlaySpec?.milestonePositions) ? overlaySpec.milestonePositions : [];
    const wpSegments = Array.isArray(overlaySpec?.wpSegments) ? overlaySpec.wpSegments : [];

    const nodesById = new Map();
    milestonePositions.forEach((item) => {
      const milestoneId = String(item?.milestone_id || "");
      const x = asFiniteNumber(item?.comp_1);
      const y = asFiniteNumber(item?.comp_2);
      if (!milestoneId || x === null || y === null || nodesById.has(milestoneId)) {
        return;
      }
      nodesById.set(milestoneId, {
        id: milestoneId,
        x,
        y,
        color: "#9aa7b0"
      });
    });

    const edgesById = new Map();
    milestonePositions.forEach((item) => {
      const source = String(item?.from || "");
      const target = String(item?.to || "");
      const edgeId = String(item?.group || `${source}---${target}`);
      if (!source || !target || !edgeId) {
        return;
      }
      if (!nodesById.has(source) || !nodesById.has(target)) {
        return;
      }
      if (!edgesById.has(edgeId)) {
        edgesById.set(edgeId, { id: edgeId, source, target });
      }
    });

    const waypointSegments = {};
    wpSegments.forEach((item) => {
      const groupId = String(item?.group || "");
      const x = asFiniteNumber(item?.comp_1);
      const y = asFiniteNumber(item?.comp_2);
      if (!groupId || x === null || y === null) {
        return;
      }
      if (!waypointSegments[groupId]) {
        waypointSegments[groupId] = [];
      }
      waypointSegments[groupId].push({
        x,
        y,
        percentage: asFiniteNumber(item?.percentage) ?? 0
      });
    });

    Object.values(waypointSegments).forEach((points) => {
      points.sort((left, right) => Number(right.percentage || 0) - Number(left.percentage || 0));
    });

    return {
      nodes: Array.from(nodesById.values()),
      edges: Array.from(edgesById.values()),
      waypointSegments
    };
  }

  function renderOverlay() {
    const overlayRoot = ensureOverlayRoot();
    if (!overlayRoot) {
      console.debug("CAFE overlay: graph host container is unavailable.");
      return;
    }

    if (!bridgeState.trajectory.showTrajectory) {
      overlayRoot.style.display = "none";
      overlayImageSignature = "";
      console.debug("CAFE overlay: hidden", {
        showTrajectory: bridgeState.trajectory.showTrajectory,
        hasPreview: !!bridgeContext?.plot?.preview,
        hasOverlaySpec: !!bridgeContext?.plot?.overlaySpec
      });
      return;
    }

    const trajectoryId = String(bridgeState.trajectoryChoice.current || bridgeContext?.current?.trajectory || "").trim();
    const layoutId = normalizeLayoutName(bridgeState.layoutChoice.current || bridgeContext?.current?.layout || "");
    if (!trajectoryId || !layoutId) {
      overlayRoot.style.display = "none";
      overlayImageSignature = "";
      console.debug("CAFE overlay: missing trajectory or layout for overlay image.", {
        trajectoryId,
        layoutId
      });
      return;
    }

    overlayRoot.style.display = "";
    const signature = JSON.stringify({
      trajectory: trajectoryId,
      layout: layoutId,
      show: !!bridgeState.trajectory.showTrajectory
    });
    if (overlayImageSignature !== signature) {
      const imageUrl = apiUrl("/plot/static", {
        view: "trajectory",
        trajectory: trajectoryId,
        layout: layoutId,
        overlay: "1",
        t: String(Date.now())
      });
      overlayRoot.src = imageUrl;
      overlayImageSignature = signature;
    }
    overlayRoot.style.display = "";
    console.debug("CAFE overlay: rendering", {
      trajectory: trajectoryId,
      layout: layoutId,
      type: "cafe.plot overlay image",
      signature
    });
  }

  async function refreshOverlayContext() {
    const fetchId = ++currentFetchId;
    const params = {
      trajectory: bridgeState.trajectoryChoice.current || "",
      layout: normalizeLayoutName(bridgeState.layoutChoice.current || hostLayoutChoice())
    };
    try {
      const response = await fetch(apiUrl("/context", params), { credentials: "same-origin" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      if (fetchId !== currentFetchId) {
        return;
      }
      console.debug("CAFE overlay context loaded", payload);
      bridgeContext = payload;
      bridgeState.trajectoryChoice.available = Array.isArray(payload.trajectories) ? payload.trajectories : [];
      if (!bridgeState.trajectoryChoice.current) {
        bridgeState.trajectoryChoice.current = payload?.current?.trajectory || "";
      }
      if (!bridgeState.layoutChoice.current) {
        bridgeState.layoutChoice.current = normalizeLayoutName(payload?.current?.layout || "");
      }
      notifyBridge();
      renderOverlay();
    } catch (error) {
      console.error("Failed to refresh CAFE overlay context.", error);
      if (fetchId === currentFetchId) {
        bridgeContext = null;
        clearOverlay();
      }
    }
  }

  function updateBridge(patch) {
    const before = JSON.stringify(bridgeState);
    applyBridgePatch(patch);
    syncHostLayoutChoice();
    notifyBridge();
    renderOverlay();
    if (JSON.stringify(bridgeState) !== before || !bridgeContext) {
      refreshOverlayContext();
    }
  }

  function watchHostLayoutChoice() {
    const button = document.querySelector('[data-testid="layout-choice"]');
    if (!button) {
      return;
    }
    if (layoutObserver) {
      layoutObserver.disconnect();
    }
    layoutObserver = new MutationObserver(() => {
      if (syncHostLayoutChoice()) {
        refreshOverlayContext();
      }
    });
    layoutObserver.observe(button, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  function startGraphPolling() {
    if (graphPollHandle) {
      window.clearInterval(graphPollHandle);
    }
    graphPollHandle = window.setInterval(() => {
      watchHostLayoutChoice();
      renderOverlay();
    }, 1200);
  }

  window.CafeHostBridge = {
    getState: function () {
      syncHostLayoutChoice();
      return deepClone(bridgeState);
    },
    subscribe: function (listener) {
      if (typeof listener !== "function") {
        return function () {};
      }
      bridgeListeners.add(listener);
      try {
        listener(deepClone(bridgeState));
      } catch (error) {
        console.error("CAFE host bridge initial listener call failed.", error);
      }
      return function () {
        bridgeListeners.delete(listener);
      };
    },
    updateTrajectory: function (patch) {
      updateBridge(patch || {});
    }
  };

  window.addEventListener(trajectoryUpdateEvent, function (event) {
    const patch = event && event.detail ? event.detail : {};
    console.debug("CAFE overlay: received trajectory update event", patch);
    updateBridge(patch);
  });

  function mountCafePlugin() {
    if (window.CafePlugin && typeof window.CafePlugin.mount === "function") {
      window.CafePlugin.mount(rootId);
    } else if (window.mountCafeApp) {
      window.mountCafeApp(rootId);
    } else {
      console.error("CAFE plugin bundle loaded but mount function is missing.");
    }
  }

  function openPanel() {
    if (!window.jsPanel) {
      console.error("jsPanel is not loaded.");
      return;
    }

    const existing = document.getElementById(panelId);
    if (existing && existing.jspanel) {
      existing.jspanel.front();
      return;
    }

    window.jsPanel.create({
      id: panelId,
      headerTitle: "CAFE Plugins",
      theme: "primary",
      contentSize: "780 640",
      position: "center-top 0 64",
      content: '<div id="' + rootId + '" style="height:100%;overflow:auto;"></div>',
      callback: mountCafePlugin,
      onclosed: function () {
        if (window.CafePlugin && typeof window.CafePlugin.unmount === "function") {
          window.CafePlugin.unmount(rootId);
        }
      }
    });
  }

  function ensureLauncherButton() {
    if (document.getElementById(launcherId)) {
      return;
    }

    const button = document.createElement("button");
    button.id = launcherId;
    button.type = "button";
    button.textContent = "Cafe Plugins";
    button.style.position = "fixed";
    button.style.right = "14px";
    button.style.bottom = "16px";
    button.style.zIndex = "9999";
    button.style.padding = "6px 10px";
    button.style.border = "1px solid #6a8fb2";
    button.style.borderRadius = "4px";
    button.style.background = "#2f6f9f";
    button.style.color = "#fff";
    button.style.cursor = "pointer";
    button.title = "Open CAFE plugin window";
    button.addEventListener("click", openPanel);
    document.body.appendChild(button);
  }

  window.openCafePluginPanel = openPanel;
  window.addEventListener("load", function () {
    syncHostLayoutChoice();
    watchHostLayoutChoice();
    startGraphPolling();
    refreshOverlayContext();
    setTimeout(ensureLauncherButton, 700);
  });
})();
</script>
<!-- CAFE-PLUGIN-INJECTION END -->
"""

INJECTION_BLOCK_PATTERN = re.compile(
  r"<!-- CAFE-PLUGIN-INJECTION START -->.*?<!-- CAFE-PLUGIN-INJECTION END -->",
  re.DOTALL,
)


def inject_html(target_file: Path) -> None:
    if not target_file.exists():
        print(f"Skip missing file: {target_file}")
        return

    content = target_file.read_text(encoding="utf-8")
    if "CAFE-PLUGIN-INJECTION" in content:
      updated = INJECTION_BLOCK_PATTERN.sub(lambda _match: INJECTION_HTML.strip(), content, count=1)
      if updated != content:
        target_file.write_text(updated, encoding="utf-8")
        print(f"Updated injection: {target_file}")
      else:
        print(f"Injection marker found but unchanged: {target_file}")
      return

    if "</body>" not in content:
        raise RuntimeError(f"Cannot find </body> in {target_file}")

    updated = content.replace("</body>", f"{INJECTION_HTML}\n</body>", 1)
    target_file.write_text(updated, encoding="utf-8")
    print(f"Injected: {target_file}")


def main() -> None:
    for target in TARGET_FILES:
        inject_html(target)


if __name__ == "__main__":
    main()
