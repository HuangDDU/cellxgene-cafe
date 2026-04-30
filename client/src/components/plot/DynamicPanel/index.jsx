import React from "react";

import TrajectoryPreview from "./TrajectoryPreview";
import TrajectorySetting from "./TrajectorySetting";

import "./index.css";

function DynamicPanel(props) {
	const {
		plotState,
		preview,
		currentTrajectory,
		currentLayout,
		trajectoryOptions,
		layoutOptions,
		onTrajectoryChange,
		onLayoutChange,
		onSetTrajectoryVisible,
		onSetTrajectoryType,
		onSetTrajectoryNodeSize,
		onSetTrajectoryEdgeWidth,
	} = props;

	return (
		<div className="cafe-card cafe-dynamics-card">
			<div className="cafe-dynamics-header">
				<h4>Dynamics</h4>
				<label className="cafe-dynamics-show-toggle">
					<input
						type="checkbox"
						checked={!!plotState.showTrajectory}
						onChange={(event) => onSetTrajectoryVisible(event.target.checked)}
					/>
					Show
				</label>
			</div>
			<div className="cafe-note cafe-dynamics-note">
				Display trajectory dynamically on cellxgene main panel.
			</div>

			<div className="cafe-dynamics-layout">
				<TrajectorySetting
					plotState={plotState}
					currentTrajectory={currentTrajectory}
					currentLayout={currentLayout}
					trajectoryOptions={trajectoryOptions}
					layoutOptions={layoutOptions}
					onTrajectoryChange={onTrajectoryChange}
					onLayoutChange={onLayoutChange}
					onSetTrajectoryType={onSetTrajectoryType}
					onSetTrajectoryNodeSize={onSetTrajectoryNodeSize}
					onSetTrajectoryEdgeWidth={onSetTrajectoryEdgeWidth}
				/>

				<TrajectoryPreview preview={preview} />
			</div>
		</div>
	);
}

export default DynamicPanel;