import React from "react";

function inferMetricKeys(rows) {
  if (!rows.length) {
    return [];
  }
  return Object.keys(rows[0]).filter((key) => key !== "id");
}

class Explorer extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      activeSubModule: "benchmark",
    };
  }

  renderBenchmark(benchmarkRows, metricKeys) {
    if (!benchmarkRows.length) {
      return <div className="cafe-note">No benchmark metrics found in current trajectory history.</div>;
    }

    return (
      <table className="cafe-table">
        <thead>
          <tr>
            <th>ID</th>
            {metricKeys.map((key) => (
              <th key={key}>{key}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {benchmarkRows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              {metricKeys.map((key) => {
                const value = row[key];
                const text =
                  typeof value === "number" ? value.toFixed(3) : String(value ?? "");
                return <td key={`${row.id}-${key}`}>{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  render() {
    const { context } = this.props;
    const { activeSubModule } = this.state;

    const benchmarkRows = context?.plot?.benchmarkRows || [];
    const keysFromContext = context?.plot?.metricKeys || [];
    const metricKeys =
      keysFromContext.length > 0
        ? keysFromContext
        : inferMetricKeys(benchmarkRows);

    return (
      <div>
        <div className="cafe-card">
          <h4>Explorer</h4>
          <div className="cafe-switch-row">
            <button
              type="button"
              className={`cafe-chip-btn ${
                activeSubModule === "benchmark" ? "is-active" : ""
              }`}
              onClick={() => this.setState({ activeSubModule: "benchmark" })}
            >
              Benchmark
            </button>
            <button
              type="button"
              className={`cafe-chip-btn ${
                activeSubModule === "insights" ? "is-active" : ""
              }`}
              onClick={() => this.setState({ activeSubModule: "insights" })}
            >
              Insights (TODO)
            </button>
          </div>
        </div>

        {activeSubModule === "benchmark" ? (
          <div className="cafe-card">
            <h4>Trajectory Benchmark</h4>
            {this.renderBenchmark(benchmarkRows, metricKeys)}
          </div>
        ) : (
          <div className="cafe-placeholder">
            <h4>Explorer Insights (TODO)</h4>
            <p className="cafe-note">后续将在该子模块扩展驱动基因、趋势分析、跨方法比较等内容。</p>
          </div>
        )}
      </div>
    );
  }
}

export default Explorer;