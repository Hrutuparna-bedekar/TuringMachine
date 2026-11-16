import React, { useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { CheckCircle2, Trash2, Play, Check, Edit2, ArrowRight } from 'lucide-react';

export interface StateNodeData {
  id: string;
  name: string;
  isStart: boolean;
  isFinal: boolean;
  isActive?: boolean;
  isReject?: boolean;
  onEditName?: (id: string, newName: string) => void;
  onSetStart?: (id: string) => void;
  onToggleFinal?: (id: string) => void;
  onDelete?: (id: string) => void;
}

export const StateNode: React.FC<any> = ({ data, selected }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [draftName, setDraftName] = useState(data.name || data.id);
  const [isHovered, setIsHovered] = useState(false);

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

  // Determine if this state represents an explicit rejecting state
  const isReject =
    data.isReject ||
    data.id.toLowerCase().includes('reject') ||
    (data.name && data.name.toLowerCase().includes('reject'));

  return (
    <div
      className={`tm-circular-state-node ${selected ? 'selected' : ''} ${
        data.isStart ? 'start-state' : ''
      } ${data.isFinal ? 'final-state' : ''} ${isReject ? 'reject-state' : ''} ${
        data.isActive ? 'active-replay-state' : ''
      }`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Connection Handles positioned symmetrically on the circle boundary */}
      <Handle
        type="target"
        position={Position.Left}
        id="target-left"
        className="tm-handle handle-left"
        isConnectableStart={false}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="target-top"
        className="tm-handle handle-top"
        isConnectableStart={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="source-right"
        className="tm-handle handle-right"
        isConnectableStart={!data.isFinal}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source-bottom"
        className="tm-handle handle-bottom"
        isConnectableStart={!data.isFinal}
      />

      {/* Start State Indicator: Formal TOC start arrow entering from the left */}
      {data.isStart && (
        <div className="state-start-arrow" title="Initial Start State (Head starts here)">
          <div className="start-badge-pill">START</div>
          <ArrowRight size={16} className="start-arrow-glyph" />
        </div>
      )}

      {/* Accepting / Final State: Formal TOC double concentric circle */}
      {data.isFinal && <div className="concentric-final-ring" />}

      {/* Active Replay / Simulation glowing pulse aura */}
      {data.isActive && <div className="active-pulse-aura" />}

      {/* Circular Node Core Body */}
      <div
        className="circular-node-core"
        onDoubleClick={data.onEditName ? startRename : undefined}
      >
        {isEditing ? (
          <form onSubmit={handleSaveName} className="node-inline-edit-form nodrag">
            <input
              type="text"
              aria-label="New state name"
              maxLength={16}
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              autoFocus
              onKeyDown={(event) => {
                if (event.key === 'Escape') setIsEditing(false);
              }}
              className="node-circle-input font-mono"
            />
            <button type="submit" className="node-circle-save" aria-label="Save">
              <Check size={11} />
            </button>
          </form>
        ) : (
          <div className="circle-labels">
            <span className="state-id-title font-mono">{data.id}</span>
          </div>
        )}
      </div>

      {/* Human-readable State Name underneath circle */}
      {data.name && data.name !== data.id && !isEditing && (
        <div className="state-subtitle-caption" title={data.name}>
          {data.name}
        </div>
      )}

      {/* Floating Action Bar on hover or selection (non-intrusive) */}
      {(selected || isHovered) && (data.onSetStart || data.onToggleFinal || data.onEditName || data.onDelete) && (
        <div className="node-floating-actions nodrag">
          {!data.isStart && data.onSetStart && (
            <button
              type="button"
              className="action-icon-btn"
              title="Set as Start State"
              onClick={(e) => {
                e.stopPropagation();
                data.onSetStart(data.id);
              }}
            >
              <Play size={10} />
            </button>
          )}

          {data.onToggleFinal && (
            <button
              type="button"
              className={`action-icon-btn ${data.isFinal ? 'active-final' : ''}`}
              title={data.isFinal ? 'Unmark as Final (Accepting)' : 'Mark as Final (Accepting State)'}
              onClick={(e) => {
                e.stopPropagation();
                data.onToggleFinal(data.id);
              }}
            >
              <CheckCircle2 size={11} />
            </button>
          )}

          {data.onEditName && (
            <button
              type="button"
              className="action-icon-btn"
              title="Rename State"
              onClick={(e) => {
                e.stopPropagation();
                startRename();
              }}
            >
              <Edit2 size={10} />
            </button>
          )}

          {data.onDelete && !data.isStart && (
            <button
              type="button"
              className="action-icon-btn btn-danger"
              title="Delete State"
              onClick={(e) => {
                e.stopPropagation();
                data.onDelete(data.id);
              }}
            >
              <Trash2 size={10} />
            </button>
          )}
        </div>
      )}
    </div>
  );
};
