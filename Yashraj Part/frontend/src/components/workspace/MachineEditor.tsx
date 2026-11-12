import React, { useMemo, useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeChange,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { TuringMachine, NodeLayout } from '../../types';
import { StateNode } from './StateNode';
import { TransitionEdge, TransitionRuleItem } from './TransitionEdge';
import { generateAutoLayout } from '../../utils/tape';
import { Plus, LayoutGrid, AlertCircle } from 'lucide-react';

interface MachineEditorProps {
  machine: TuringMachine;
  layout: Record<string, NodeLayout>;
  onChangeMachine: (updated: TuringMachine) => void;
  onChangeLayout: (updated: Record<string, NodeLayout>) => void;
  activeStateId?: string;
  activeTransitionIndex?: number;
}

const nodeTypes: any = {
  stateNode: StateNode,
};

const edgeTypes: any = {
  transitionEdge: TransitionEdge,
};

export const MachineEditor: React.FC<MachineEditorProps> = ({
  machine,
  layout,
  onChangeMachine,
  onChangeLayout,
  activeStateId,
  activeTransitionIndex,
}) => {
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  // 1. Handlers for state mutations
  const handleEditName = useCallback(
    (id: string, newName: string) => {
      const updatedStates = machine.states.map((s) => (s.id === id ? { ...s, name: newName } : s));
      onChangeMachine({ ...machine, states: updatedStates });
    },
    [machine, onChangeMachine]
  );

  const handleSetStart = useCallback(
    (id: string) => {
      onChangeMachine({ ...machine, start_state: id });
    },
    [machine, onChangeMachine]
  );

  const handleToggleFinal = useCallback(
    (id: string) => {
      const isCurrentlyFinal = machine.final_states.includes(id);
      let updatedFinals: string[];
      let updatedTransitions = [...machine.transitions];

      if (isCurrentlyFinal) {
        updatedFinals = machine.final_states.filter((f) => f !== id);
      } else {
        // Marking as final: Final states cannot have outgoing transitions
        const outgoing = machine.transitions.filter((t) => t.from_state === id);
        if (outgoing.length > 0) {
          // Remove outgoing transitions and notify user
          updatedTransitions = machine.transitions.filter((t) => t.from_state !== id);
          setWarningMessage(
            `Marked "${id}" as final. Removed ${outgoing.length} outgoing transition(s) as final states cannot have outgoing rules.`
          );
          setTimeout(() => setWarningMessage(null), 6000);
        }
        updatedFinals = [...machine.final_states, id];
      }

      onChangeMachine({
        ...machine,
        final_states: updatedFinals,
        transitions: updatedTransitions,
      });
    },
    [machine, onChangeMachine]
  );

  const handleDeleteState = useCallback(
    (id: string) => {
      if (machine.states.length <= 1) {
        alert('A Turing machine must retain at least one state.');
        return;
      }

      const connectedTransitions = machine.transitions.filter(
        (t) => t.from_state === id || t.to_state === id
      );

      if (connectedTransitions.length > 0) {
        const confirmDelete = window.confirm(
          `Deleting state "${id}" will also remove ${connectedTransitions.length} connected transition rule(s). Proceed?`
        );
        if (!confirmDelete) return;
      }

      const updatedStates = machine.states.filter((s) => s.id !== id);
      const updatedTransitions = machine.transitions.filter(
        (t) => t.from_state !== id && t.to_state !== id
      );
      const updatedFinals = machine.final_states.filter((f) => f !== id);

      let newStartState = machine.start_state;
      if (machine.start_state === id) {
        newStartState = updatedStates[0].id;
        setWarningMessage(`Start state was re-assigned to "${newStartState}".`);
        setTimeout(() => setWarningMessage(null), 5000);
      }

      const updatedLayout = { ...layout };
      delete updatedLayout[id];
      onChangeLayout(updatedLayout);

      onChangeMachine({
        ...machine,
        states: updatedStates,
        start_state: newStartState,
        final_states: updatedFinals,
        transitions: updatedTransitions,
      });
    },
    [machine, layout, onChangeMachine, onChangeLayout]
  );

  const handleAddState = () => {
    let nextNum = machine.states.length;
    let candidateId = `q${nextNum}`;
    while (machine.states.some((s) => s.id === candidateId)) {
      nextNum++;
      candidateId = `q${nextNum}`;
    }

    const newState = {
      id: candidateId,
      name: `State ${candidateId}`,
    };

    // Calculate position
    const existingCoords = Object.values(layout);
    const lastX = existingCoords.length > 0 ? Math.max(...existingCoords.map((c) => c.x)) : 100;
    const newLayout = {
      ...layout,
      [candidateId]: {
        x: lastX + 160,
        y: 200 + (existingCoords.length % 2 === 0 ? 40 : -40),
      },
    };

    onChangeLayout(newLayout);
    onChangeMachine({
      ...machine,
      states: [...machine.states, newState],
    });
  };

  const handleAutoLayout = () => {
    const newLayout = generateAutoLayout(machine.states, machine.transitions, machine.start_state);
    onChangeLayout(newLayout);
  };

  // 2. Build React Flow Nodes
  const nodes: Node[] = useMemo(() => {
    return machine.states.map((state) => {
      const pos = layout[state.id] || { x: 100, y: 150 };
      const isStart = state.id === machine.start_state;
      const isFinal = machine.final_states.includes(state.id);
      const isActive = state.id === activeStateId;

      return {
        id: state.id,
        type: 'stateNode',
        position: { x: pos.x, y: pos.y },
        data: {
          id: state.id,
          name: state.name,
          isStart,
          isFinal,
          isActive,
          onEditName: handleEditName,
          onSetStart: handleSetStart,
          onToggleFinal: handleToggleFinal,
          onDelete: handleDeleteState,
        },
      };
    });
  }, [
    machine.states,
    machine.start_state,
    machine.final_states,
    layout,
    activeStateId,
    handleEditName,
    handleSetStart,
    handleToggleFinal,
    handleDeleteState,
  ]);

  // 3. Build React Flow Edges (grouping transitions sharing (from, to))
  const edges: Edge[] = useMemo(() => {
    const edgeMap: Record<string, { rules: TransitionRuleItem[]; indices: number[] }> = {};

    machine.transitions.forEach((t, idx) => {
      const key = `${t.from_state}->${t.to_state}`;
      if (!edgeMap[key]) {
        edgeMap[key] = { rules: [], indices: [] };
      }
      edgeMap[key].rules.push({
        read: t.read,
        write: t.write,
        move: t.move,
      });
      edgeMap[key].indices.push(idx);
    });

    return Object.entries(edgeMap).map(([key, item]) => {
      const [source, target] = key.split('->');
      const isSelfLoop = source === target;
      const isActive =
        activeTransitionIndex !== undefined && item.indices.includes(activeTransitionIndex);

      return {
        id: `e-${key}`,
        source,
        target,
        sourceHandle: isSelfLoop ? 'source-bottom' : 'source-right',
        targetHandle: isSelfLoop ? 'target-top' : 'target-left',
        type: 'transitionEdge',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 16,
          height: 16,
          color: isActive ? '#167E7A' : '#77756F',
        },
        data: {
          rules: item.rules,
          isActive,
        },
      };
    });
  }, [machine.transitions, activeTransitionIndex]);

  // 4. Node Drag Event to persist layout coordinates
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const updatedLayout = { ...layout };
      let changed = false;

      changes.forEach((change) => {
        if (change.type === 'position' && change.position && change.id) {
          updatedLayout[change.id] = {
            x: Math.round(change.position.x),
            y: Math.round(change.position.y),
          };
          changed = true;
        }
      });

      if (changed) {
        onChangeLayout(updatedLayout);
      }
    },
    [layout, onChangeLayout]
  );

  return (
    <div className="machine-editor-container">
      {/* Editor Canvas Toolbar */}
      <div className="editor-toolbar">
        <div className="toolbar-left">
          <span className="toolbar-badge">
            <strong>{machine.states.length}</strong> States
          </span>
          <span className="toolbar-badge">
            <strong>{machine.transitions.length}</strong> Transitions
          </span>
        </div>

        <div className="toolbar-right">
          <button
            type="button"
            className="toolbar-btn btn-primary-soft"
            onClick={handleAddState}
            title="Create a new machine state"
          >
            <Plus size={14} />
            <span>Add State</span>
          </button>

          <button
            type="button"
            className="toolbar-btn"
            onClick={handleAutoLayout}
            title="Auto-arrange state positions"
          >
            <LayoutGrid size={14} />
            <span>Auto Layout</span>
          </button>
        </div>
      </div>

      {/* Warning message notification */}
      {warningMessage && (
        <div className="editor-warning-banner">
          <AlertCircle size={14} />
          <span>{warningMessage}</span>
        </div>
      )}

      {/* Technical Graph Canvas */}
      <div className="editor-canvas-wrapper">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          fitView
          fitViewOptions={{ padding: 0.35 }}
          minZoom={0.2}
          maxZoom={2.0}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#CBD5E1" gap={20} size={1.2} />
          <Controls showInteractive={false} position="bottom-right" className="flow-controls" />
          <MiniMap
            nodeColor={(n) => {
              if (n.data?.isStart) return '#167E7A';
              if (n.data?.isFinal) return '#A9BA7B';
              return '#DED8CC';
            }}
            maskColor="rgba(248, 241, 227, 0.7)"
            className="flow-minimap"
          />
        </ReactFlow>
      </div>
    </div>
  );
};

