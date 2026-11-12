import React, { useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { CheckCircle2, Trash2, Edit2, Play, Check } from 'lucide-react';

export interface StateNodeData {
  id: string;
  name: string;
  isStart: boolean;
  isFinal: boolean;
  isActive?: boolean;
  onEditName?: (id: string, newName: string) => void;
  onSetStart?: (id: string) => void;
  onToggleFinal?: (id: string) => void;
  onDelete?: (id: string) => void;
}

export const StateNode: React.FC<any> = ({ data, selected }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [draftName, setDraftName] = useState(data.name || data.id);

  const handleSaveName = (e: React.FormEvent) => {
    e.preventDefault();
    if (draftName.trim() && data.onEditName) {
      data.onEditName(data.id, draftName.trim());
    }
    setIsEditing(false);
  };

  return (
    <div
      className={`tm-state-node ${selected ? 'selected' : ''} ${data.isStart ? 'start-state' : ''} ${
        data.isFinal ? 'final-state' : ''
      } ${data.isActive ? 'active-replay-state' : ''}`}
    >
      {/* Handles for connections */}
      <Handle type="target" position={Position.Left} id="target-left" className="tm-handle" />
      <Handle type="target" position={Position.Top} id="target-top" className="tm-handle" />
      <Handle type="source" position={Position.Right} id="source-right" className="tm-handle" />
      <Handle type="source" position={Position.Bottom} id="source-bottom" className="tm-handle" />

      {/* Start State Indicator Indicator Marker */}
      {data.isStart && (
        <div className="state-badge-start" title="Initial Start State (Head begins here)">
          <Play size={10} className="badge-icon" />
          <span>START</span>
        </div>
      )}

      {/* Final State Indicator */}
      {data.isFinal && (
        <div className="state-badge-final" title="Accepting / Terminal State">
          <CheckCircle2 size={10} className="badge-icon" />
          <span>FINAL</span>
        </div>
      )}

      {/* Active Replay Indicator */}
      {data.isActive && (
        <div className="state-badge-active" title="Current Head State">
          <span>● CURRENT</span>
        </div>
      )}

      {/* Node Content Header */}
      <div className="node-body">
        <div className="node-id-tag font-mono">{data.id}</div>

        {isEditing ? (
          <form onSubmit={handleSaveName} className="node-name-form">
            <input
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              autoFocus
              onBlur={() => setIsEditing(false)}
              className="node-name-input"
            />
            <button type="submit" className="node-save-btn">
              <Check size={12} />
            </button>
          </form>
        ) : (
          <div
            className="node-title"
            onDoubleClick={() => setIsEditing(true)}
            title="Double click to edit label"
          >
            {data.name || data.id}
          </div>
        )}
      </div>

      {/* Node Context Actions Toolbar */}
      <div className="node-action-bar">
        {!data.isStart && data.onSetStart && (
          <button
            type="button"
            className="node-mini-btn"
            title="Make this the Start State"
            onClick={(e) => {
              e.stopPropagation();
              data.onSetStart(data.id);
            }}
          >
            Set Start
          </button>
        )}

        {data.onToggleFinal && (
          <button
            type="button"
            className={`node-mini-btn ${data.isFinal ? 'active-toggle' : ''}`}
            title={data.isFinal ? 'Unmark as final state' : 'Mark as accepting final state'}
            onClick={(e) => {
              e.stopPropagation();
              data.onToggleFinal(data.id);
            }}
          >
            {data.isFinal ? 'Final ✓' : 'Make Final'}
          </button>
        )}

        <button
          type="button"
          className="node-mini-btn"
          title="Edit display label"
          onClick={(e) => {
            e.stopPropagation();
            setIsEditing(true);
          }}
        >
          <Edit2 size={11} />
        </button>

        {data.onDelete && (
          <button
            type="button"
            className="node-mini-btn btn-danger"
            title="Delete this state"
            onClick={(e) => {
              e.stopPropagation();
              data.onDelete(data.id);
            }}
          >
            <Trash2 size={11} />
          </button>
        )}
      </div>
    </div>
  );
};

