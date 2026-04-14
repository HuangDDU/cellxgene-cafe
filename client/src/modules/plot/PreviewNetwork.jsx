import React, { useMemo } from "react";

const WIDTH = 300;
const HEIGHT = 260;
const PAD = 16;

function PreviewNetwork({ preview }) {
  const nodes = preview?.nodes || [];
  const edges = preview?.edges || [];
  const waypointSegments = preview?.waypointSegments || {};

  const nodeById = useMemo(() => {
    const map = {};
    nodes.forEach((node) => {
      map[node.id] = node;
    });
    return map;
  }, [nodes]);

  const bounds = useMemo(() => {
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
  }, [nodes]);

  const scaleX = (value) => {
    const range = bounds.maxX - bounds.minX || 1;
    return PAD + ((Number(value || 0) - bounds.minX) / range) * (WIDTH - PAD * 2);
  };

  const scaleY = (value) => {
    const range = bounds.maxY - bounds.minY || 1;
    const normalized = (Number(value || 0) - bounds.minY) / range;
    return HEIGHT - PAD - normalized * (HEIGHT - PAD * 2);
  };

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
          .map((point, idx) => `${idx === 0 ? "M" : "L"} ${scaleX(point.x)} ${scaleY(point.y)}`)
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
            x1={scaleX(source.x)}
            y1={scaleY(source.y)}
            x2={scaleX(target.x)}
            y2={scaleY(target.y)}
            stroke="#2b2b2b"
            strokeWidth="2"
          />
        );
      })}

      {nodes.map((node) => (
        <g key={`node-${node.id}`}>
          <circle cx={scaleX(node.x)} cy={scaleY(node.y)} r="5" fill={node.color || "#9aa7b0"} stroke="#213245" />
          <text x={scaleX(node.x) + 7} y={scaleY(node.y) - 7} fontSize="10" fill="#2f4d6f">
            {node.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default PreviewNetwork;
