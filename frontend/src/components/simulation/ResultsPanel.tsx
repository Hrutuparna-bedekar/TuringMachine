import React from 'react';
import { SimulationResponse, TuringMachine } from '../../types';
import { reconstructTapeAtStep } from '../../utils/tape';
import {
  CheckCircle2,
  XCircle,
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

interface OutcomeMeta {
  statusTag: 'ACCEPTED' | 'REJECTED' | 'LIMIT REACHED';
  label: string;
  explanation: string;
  variant: 'success' | 'danger' | 'warning';
}

const OUTCOME_CONFIG: Record<string, OutcomeMeta> = {
  final_state: {
    statusTag: 'ACCEPTED',
    label: 'ACCEPTED — Final State Reached',
    explanation:
      'The Turing machine accepted the input string. Execution halted because the active state entered the set of declared final accepting states (F).',
    variant: 'success',
  },
  missing_transition: {
    statusTag: 'REJECTED',
    label: 'REJECTED — No Transition Defined',
    explanation:
      'The Turing machine rejected the input string. Execution halted because no transition rule matches the active state and tape symbol, and the state is not an accepting final state.',
    variant: 'danger',
  },
  step_limit: {
    statusTag: 'LIMIT REACHED',
    label: 'SAFETY LIMIT REACHED — Timeout',
    explanation:
      'The simulation exceeded the configured computational safety step limit while still active and executing transitions. (Note: this is a safety cutoff to prevent runaway loops, not proof that the machine would never halt on an infinite budget — the General Halting Problem is undecidable).',
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
        <p className="results-desc">Calling FastAPI simulation engine with sparse bidirectional tape</p>
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
          Check alphabet symbols, state IDs, or ensure all characters match single Unicode scalar values.
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
          No simulation executed yet. Configure machine transitions and click <strong>Run Simulation</strong> to compute and replay the trace.
        </p>
      </div>
    );
  }

  const outcome = OUTCOME_CONFIG[simulationResult.stop_reason] || {
    statusTag: simulationResult.halted_within_limit ? 'ACCEPTED' : 'LIMIT REACHED',
    label: simulationResult.stop_reason,
    explanation: 'Simulation halted.',
    variant: simulationResult.halted_within_limit ? 'success' : 'warning',
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
  const { tapeMap } = reconstructTapeAtStep(
    simulationResult.initial,
    simulationResult.trace,
    simulationResult.steps,
    machine.blank_symbol
  );
  const writtenCells = Object.keys(tapeMap)
    .map(Number)
    .filter((pos) => tapeMap[pos] !== machine.blank_symbol);
  const first = writtenCells.length ? Math.min(...writtenCells) : 0;
  const last = writtenCells.length ? Math.max(...writtenCells) : 0;
  const tapeOutput = writtenCells.length
    ? Array.from({ length: last - first + 1 }, (_, index) => tapeMap[first + index]).join('')
    : '';

  return (
    <div className={`results-card run-result status-${outcome.variant}`}>
      <div className="results-primary">
        <div className="results-header-banner">
          <div className="banner-icon">
            {outcome.variant === 'success' && (
              <CheckCircle2 size={20} className="text-success" />
            )}
            {outcome.variant === 'danger' && (
              <XCircle size={20} className="text-danger" />
            )}
            {outcome.variant === 'warning' && (
              <Clock size={20} className="text-warning" />
            )}
          </div>
          <div className="banner-titles">
            <div className="banner-badge-row">
              <span className={`status-pill badge-${outcome.variant}`}>
                {outcome.statusTag}
              </span>
              <span className="result-stop-summary">
                Step {simulationResult.steps} · Final state: <strong>{finalStateObj?.name ?? finalStateId}</strong>
              </span>
            </div>
            <h3 className="banner-reason-title">{outcome.label}</h3>
          </div>
        </div>
        <div className="tape-output">
          <h3>{simulationResult.halted_within_limit ? 'Final Tape Contents' : 'Tape at Step Limit'}</h3>
          <code aria-label="Tape contents at the end of the run" className="font-mono">{tapeOutput || '□ (Empty Tape)'}</code>
        </div>
      </div>

      <details className="run-details" open>
        <summary>Execution Details & Theoretical Analysis</summary>
        <p className="reason-explanation">{outcome.explanation}</p>
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
      </details>
    </div>
  );
};
