import React, { useState } from 'react';
import { SimulationResponse } from './machine';

interface TapePlayerProps {
  simulationResult: SimulationResponse | null;
}

export const TapePlayer: React.FC<TapePlayerProps> = ({ simulationResult }) => {
  const [cursor, setCursor] = useState(0);

  if (!simulationResult) {
    return (
      <div className="panel tape-player-panel">
        <h2>Tape Playback</h2>
        <p style={{ color: '#64748b' }}>Run a simulation to view tape playback and trace controls.</p>
      </div>
    );
  }

  const maxSteps = simulationResult.trace.length;

  return (
    <div className="panel tape-player-panel">
      <h2>Tape Playback & Execution Trace</h2>
      <div style={{ margin: '1rem 0', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <button onClick={() => setCursor(0)} disabled={cursor === 0}>Reset</button>
        <button onClick={() => setCursor(Math.max(0, cursor - 1))} disabled={cursor === 0}>Step Back</button>
        <button onClick={() => setCursor(Math.min(maxSteps, cursor + 1))} disabled={cursor >= maxSteps}>Step Forward</button>
        <span>Step {cursor} of {maxSteps}</span>
      </div>
    </div>
  );
};
