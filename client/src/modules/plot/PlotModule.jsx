import React, { useEffect, useMemo, useState } from "react";

import { buildStaticPlotUrl, cancelMethodJob, queryMethodJob, submitMethodJob } from "../../lib/api";
import { applyTrajectoryPatch } from "../../lib/hostBridge";
import PreviewNetwork from "./PreviewNetwork";

function PlotModule({ context, bridgeState, onPatchPlotState, onRefreshContext }) {
  const plotState = bridgeState?.trajectory || {};
  const trajectoryChoice = bridgeState?.trajectoryChoice || {};
  const layoutChoice = bridgeState?.layoutChoice || {};

  const [staticView, setStaticView] = useState("trajectory");
  const [imageSeed, setImageSeed] = useState(0);
  const [imageFailed, setImageFailed] = useState(false);
  const [lazyJob, setLazyJob] = useState(null);
  const [lazyError, setLazyError] = useState("");
  const [pendingTrajectoryId, setPendingTrajectoryId] = useState("");

  const trajectoryOptions =
    context?.trajectoryOptions ||
    (context?.trajectories || []).map((item) => ({
      id: item,
      label: item,
      loaded: true,
      kind: "trajectory",
      defaultRuntime: "",
      availableRuntimes: [],
    }));
  const layoutOptions = context?.layouts || [];

  const currentTrajectory = pendingTrajectoryId || trajectoryChoice.current || context?.current?.trajectory || "";
  const currentLayout = layoutChoice.current || context?.current?.layout || "";
  const preview = context?.plot?.preview || { nodes: [], edges: [], waypointSegments: {} };
  const contextTrajectory = context?.current?.trajectory || "";
  const contextLayout = context?.current?.layout || "";
  const selectedTrajectoryOption = trajectoryOptions.find((item) => item.id === currentTrajectory) || null;
  const currentTrajectorySummary = context?.currentTrajectory || null;
  const currentEffectiveWrapperType = String(
    currentTrajectorySummary?.effectiveWrapperType || currentTrajectorySummary?.wrapperType || ""
  ).toLowerCase();
  const previewMatchesCurrentTrajectory = contextTrajectory === currentTrajectory;
  const staticImageReady = contextTrajectory === currentTrajectory && contextLayout === currentLayout;
  const staticTrajectory = staticImageReady ? currentTrajectory : contextTrajectory || currentTrajectory;
  const staticLayout = staticImageReady ? currentLayout : contextLayout || currentLayout;
  const effectivePreview = previewMatchesCurrentTrajectory
    ? preview
    : { nodes: [], edges: [], waypointSegments: {} };

  useEffect(() => {
    if (!lazyJob?.jobId) {
      return undefined;
    }
    if (!["queued", "running", "cancel_requested"].includes(lazyJob.status)) {
      return undefined;
    }

    let active = true;
    const poll = async () => {
      try {
        const snapshot = await queryMethodJob(lazyJob.jobId);
        if (!active) {
          return;
        }
        setLazyJob(snapshot);

        if (["completed", "succeeded"].includes(snapshot.status)) {
          const trajectoryId = snapshot?.result?.trajectoryId || snapshot?.trajectoryId || pendingTrajectoryId;
          setPendingTrajectoryId("");
          setLazyError("");
          await onRefreshContext({ trajectory: trajectoryId, layout: currentLayout });
          onPatchPlotState({ trajectoryChoice: trajectoryId });
          return;
        }

        if (snapshot.status === "failed") {
          setPendingTrajectoryId("");
          setLazyError(snapshot.error || "Method loading failed.");
          return;
        }

        if (snapshot.status === "cancelled") {
          setPendingTrajectoryId("");
          setLazyError("Method loading was cancelled.");
        }
      } catch (error) {
        if (!active) {
          return;
        }
        setPendingTrajectoryId("");
        setLazyError(error?.response?.data?.error || error?.message || "Failed to query method job.");
      }
    };

    poll();
    const timer = window.setInterval(poll, 1200);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [lazyJob?.jobId, lazyJob?.status, currentLayout, onPatchPlotState, onRefreshContext, pendingTrajectoryId]);

  const staticImageUrl = useMemo(
    () =>
      buildStaticPlotUrl({
        view: staticView,
        trajectory: staticTrajectory,
        layout: staticLayout,
        t: imageSeed,
      }),
    [staticView, staticTrajectory, staticLayout, imageSeed]
  );

  const previewImageView = "trajectory";

  const previewImageUrl = useMemo(
    () =>
      buildStaticPlotUrl({
        view: previewImageView,
        trajectory: currentTrajectory,
        layout: currentLayout,
        t: imageSeed,
      }),
    [previewImageView, currentTrajectory, currentLayout, imageSeed]
  );

  useEffect(() => {
    setImageFailed(false);
    setImageSeed((seed) => seed + 1);
  }, [currentTrajectory, currentLayout, staticView]);

  useEffect(() => {
    const patch = {};
    if (!trajectoryChoice.current && contextTrajectory) {
      patch.trajectoryChoice = contextTrajectory;
    }
    if (!layoutChoice.current && contextLayout) {
      patch.layoutChoice = contextLayout;
    }
    if (Object.keys(patch).length) {
      onPatchPlotState(patch);
    }
  }, [
    contextTrajectory,
    contextLayout,
    trajectoryChoice.current,
    layoutChoice.current,
    onPatchPlotState,
  ]);

  const previewFallbackLabel = useMemo(() => {
    const wrapperType = currentEffectiveWrapperType;
    if (wrapperType === "velocity") {
      return "Graph preview is unavailable for this velocity trajectory; showing trajectory preview image instead.";
    }
    if (currentTrajectory) {
      return "This trajectory does not expose a graph-style preview. Showing a generated image instead.";
    }
    return "";
  }, [currentEffectiveWrapperType, currentTrajectory]);

  const onTrajectoryChange = async (event) => {
    const value = event.target.value;
    const option = trajectoryOptions.find((item) => item.id === value);
    setLazyError("");

    if (!option) {
      onPatchPlotState({ trajectoryChoice: value });
      onRefreshContext({ trajectory: value, layout: currentLayout });
      return;
    }

    if (option.loaded) {
      setPendingTrajectoryId("");
      setLazyJob(null);
      onPatchPlotState({ trajectoryChoice: value });
      onRefreshContext({ trajectory: value, layout: currentLayout });
      return;
    }

    try {
      setPendingTrajectoryId(value);
      onPatchPlotState({ trajectoryChoice: value });
      const runtimeKey = option.defaultRuntime || option.availableRuntimes?.[0]?.key || "";
      const submitted = await submitMethodJob({
        methodName: option.id,
        backendName: runtimeKey,
        trajectoryId: option.id,
        parameters: {},
      });
      setLazyJob(submitted);
    } catch (error) {
      setPendingTrajectoryId("");
      setLazyJob(null);
      setLazyError(error?.response?.data?.error || error?.message || "Failed to start method loading.");
    }
  };

  const onLayoutChange = (event) => {
    const value = event.target.value;
    onPatchPlotState({ layoutChoice: value });
    onRefreshContext({ trajectory: currentTrajectory, layout: value });
  };

  const refreshStaticPlot = () => {
    setImageFailed(false);
    setImageSeed((seed) => seed + 1);
  };

  const cancelLazyLoad = async () => {
    if (!lazyJob?.jobId) {
      return;
    }
    try {
      const snapshot = await cancelMethodJob(lazyJob.jobId);
      setLazyJob(snapshot);
      setPendingTrajectoryId("");
    } catch (error) {
      setLazyError(error?.response?.data?.error || error?.message || "Failed to cancel method loading.");
    }
  };

  const lazyProgress = Math.max(0, Math.min(100, Number(lazyJob?.progress || 0)));
  const lazyStageText = lazyJob?.stage || lazyJob?.status || "";

  const patchDynamicsState = (patch) => {
    applyTrajectoryPatch(patch);
    onPatchPlotState(patch);
  };

  return (
    <div>
      <div className="cafe-card cafe-dynamics-card">
        <h4>Dynamics</h4>
        <div className="cafe-note" style={{ marginBottom: "10px" }}>
          在 Cellxgene 主面板上动态展示轨迹（和原本交互逻辑一致）。
        </div>

        <div className="cafe-dynamics-layout">
          <div className="cafe-dynamics-controls-panel">
            <div className="cafe-dynamics-control-grid">
              <div className="cafe-field">
                <label htmlFor="trajectory-method">Method / Trajectory</label>
                <select id="trajectory-method" value={currentTrajectory} onChange={onTrajectoryChange}>
                  {trajectoryOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.loaded ? item.label : `${item.label} (load)`}
                    </option>
                  ))}
                </select>
              </div>

              <div className="cafe-field">
                <label htmlFor="trajectory-layout">Embedding Layout</label>
                <select id="trajectory-layout" value={currentLayout} onChange={onLayoutChange}>
                  {layoutOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="cafe-switch-row cafe-dynamics-switches">
              <label>
                <input
                  type="checkbox"
                  checked={!!plotState.showTrajectory}
                  onChange={(event) => patchDynamicsState({ showTrajectory: event.target.checked })}
                />{" "}
                Show
              </label>

              <label>
                <input
                  type="checkbox"
                  checked={!!plotState.anchorTrajectory}
                  onChange={(event) => patchDynamicsState({ anchorTrajectory: event.target.checked })}
                />{" "}
                Anchor
              </label>

              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(plotState.trajectoryType || "milestone") === "milestone"}
                  onChange={() => patchDynamicsState({ trajectoryType: "milestone" })}
                />{" "}
                milestone
              </label>

              <label>
                <input
                  type="radio"
                  name="trajectoryType"
                  checked={(plotState.trajectoryType || "milestone") === "waypoint"}
                  onChange={() => patchDynamicsState({ trajectoryType: "waypoint" })}
                />{" "}
                waypoint
              </label>
            </div>

            <div className="cafe-dynamics-sliders">
              <div className="cafe-field">
                <label>Milestone node size: {Number(plotState.nodeSize ?? 2.5).toFixed(1)}</label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.1"
                  value={plotState.nodeSize ?? 2.5}
                  onChange={(event) => patchDynamicsState({ nodeSize: Number(event.target.value) })}
                />
              </div>

              <div className="cafe-field">
                <label>Milestone edge width: {Number(plotState.edgeWidth ?? 1).toFixed(1)}</label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.1"
                  value={plotState.edgeWidth ?? 1}
                  onChange={(event) => patchDynamicsState({ edgeWidth: Number(event.target.value) })}
                />
              </div>
            </div>

            <div className="cafe-dynamics-refresh-row">
              <button
                type="button"
                className="cafe-btn"
                onClick={() => onRefreshContext({ trajectory: currentTrajectory, layout: currentLayout })}
              >
                Refresh Plot Context
              </button>
              <span className="cafe-note">动态可视化会同步主面板轨迹绘制。</span>
            </div>

            {currentTrajectory ? (
              <div
                style={{
                  marginTop: "10px",
                  padding: "10px",
                  border: "1px solid #d8e1ec",
                  borderRadius: "6px",
                  background: "#f8fbff",
                }}
              >
                <div className="cafe-note">Current Trajectory: {currentTrajectory}</div>
                <div className="cafe-note">
                  Trajectory Type: {currentTrajectorySummary?.effectiveWrapperType || currentTrajectorySummary?.wrapperType || "unknown"}
                </div>
                <div className="cafe-note">Preview Mode: {previewImageView}</div>
                <div className="cafe-note">Static View: {staticView}</div>
              </div>
            ) : null}

            {selectedTrajectoryOption && !selectedTrajectoryOption.loaded ? (
              <div className="cafe-note" style={{ marginTop: "8px" }}>
                选中未加载的方法后，插件会按需运行该算法并在完成后并入 `trajectory_history_dict`。
              </div>
            ) : null}

            {lazyJob ? (
              <div
                style={{
                  marginTop: "12px",
                  padding: "10px",
                  border: "1px solid #d9d9d9",
                  borderRadius: "8px",
                  background: "#fafafa",
                }}
              >
                <div className="cafe-note" style={{ marginBottom: "6px" }}>
                  {lazyJob.trajectoryId || pendingTrajectoryId || "trajectory"}: {lazyStageText || "queued"}
                </div>
                <div
                  style={{
                    width: "100%",
                    height: "8px",
                    borderRadius: "999px",
                    background: "#e5e7eb",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${lazyProgress}%`,
                      height: "100%",
                      background: "#2d6cdf",
                      transition: "width 0.2s ease",
                    }}
                  />
                </div>
                <div
                  style={{
                    marginTop: "8px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "12px",
                  }}
                >
                  <span className="cafe-note">
                    {lazyJob.status} · {lazyProgress.toFixed(0)}%
                  </span>
                  {["queued", "running", "cancel_requested"].includes(lazyJob.status) ? (
                    <button type="button" className="cafe-btn cafe-btn-secondary" onClick={cancelLazyLoad}>
                      Cancel
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}

            {lazyError ? (
              <div className="cafe-error" style={{ marginTop: "10px" }}>
                {lazyError}
              </div>
            ) : null}
          </div>

          <div className="cafe-dynamics-preview-panel">
            <h4 className="cafe-subsection-title">Trajectory Preview</h4>
            <PreviewNetwork preview={effectivePreview} imageUrl={previewImageUrl} fallbackLabel={previewFallbackLabel} />
          </div>
        </div>
      </div>

      <div className="cafe-card">
        <h4>Static</h4>
        <div className="cafe-note" style={{ marginBottom: "10px" }}>
          后端分别调用 cafe.plot.plot_trajectory / cafe.plot.plot_graph / cafe.plot.plot_stream 并返回图片。
        </div>

        <div className="cafe-switch-row" style={{ marginBottom: "10px" }}>
          <span className="cafe-note">Static View:</span>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "trajectory" ? "is-active" : ""}`}
            onClick={() => setStaticView("trajectory")}
          >
            Trajectory
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "graph" ? "is-active" : ""}`}
            onClick={() => setStaticView("graph")}
          >
            Graph
          </button>
          <button
            type="button"
            className={`cafe-chip-btn ${staticView === "stream" ? "is-active" : ""}`}
            onClick={() => setStaticView("stream")}
          >
            Stream
          </button>
        </div>

        <div style={{ marginBottom: "10px" }}>
          <button type="button" className="cafe-btn" onClick={refreshStaticPlot}>
            Refresh Static Figure
          </button>
        </div>

        <div className="cafe-static-image-wrap">
          {staticTrajectory ? (
            <img
              key={staticImageUrl}
              className="cafe-static-image"
              src={staticImageUrl}
              alt="Static trajectory visualization"
              onLoad={() => setImageFailed(false)}
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="cafe-note" style={{ padding: "24px 0" }}>
              Waiting for the selected trajectory context to finish syncing before rendering the static figure.
            </div>
          )}
          {imageFailed ? (
            <div className="cafe-error" style={{ margin: "10px 0 0" }}>
              Static image request failed. Reinstall the latest backend hooks and check the Cellxgene server log for
              `/api/cafe/plot/static`.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default PlotModule;
