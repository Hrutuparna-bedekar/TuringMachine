import React, { useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { CheckCircle2, Trash2, Play, Check } from 'lucide-react';

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

  const startRename = () => {
    setDraftName(data.name || data.id);
    setIsEditing(true);
  };

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
      <Handle type="target" position={Position.Left} id="target-left" className="tm-handle" isConnectableStart={false} />
      <Handle type="target" position={Position.Top} id="target-top" className="tm-handle" isConnectableStart={false} />
      <Handle type="source" position={Position.Right} id="source-right" className="tm-handle" isConnectableStart={!data.isFinal} />
      <Handle type="source" position={Position.Bottom} id="source-bottom" className="tm-handle" isConnectableStart={!data.isFinal} />

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
          <form onSubmit={handleSaveName} className="node-name-form nodrag">
            <input
              type="text"
              aria-label="New state name"
              maxLength={64}
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              autoFocus
              onKeyDown={(event) => {
                if (event.key === 'Escape') setIsEditing(false);
              }}
              className="node-name-input"
            />
            <button type="submit" className="node-save-btn" aria-label="Save state name">
              <Check size={12} />
            </button>
          </form>
        ) : (
          <div
            className="node-title"
            onDoubleClick={data.onEditName ? startRename : undefined}
            title={data.onEditName ? 'Double click to rename' : undefined}
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

        {data.onEditName && <button
          type="button"
          className="node-mini-btn"
          title="Rename state"
          onClick={(e) => {
            e.stopPropagation();
            startRename();
          }}
        >
          Rename
        </button>}

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

