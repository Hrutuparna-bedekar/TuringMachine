import React from 'react';
import { TuringMachine } from './machine';

interface TransitionTableProps {
  machine: TuringMachine;
  onChange: (updated: TuringMachine) => void;
}

export const TransitionTable: React.FC<TransitionTableProps> = ({ machine }) => {
  return (
    <div className="panel transition-table-panel">
      <h2>Transition Rules Table</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
            <th style={{ padding: '0.5rem' }}>From State</th>
            <th style={{ padding: '0.5rem' }}>Read</th>
            <th style={{ padding: '0.5rem' }}>To State</th>
            <th style={{ padding: '0.5rem' }}>Write</th>
            <th style={{ padding: '0.5rem' }}>Move</th>
          </tr>
        </thead>
        <tbody>
          {machine.transitions.map((t, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
              <td style={{ padding: '0.5rem' }}>{t.from_state}</td>
              <td style={{ padding: '0.5rem' }}>{t.read}</td>
              <td style={{ padding: '0.5rem' }}>{t.to_state}</td>
              <td style={{ padding: '0.5rem' }}>{t.write}</td>
              <td style={{ padding: '0.5rem' }}>{t.move}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
