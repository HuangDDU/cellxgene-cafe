import React from "react";

import DynamicPanel from "./DynamicPanel";
import StaticPanel from "./StaticPanel";

class Plot extends React.Component {
  onTrajectoryChange = (event) => {
    const {
      context,
      bridgeState,
      onSetTrajectoryChoice,
      onRefreshContext,
    } = this.props;
    const value = event.target.value;
    const layoutChoice = bridgeState?.layoutChoice || {};
    const currentLayout =
      layoutChoice.current || context?.current?.layout || "";

    onSetTrajectoryChoice(value);
    onRefreshContext({ trajectory: value, layout: currentLayout });
  };

  onLayoutChange = (event) => {
    const {
      context,
      bridgeState,
      onSetLayoutChoice,
      onRefreshContext,
    } = this.props;
    const value = event.target.value;
    const trajectoryChoice = bridgeState?.trajectoryChoice || {};
    const currentTrajectory =
      trajectoryChoice.current || context?.current?.trajectory || "";

    onSetLayoutChoice(value);
    onRefreshContext({ trajectory: currentTrajectory, layout: value });
  };

  render() {
    const {
      context,
      bridgeState,
      onSetTrajectoryVisible,
      onSetTrajectoryType,
      onSetTrajectoryNodeSize,
      onSetTrajectoryEdgeWidth,
    } = this.props;

    const plotState = bridgeState?.trajectory || {};
    const trajectoryChoice = bridgeState?.trajectoryChoice || {};
    const layoutChoice = bridgeState?.layoutChoice || {};

    const trajectoryOptions = context?.trajectories || [];
    const layoutOptions = context?.layouts || [];

    const currentTrajectory =
      trajectoryChoice.current || context?.current?.trajectory || "";
    const currentLayout = layoutChoice.current || context?.current?.layout || "";
    const preview =
      context?.plot?.preview || { nodes: [], edges: [], waypointSegments: {} };

    return (
      <div>
        <DynamicPanel
          plotState={plotState}
          preview={preview}
          currentTrajectory={currentTrajectory}
          currentLayout={currentLayout}
          trajectoryOptions={trajectoryOptions}
          layoutOptions={layoutOptions}
          onTrajectoryChange={this.onTrajectoryChange}
          onLayoutChange={this.onLayoutChange}
          onSetTrajectoryVisible={onSetTrajectoryVisible}
          onSetTrajectoryType={onSetTrajectoryType}
          onSetTrajectoryNodeSize={onSetTrajectoryNodeSize}
          onSetTrajectoryEdgeWidth={onSetTrajectoryEdgeWidth}
        />

        <StaticPanel
          currentTrajectory={currentTrajectory}
          currentLayout={currentLayout}
        />
      </div>
    );
  }
}

export default Plot;