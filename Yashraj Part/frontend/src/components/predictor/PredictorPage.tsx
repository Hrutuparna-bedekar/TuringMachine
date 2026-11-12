import React, { useState } from 'react';
import { TuringMachine, MultiBudgetPrediction } from '../../types';
import { predictBoundedHalting } from '../../api';
import {
  Cpu,
  Sparkles,
  AlertCircle,
  HelpCircle,
  RefreshCw,
} from 'lucide-react';

interface PredictorPageProps {
  machine: TuringMachine;
  input: string;
}

export const PredictorPage: React.FC<PredictorPageProps> = ({ machine, input }) => {
  const [predictions, setPredictions] = useState<MultiBudgetPrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunPrediction = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await predictBoundedHalting(machine, input);
      setPredictions(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const budgets: Array<50 | 200 | 1000> = [50, 200, 1000];
  const budgetColors: Record<number, 'yellow' | 'pink' | 'blue'> = {
    50: 'yellow',
    200: 'pink',
    1000: 'blue',
  };

  return (
    <div className="predictor-page-container">
      {/* Intro Header Card */}
      <div className="predictor-header-card">
        <div className="header-icon-box">
          <Cpu size={24} className="text-teal" />
        </div>
        <div className="header-text-group">
          <div className="header-tag-pill">PHASE 2 • RESEARCH ENGINE</div>
          <h2 className="page-title">Bounded Halting Predictor</h2>
          <p className="page-subtitle">
            Combines 10-step prefix trace observation with machine learning classification for still-active machines across finite budgets.
          </p>
        </div>

        <div className="header-action-group">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleRunPrediction}
            disabled={loading}
          >
            {loading ? (
              <>
                <RefreshCw size={15} className="spin" />
                <span>Evaluating...</span>
              </>
            ) : (
              <>
                <Sparkles size={15} />
                <span>Predict Halting</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="predictor-alert error">
          <AlertCircle size={16} />
          <span>Prediction Failed: {error}</span>
        </div>
      )}

      {/* Target Input Overview */}
      <div className="current-target-strip">
        <span className="strip-label">Evaluating Machine on Input:</span>
        <code className="strip-code font-mono">"{input}"</code>
        <span className="strip-meta font-mono">({machine.states.length} states, {machine.transitions.length} rules)</span>
      </div>

      {/* 3 Budget Cards Grid */}
      <div className="budget-cards-grid">
        {budgets.map((b) => {
          const item = predictions ? predictions[b] : null;
          const cardColor = budgetColors[b];

          return (
            <div key={b} className={`budget-card card-${cardColor}`}>
              <div className="budget-card-header">
                <span className="budget-tag font-mono">BUDGET: {b} STEPS</span>
                {item && (
                  <span
                    className={`source-badge ${item.source === 'observed' ? 'source-observed' : 'source-model'}`}
                  >
                    {item.source === 'observed' ? 'Direct Observation' : 'ML Model'}
                  </span>
                )}
              </div>

              <div className="budget-card-body">
                {item ? (
                  <>
                    <div className="prediction-outcome-tag">
                      {item.predicted_halted_within_limit ? (
                        <span className="outcome-halted">HALTS ≤ {b} STEPS</span>
                      ) : (
                        <span className="outcome-active">STILL ACTIVE &gt; {b} STEPS</span>
                      )}
                    </div>

                    {item.source === 'observed' ? (
                      <div className="observed-info-box">
                        <div className="info-row">
                          <span>Prefix Observation:</span>
                          <strong className="font-mono">Halted early at step {item.observed_steps}</strong>
                        </div>
                        <div className="info-row">
                          <span>Stop Reason:</span>
                          <code className="font-mono">{item.stop_reason}</code>
                        </div>
                      </div>
                    ) : (
                      <div className="model-info-box">
                        <div className="score-row">
                          <span className="score-label">Halt Score:</span>
                          <span className="score-val font-mono">
                            {item.halt_score !== undefined ? item.halt_score.toFixed(4) : '—'}
                          </span>
                        </div>

                        {/* Visual Score Meter */}
                        <div className="score-meter-track">
                          <div
                            className="score-meter-fill"
                            style={{
                              width: `${Math.round((item.halt_score || 0) * 100)}%`,
                            }}
                          />
                        </div>

                        <div className="model-meta-row font-mono">
                          <span>Model ID: {item.model_id}</span>
                          <span>Prefix: {item.observed_steps} steps</span>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="budget-card-placeholder">
                    <p>Click "Predict Halting" above to evaluate bounded halting at budget {b}.</p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Theoretical Context Card */}
      <div className="theoretical-notice-card">
        <div className="notice-icon">
          <HelpCircle size={22} className="text-teal" />
        </div>
        <div className="notice-content">
          <h4 className="notice-title">Bounded Halting vs The General Halting Problem</h4>
          <p className="notice-text">
            Alan Turing proved in 1936 that the <em>general halting problem</em> (determining whether an arbitrary Turing machine halts on an arbitrary input) is undecidable.
          </p>
          <p className="notice-text">
            However, <strong>bounded halting</strong> asks: <em>"Does this machine halt in at most B executed steps?"</em> Because B is finite, the bounded problem is strictly decidable and can be evaluated or approximated via prefix trace simulation and statistical pattern recognition. Model scores are empirical estimates and not mathematical proofs of unbounded termination.
          </p>
        </div>
      </div>
    </div>
  );
};

