import React from 'react';
import {
  getBezierPath,
  EdgeLabelRenderer,
  BaseEdge,
} from '@xyflow/react';

export interface TransitionRuleItem {
  read: string;
  write: string;
  move: 'L' | 'R';
}

export interface TransitionEdgeData {
  rules: TransitionRuleItem[];
  isActive?: boolean;
}

export const TransitionEdge: React.FC<any> = ({
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
  selected,
}) => {
  const isSelfLoop = source === target;
  let edgePath = '';
  let labelX = 0;
  let labelY = 0;

  if (isSelfLoop) {
    // Custom SVG path for self loop curving upwards
    const loopHeight = 55;
    const loopWidth = 45;
    edgePath = `M ${sourceX} ${sourceY} C ${sourceX + loopWidth} ${sourceY - loopHeight}, ${
      sourceX - loopWidth
    } ${sourceY - loopHeight}, ${targetX} ${targetY}`;
    labelX = sourceX;
    labelY = sourceY - loopHeight - 12;
  } else {
    const [path, lx, ly] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
    });
    edgePath = path;
    labelX = lx;
    labelY = ly;
  }

  const rules: TransitionRuleItem[] = data?.rules || [];
  const isActive = Boolean(data?.isActive);

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: isActive ? '#167E7A' : selected ? '#171717' : '#94A3B8',
          strokeWidth: isActive ? 3 : selected ? 2.5 : 1.75,
          transition: 'stroke 0.2s, stroke-width 0.2s',
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all',
          }}
          className={`edge-label-pill ${selected ? 'selected' : ''} ${isActive ? 'active-edge' : ''}`}
        >
          {rules.map((rule, idx) => (
            <div key={idx} className="edge-rule-row font-mono">
              <span className="rule-read">{rule.read}</span>
              <span className="rule-arrow">→</span>
              <span className="rule-write">{rule.write}</span>
              <span className="rule-comma">·</span>
              <span className={`rule-move move-${rule.move}`}>{rule.move === 'R' ? 'Right' : 'Left'}</span>
            </div>
          ))}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

