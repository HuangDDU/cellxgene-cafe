import React from "react";

const WIDTH = 300;
const HEIGHT = 260;
const PAD = 16;

class PreviewNetwork extends React.Component {
  getNodeById(nodes) {
    const map = {};
    nodes.forEach((node) => {
      map[node.id] = node;
    });
    return map;
  }

  getBounds(nodes) {
    if (!nodes.length) {
      return { minX: 0, maxX: 1, minY: 0, maxY: 1 };
    }
    const xs = nodes.map((n) => Number(n.x || 0));
    const ys = nodes.map((n) => Number(n.y || 0));
    return {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
  }

  scaleX(value, bounds) {
    const range = bounds.maxX - bounds.minX || 1;
    return PAD + ((Number(value || 0) - bounds.minX) / range) * (WIDTH - PAD * 2);
  }

  scaleY(value, bounds) {
    const range = bounds.maxY - bounds.minY || 1;
    const normalized = (Number(value || 0) - bounds.minY) / range;
    return HEIGHT - PAD - normalized * (HEIGHT - PAD * 2);
  }

  render() {
    const preview = this.props.preview;
    const nodes = preview?.nodes || [];
    const edges = preview?.edges || [];
    const waypointSegments = preview?.waypointSegments || {};
    const nodeById = this.getNodeById(nodes);
    const bounds = this.getBounds(nodes);

    if (!nodes.length) {
      return <div className="cafe-note">No preview graph available for this trajectory/layout.</div>;
    }

    return (
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <rect x="0" y="0" width={WIDTH} height={HEIGHT} fill="#fbfdff" stroke="#d7e0eb" />

        {Object.entries(waypointSegments).map(([groupId, points]) => {
          if (!points || points.length < 2) {
            return null;
          }
          const pathD = points
            .map(
              (point, idx) =>
                `${idx === 0 ? "M" : "L"} ${this.scaleX(point.x, bounds)} ${this.scaleY(point.y, bounds)}`
            )
            .join(" ");
          return (
            <path
              key={`segment-${groupId}`}
              d={pathD}
              fill="none"
              stroke="#6f7f8d"
              strokeWidth="1.4"
              strokeDasharray="3 2"
              opacity="0.8"
            />
          );
        })}

        {edges.map((edge) => {
          const source = nodeById[edge.source];
          const target = nodeById[edge.target];
          if (!source || !target) {
            return null;
          }
          return (
            <line
              key={`edge-${edge.id}`}
              x1={this.scaleX(source.x, bounds)}
              y1={this.scaleY(source.y, bounds)}
              x2={this.scaleX(target.x, bounds)}
              y2={this.scaleY(target.y, bounds)}
              stroke="#2b2b2b"
              strokeWidth="2"
            />
          );
        })}

        {nodes.map((node) => (
          <g key={`node-${node.id}`}>
            <circle
              cx={this.scaleX(node.x, bounds)}
              cy={this.scaleY(node.y, bounds)}
              r="5"
              fill={node.color || "#9aa7b0"}
              stroke="#213245"
            />
            <text
              x={this.scaleX(node.x, bounds) + 7}
              y={this.scaleY(node.y, bounds) - 7}
              fontSize="10"
              fill="#2f4d6f"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    );
  }
}

export default PreviewNetwork;
