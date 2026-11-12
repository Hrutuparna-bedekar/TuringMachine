import React from 'react';
import { TuringMachine, ActiveView } from '../../types';
import { EXAMPLE_MACHINES, ExampleMachineItem } from '../../utils/examples';
import {
  ArrowRight,
  PlusCircle,
  Play,
  Network,
  Cpu,
  BookOpen,
} from 'lucide-react';

interface DashboardPageProps {
  machine: TuringMachine;
  onNavigate: (view: ActiveView) => void;
  onLoadExample: (example: ExampleMachineItem) => void;
  onNewMachine: () => void;
  apiStatus: string;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  machine,
  onNavigate,
  onLoadExample,
  onNewMachine,
  apiStatus,
}) => {
  return (
    <div className="dashboard-page-container">
      {/* Welcome Banner */}
      <div className="dashboard-hero-card">
        <div className="hero-text-content">
          <div className="hero-badge-tag">THEORY OF COMPUTATION WORKSPACE</div>
          <h2 className="hero-heading">Welcome to the Turing Machine Simulator</h2>
          <p className="hero-description">
            A precise technical workbench for constructing deterministic Turing machines, visualizing state transition graphs, simulating tape execution with step-by-step trace replay, and investigating bounded-halting predictions.
          </p>
          <div className="hero-cta-row">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigate('workspace')}
            >
              <Network size={16} />
              <span>Open Machine Workspace</span>
              <ArrowRight size={15} />
            </button>

            <button
              type="button"
              className="btn btn-secondary"
              onClick={onNewMachine}
            >
              <PlusCircle size={16} />
              <span>New Machine Template</span>
            </button>
          </div>
        </div>
      </div>

      {/* Pastel Feature Cards Grid (Reference 2) */}
      <div className="dashboard-cards-grid">
        {/* Card 1: Active Machine Status (Pastel Powder Blue) */}
        <div className="dash-card card-blue">
          <div className="dash-card-header">
            <div className="card-pill">ACTIVE MODEL</div>
            <Network size={18} />
          </div>
          <h3 className="dash-card-title">Current Machine</h3>
          <p className="dash-card-desc">
            Currently loaded with <strong>{machine.states.length}</strong> states and{' '}
            <strong>{machine.transitions.length}</strong> transitions.
          </p>
          <div className="dash-stat-row font-mono">
            <span>Start: {machine.start_state}</span>
            <span>Finals: [{machine.final_states.join(', ')}]</span>
          </div>
          <button
            type="button"
            className="dash-link-btn"
            onClick={() => onNavigate('workspace')}
          >
            <span>Edit in Graph Canvas</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {/* Card 2: Exact Simulation (Pastel Sage) */}
        <div className="dash-card card-sage">
          <div className="dash-card-header">
            <div className="card-pill">SIMULATION ENGINE</div>
            <Play size={18} />
          </div>
          <h3 className="dash-card-title">Tape Simulation</h3>
          <p className="dash-card-desc">
            Deterministic execution over infinite 2-way tape with full chronological trace logging and backward replay.
          </p>
          <div className="dash-stat-row">
            <span>Backend: {apiStatus === 'ok' ? 'FastAPI Connected' : 'Local Standalone'}</span>
          </div>
          <button
            type="button"
            className="dash-link-btn"
            onClick={() => onNavigate('simulation')}
          >
            <span>Open Tape Replay</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {/* Card 3: ML Predictor (Pastel Yellow) */}
        <div className="dash-card card-yellow">
          <div className="dash-card-header">
            <div className="card-pill">RESEARCH ENGINE</div>
            <Cpu size={18} />
          </div>
          <h3 className="dash-card-title">Bounded Halting</h3>
          <p className="dash-card-desc">
            Evaluates finite termination across 50, 200, and 1,000 steps using prefix observation and learned feature classifiers.
          </p>
          <div className="dash-stat-row font-mono">
            <span>Budgets: 50 / 200 / 1000</span>
          </div>
          <button
            type="button"
            className="dash-link-btn"
            onClick={() => onNavigate('predictor')}
          >
            <span>View Predictor</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {/* Card 4: Automata Library (Pastel Pink) */}
        <div className="dash-card card-pink">
          <div className="dash-card-header">
            <div className="card-pill">ARCHIVE</div>
            <BookOpen size={18} />
          </div>
          <h3 className="dash-card-title">Classical Examples</h3>
          <p className="dash-card-desc">
            Explore canonical automata including Scan to Blank, Symbol Replacement, Ping-Pong Cycle, and Binary Incrementer.
          </p>
          <div className="dash-stat-row font-mono">
            <span>{EXAMPLE_MACHINES.length} curated templates</span>
          </div>
          <button
            type="button"
            className="dash-link-btn"
            onClick={() => onNavigate('examples')}
          >
            <span>Browse Library</span>
            <ArrowRight size={13} />
          </button>
        </div>
      </div>

      {/* Quick Start Machines Section */}
      <div className="dashboard-quickstart-section">
        <div className="section-header-row">
          <h3 className="section-title">Quick-Start Machine Templates</h3>
          <button
            type="button"
            className="view-all-link"
            onClick={() => onNavigate('examples')}
          >
            View all ({EXAMPLE_MACHINES.length}) →
          </button>
        </div>

        <div className="quickstart-cards-grid">
          {EXAMPLE_MACHINES.slice(0, 3).map((item) => (
            <div key={item.id} className="quickstart-item-card">
              <div className="item-header">
                <span className="item-tagline">{item.tagline}</span>
                <span className="item-states font-mono">{item.data.machine.states.length} States</span>
              </div>
              <h4 className="item-title">{item.title}</h4>
              <p className="item-desc">{item.description}</p>
              <div className="item-footer">
                <span className="item-input font-mono">Input: "{item.defaultInput}"</span>
                <button
                  type="button"
                  className="item-load-btn"
                  onClick={() => onLoadExample(item)}
                >
                  <Play size={13} />
                  <span>Load</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

