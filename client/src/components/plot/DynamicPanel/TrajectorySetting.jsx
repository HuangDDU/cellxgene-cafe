import React from "react";

import "./index.css";

class TrajectorySetting extends React.Component {
	render() {
		const {
			plotState,
			currentTrajectory,
			currentLayout,
			trajectoryOptions,
			layoutOptions,
			onTrajectoryChange,
			onLayoutChange,
			onSetTrajectoryType,
			onSetTrajectoryNodeSize,
			onSetTrajectoryEdgeWidth,
		} = this.props;

		return (
			<div className="cafe-dynamics-controls-panel">
				<h4 className="cafe-subsection-title">Trajectory Setting</h4>
				<div className="cafe-dynamics-control-grid">
					<div className="cafe-dynamics-field-row">
						<label htmlFor="trajectory-method">Method / Trajectory</label>
						<select
							id="trajectory-method"
							value={currentTrajectory}
							onChange={onTrajectoryChange}
						>
							{trajectoryOptions.map((item) => (
								<option key={item} value={item}>
									{item}
								</option>
							))}
						</select>
					</div>

					<div className="cafe-dynamics-field-row">
						<label htmlFor="trajectory-layout">Embedding Layout</label>
						<select
							id="trajectory-layout"
							value={currentLayout}
							onChange={onLayoutChange}
						>
							{layoutOptions.map((item) => (
								<option key={item} value={item}>
									{item}
								</option>
							))}
						</select>
					</div>
				</div>

				<div className="cafe-switch-row cafe-dynamics-switches">
					<div className="cafe-dynamics-mode-row">
						<span className="cafe-dynamics-mode-label">Plot Mode:</span>
						<div className="cafe-dynamics-mode-options">
							<label>
								<input
									type="radio"
									name="trajectoryType"
									checked={(plotState.trajectoryType || "milestone") === "milestone"}
									onChange={() => onSetTrajectoryType("milestone")}
								/>{" "}
								milestone
							</label>

							<label>
								<input
									type="radio"
									name="trajectoryType"
									checked={(plotState.trajectoryType || "milestone") === "waypoint"}
									onChange={() => onSetTrajectoryType("waypoint")}
								/>{" "}
								waypoint
							</label>
						</div>
					</div>
				</div>

				<div className="cafe-dynamics-sliders">
					<div className="cafe-dynamics-slider-row">
						<label htmlFor="trajectory-node-size">Milestone node size</label>
						<input
							id="trajectory-node-size"
							type="range"
							min="0"
							max="10"
							step="0.1"
							value={plotState.nodeSize ?? 2.5}
							onChange={(event) => onSetTrajectoryNodeSize(Number(event.target.value))}
						/>
						<span className="cafe-dynamics-slider-value">
							{Number(plotState.nodeSize ?? 2.5).toFixed(1)}
						</span>
					</div>

					<div className="cafe-dynamics-slider-row">
						<label htmlFor="trajectory-edge-width">Milestone edge width</label>
						<input
							id="trajectory-edge-width"
							type="range"
							min="0"
							max="10"
							step="0.1"
							value={plotState.edgeWidth ?? 1}
							onChange={(event) => onSetTrajectoryEdgeWidth(Number(event.target.value))}
						/>
						<span className="cafe-dynamics-slider-value">
							{Number(plotState.edgeWidth ?? 1).toFixed(1)}
						</span>
					</div>
				</div>
			</div>
		);
	}
}

export default TrajectorySetting;