import React from 'react';
import { SimulationResponse, TuringMachine } from '../../types';
import {
  CheckCircle2,
  Clock,
  Info,
  AlertTriangle,
} from 'lucide-react';

interface ResultsPanelProps {
  simulationResult: SimulationResponse | null;
  machine: TuringMachine;
  loading: boolean;
  error: string | null;
}

const STOP_REASON_DESCRIPTIONS: Record<
  string,
  { label: string; explanation: string; variant: 'success' | 'warning' | 'info' }
> = {
  final_state: {
    label: 'Halted: Reached Final State',
    explanation: 'The Turing machine entered an accepting terminal state declared in final_states.',
    variant: 'success',
  },
  missing_transition: {
    label: 'Halted: Missing Transition Rule',
    explanation:
      'The machine halted because no transition rule matches the current active state and tape symbol. Zero further steps consumed.',
    variant: 'info',
  },
  step_limit: {
    label: 'Step Budget Exhausted (Active)',
    explanation:
      'The machine was still active and able to execute transitions, but the configured finite step budget was reached. (Note: this is not proof that the machine would never halt on an infinite budget).',
    variant: 'warning',
  },
};

export const ResultsPanel: React.FC<ResultsPanelProps> = ({
  simulationResult,
  machine,
  loading,
  error,
}) => {
  if (loading) {
    return (
      <div className="results-card loading-state">
        <div className="loading-spinner-circle" />
        <h4 className="results-title">Executing Deterministic Simulation...</h4>
        <p className="results-desc">Calling FastAPI backend simulation engine (/api/simulate)</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-card error-state">
        <div className="results-error-header">
          <AlertTriangle size={20} className="error-icon" />
          <h4 className="results-title">Simulation Request Rejected</h4>
        </div>
        <div className="error-detail-box font-mono">{error}</div>
        <p className="results-desc">
          Check input alphabet constraints, state IDs, or ensure symbols match single Unicode scalar values.
        </p>
      </div>
    );
  }

  if (!simulationResult) {
    return (
      <div className="results-card empty-state">
        <div className="empty-icon-box">
          <Info size={20} />
        </div>
        <h4 className="results-title">Execution Results</h4>
        <p className="results-desc">
          No simulation executed yet. Define machine transitions and click <strong>Run Simulation</strong> to view execution diagnostics.
        </p>
      </div>
    );
  }

  const reasonInfo = STOP_REASON_DESCRIPTIONS[simulationResult.stop_reason] || {
    label: simulationResult.stop_reason,
    explanation: 'Simulation stopped.',
    variant: 'info',
  };

  // Compute metrics from trace
  const visitedStates = new Set<string>([simulationResult.initial.state]);
  let minHead = simulationResult.initial.head;
  let maxHead = simulationResult.initial.head;

  simulationResult.trace.forEach((t) => {
    visitedStates.add(t.state_after);
    minHead = Math.min(minHead, t.head_after);
    maxHead = Math.max(maxHead, t.head_after);
  });

  const finalStateId =
    simulationResult.trace.length > 0
      ? simulationResult.trace[simulationResult.trace.length - 1].state_after
      : simulationResult.initial.state;
  const finalStateObj = machine.states.find((s) => s.id === finalStateId);

  return (
    <div className={`results-card status-${reasonInfo.variant}`}>
      {/* Halting Status Banner */}
      <div className="results-header-banner">
        <div className="banner-icon">
          {simulationResult.halted_within_limit ? (
            <CheckCircle2 size={22} className="text-success" />
          ) : (
            <Clock size={22} className="text-warning" />
          )}
        </div>
        <div className="banner-titles">
          <div className="banner-status-badge font-mono">
            {simulationResult.halted_within_limit ? 'HALTED WITHIN BUDGET' : 'LIMIT REACHED'}
          </div>
          <h3 className="banner-reason-title">{reasonInfo.label}</h3>
        </div>
      </div>

      <p className="reason-explanation">{reasonInfo.explanation}</p>

      {/* Metrics Grid */}
      <div className="results-metrics-grid">
        <div className="metric-box">
          <div className="metric-label">Executed Steps</div>
          <div className="metric-val font-mono">{simulationResult.steps}</div>
        </div>

        <div className="metric-box">
          <div className="metric-label">Terminal State</div>
          <div className="metric-val font-mono">
            {finalStateId}
            {finalStateObj ? ` (${finalStateObj.name})` : ''}
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-label">Distinct States Visited</div>
          <div className="metric-val font-mono">
            {visitedStates.size} / {machine.states.length}
          </div>
        </div>

        <div className="metric-box">
          <div className="metric-label">Tape Head Range</div>
          <div className="metric-val font-mono">
            [{minHead} .. {maxHead}] ({maxHead - minHead + 1} cells)
          </div>
        </div>
      </div>

      {/* Stop Reason Code Pill */}
      <div className="results-footer-info">
        <span className="footer-tag">API stop_reason:</span>
        <code className="font-mono">{simulationResult.stop_reason}</code>
      </div>
    </div>
  );
};

