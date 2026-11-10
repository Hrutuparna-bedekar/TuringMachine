import React, { useState } from 'react';
import { TuringMachine, SimulationResponse } from './machine';
import { MachineEditor } from './MachineEditor';
import { TransitionTable } from './TransitionTable';
import { TapePlayer } from './TapePlayer';
import { ResultsPanel } from './ResultsPanel';
import { simulateMachine } from './api';

const defaultMachine: TuringMachine = {
  states: [
    { id: 'q_scan', name: 'Scanning Tape' },
    { id: 'q_halt', name: 'Halt on Blank' },
  ],
  input_alphabet: ['0', '1'],
  tape_alphabet: ['0', '1', '□'],
  blank_symbol: '□',
  start_state: 'q_scan',
  final_states: ['q_halt'],
  transitions: [
    { from_state: 'q_scan', read: '0', to_state: 'q_scan', write: '0', move: 'R' },
    { from_state: 'q_scan', read: '1', to_state: 'q_scan', write: '1', move: 'R' },
    { from_state: 'q_scan', read: '□', to_state: 'q_halt', write: '□', move: 'R' },
  ],
};

export const App: React.FC = () => {
  const [machine, setMachine] = useState<TuringMachine>(defaultMachine);
  const [inputText, setInputText] = useState('101');
  const [stepLimit, setStepLimit] = useState(50);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await simulateMachine({
        machine,
        input: inputText,
        step_limit: stepLimit,
      });
      setSimulationResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1>Turing Machine Simulator</h1>
        <p className="subtitle">Interactive Simulation Engine & Research Platform</p>
      </header>

      <div style={{ margin: '1rem 0', display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <label>
          Input String:
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            style={{ marginLeft: '0.5rem', padding: '0.25rem 0.5rem' }}
          />
        </label>
        <label>
          Step Limit:
          <input
            type="number"
            value={stepLimit}
            onChange={(e) => setStepLimit(Number(e.target.value))}
            style={{ marginLeft: '0.5rem', width: '80px', padding: '0.25rem 0.5rem' }}
          />
        </label>
        <button
          onClick={handleSimulate}
          disabled={loading}
          style={{ padding: '0.5rem 1rem', background: '#0284c7', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
        >
          {loading ? 'Simulating...' : 'Run Simulation'}
        </button>
      </div>

      <div className="workspace-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <MachineEditor machine={machine} onChange={setMachine} />
          <TransitionTable machine={machine} onChange={setMachine} />
          <TapePlayer simulationResult={simulationResult} />
        </div>
        <div>
          <ResultsPanel simulationResult={simulationResult} loading={loading} error={error} />
        </div>
      </div>
    </div>
  );
};
