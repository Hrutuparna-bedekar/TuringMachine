import React from 'react';
import { SimulationResponse } from './machine';

interface ResultsPanelProps {
  simulationResult: SimulationResponse | null;
  loading: boolean;
  error: string | null;
}

export const ResultsPanel: React.FC<ResultsPanelProps> = ({ simulationResult, loading, error }) => {
  return (
    <div className="panel results-panel">
      <h2>Simulation Results</h2>
      {loading && <p>Running simulation...</p>}
      {error && <p style={{ color: '#ef4444' }}>Error: {error}</p>}
      {simulationResult && (
        <div>
          <p><strong>Status:</strong> {simulationResult.halted_within_limit ? 'Halted' : 'Did Not Halt within Budget'}</p>
          <p><strong>Stop Reason:</strong> <code>{simulationResult.stop_reason}</code></p>
          <p><strong>Steps Executed:</strong> {simulationResult.steps}</p>
        </div>
      )}
      {!loading && !error && !simulationResult && (
        <p style={{ color: '#64748b' }}>No simulation executed yet.</p>
      )}
    </div>
  );
};
