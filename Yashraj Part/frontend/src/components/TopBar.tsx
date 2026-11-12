import React from 'react';
import { Play, UploadCloud, PlusCircle, RefreshCw } from 'lucide-react';
import { ActiveView, TuringMachine } from '../types';

interface TopBarProps {
  currentView: ActiveView;
  machine: TuringMachine;
  onOpenImportExport: () => void;
  onNewMachine: () => void;
  onRunSimulation: () => void;
  isSimulating: boolean;
}

const VIEW_TITLES: Record<ActiveView, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'System Overview',
    subtitle: 'Turing machine definitions, execution metrics & quick actions',
  },
  workspace: {
    title: 'Machine Workspace',
    subtitle: 'Visual state graph canvas, transition matrix & machine configuration',
  },
  simulation: {
    title: 'Tape Simulation & Replay',
    subtitle: 'Step-by-step trace navigation, tape head cursor & terminal analysis',
  },
  predictor: {
    title: 'Bounded Halting Predictor',
    subtitle: 'ML classification across 50, 200, and 1,000 transition budgets',
  },
  examples: {
    title: 'Example Machine Library',
    subtitle: 'Classical automata templates ready to inspect, load, and execute',
  },
  help: {
    title: 'Theory of Computation Reference',
    subtitle: 'Formal definitions, deterministic 1-tape semantics & halting proofs',
  },
};

export const TopBar: React.FC<TopBarProps> = ({
  currentView,
  machine,
  onOpenImportExport,
  onNewMachine,
  onRunSimulation,
  isSimulating,
}) => {
  const info = VIEW_TITLES[currentView];

  return (
    <header className="app-topbar">
      <div className="topbar-info">
        <h1 className="topbar-title">{info.title}</h1>
        <p className="topbar-subtitle">{info.subtitle}</p>
      </div>

      <div className="topbar-actions">
        {/* Machine Stats Pill */}
        <div className="machine-stats-pill">
          <span className="stat-item">
            <strong>{machine.states.length}</strong> States
          </span>
          <span className="stat-separator">/</span>
          <span className="stat-item">
            <strong>{machine.transitions.length}</strong> Rules
          </span>
        </div>

        {/* New Machine Action */}
        <button
          className="btn btn-secondary"
          onClick={onNewMachine}
          title="Clear current machine and create a blank template"
        >
          <PlusCircle size={15} />
          <span>New Machine</span>
        </button>

        {/* Import / Export Action */}
        <button
          className="btn btn-secondary"
          onClick={onOpenImportExport}
          title="Import or Export JSON envelope (schema version 1)"
        >
          <UploadCloud size={15} />
          <span>Import / Export</span>
        </button>

        {/* Run Simulation Action */}
        <button
          className="btn btn-primary"
          onClick={onRunSimulation}
          disabled={isSimulating}
          title="Execute deterministic simulation on the current tape input"
        >
          {isSimulating ? (
            <>
              <RefreshCw size={15} className="spin" />
              <span>Simulating...</span>
            </>
          ) : (
            <>
              <Play size={15} />
              <span>Run Simulation</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};

