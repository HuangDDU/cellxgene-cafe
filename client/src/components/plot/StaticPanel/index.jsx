import React from "react";

import { buildStaticPlotUrl } from "../../../lib/api";

import "./index.css";

class StaticPanel extends React.Component {
	constructor(props) {
		super(props);
		this.state = {
			staticView: "trajectory",
			imageSeed: 0,
		};
	}

	refreshStaticPlot = () => {
		this.setState((prevState) => ({
			imageSeed: prevState.imageSeed + 1,
		}));
	};

	render() {
		const { currentTrajectory, currentLayout } = this.props;
		const { staticView, imageSeed } = this.state;

		const staticImageUrl = buildStaticPlotUrl({
			view: staticView,
			trajectory: currentTrajectory,
			layout: currentLayout,
			t: imageSeed,
		});

		return (
			<div className="cafe-card cafe-static-card">
				<h4>Static</h4>
				<div className="cafe-note cafe-static-note">
					后端分别调用 cafe.plot.plot_trajectory / cafe.plot.plot_graph /
					cafe.plot.plot_stream 并返回图片。
				</div>

				<div className="cafe-switch-row cafe-static-switches">
					<span className="cafe-note">Static View:</span>
					<button
						type="button"
						className={`cafe-chip-btn ${staticView === "trajectory" ? "is-active" : ""}`}
						onClick={() => this.setState({ staticView: "trajectory" })}
					>
						Trajectory
					</button>
					<button
						type="button"
						className={`cafe-chip-btn ${staticView === "graph" ? "is-active" : ""}`}
						onClick={() => this.setState({ staticView: "graph" })}
					>
						Graph
					</button>
					<button
						type="button"
						className={`cafe-chip-btn ${staticView === "stream" ? "is-active" : ""}`}
						onClick={() => this.setState({ staticView: "stream" })}
					>
						Stream
					</button>
				</div>

				<div className="cafe-static-refresh-row">
					<button type="button" className="cafe-btn" onClick={this.refreshStaticPlot}>
						Refresh Static Figure
					</button>
				</div>

				<div className="cafe-static-image-wrap">
					<img
						className="cafe-static-image"
						src={staticImageUrl}
						alt="Static trajectory visualization"
					/>
				</div>
			</div>
		);
	}
}

export default StaticPanel;