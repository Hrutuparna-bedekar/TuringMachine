import React from 'react';
import { TuringMachine } from './machine';

interface MachineEditorProps {
  machine: TuringMachine;
  onChange: (updated: TuringMachine) => void;
}

export const MachineEditor: React.FC<MachineEditorProps> = ({ machine }) => {
  return (
    <div className="panel machine-editor-panel">
      <h2>Machine Graph Canvas</h2>
      <p style={{ color: '#64748b' }}>
        Interactive graph canvas using React Flow (@xyflow/react). States: {machine.states.length}, Rules: {machine.transitions.length}
      </p>
      <div style={{ height: '350px', background: '#f1f5f9', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px dashed #cbd5e1' }}>
        <span>React Flow Canvas Area</span>
      </div>
    </div>
  );
};
