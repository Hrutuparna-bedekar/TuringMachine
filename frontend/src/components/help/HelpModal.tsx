import React from 'react';
import { X } from 'lucide-react';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog-panel help-modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <h3 className="modal-title">Theory of Computation Reference Guide</h3>
            <span className="modal-schema-tag">DETERMINISTIC 1-TAPE TM</span>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body help-body">
          {/* Section 1: Formal Definition */}
          <div className="help-section">
            <h4 className="help-section-title">1. Formal 7-Tuple Definition</h4>
            <p className="help-text">
              In formal language theory, a Deterministic Turing Machine (DTM) is defined as a 7-tuple:
            </p>
            <div className="math-callout font-mono">
              M = (Q, Σ, Γ, δ, q₀, □, F)
            </div>
            <ul className="help-list">
              <li><strong>Q:</strong> Finite, non-empty set of discrete states.</li>
              <li><strong>Σ:</strong> Input alphabet of symbols allowed in the initial tape string (excluding □).</li>
              <li><strong>Γ:</strong> Tape alphabet, where Σ ⊂ Γ and □ ∈ Γ.</li>
              <li><strong>δ:</strong> Deterministic transition function δ: (Q \ F) × Γ → Q × Γ × {'{L, R}'}.</li>
              <li><strong>q₀:</strong> Initial start state (q₀ ∈ Q).</li>
              <li><strong>□:</strong> Designated blank symbol representing an unwritten tape cell.</li>
              <li><strong>F:</strong> Set of accepting or terminal final states (F ⊆ Q).</li>
            </ul>
          </div>

          {/* Section 2: Operational Semantics */}
          <div className="help-section">
            <h4 className="help-section-title">2. Operational & Tape Semantics</h4>
            <ul className="help-list">
              <li><strong>Tape:</strong> A discrete 1-dimensional tape extending infinitely in both directions (signed indices ... -2, -1, 0, 1, 2 ...).</li>
              <li><strong>Head:</strong> The read/write head starts at index <code>0</code>. The input word <em>w</em> is placed on cells <code>0 .. |w|-1</code>. All other cells are initialized to blank <code>□</code>.</li>
              <li><strong>Determinism:</strong> For any state <em>q</em> and tape symbol <em>σ</em>, there is at most one transition rule defined.</li>
              <li><strong>Final States:</strong> States in <em>F</em> have no outgoing transitions; entering any state in <em>F</em> immediately halts the computation.</li>
            </ul>
          </div>

          {/* Section 3: Halting Classifications */}
          <div className="help-section">
            <h4 className="help-section-title">3. Halting Classifications</h4>
            <div className="help-cards-grid">
              <div className="help-card card-sage">
                <div className="card-badge">final_state</div>
                <h5>Accepting Halt</h5>
                <p>The current state belongs to <em>F</em>. Execution stops immediately with positive acceptance.</p>
              </div>

              <div className="help-card card-blue">
                <div className="card-badge">missing_transition</div>
                <h5>Missing Transition</h5>
                <p>No rule exists for the current state and scanned symbol. The machine halts without consuming extra steps.</p>
              </div>

              <div className="help-card card-yellow">
                <div className="card-badge">step_limit</div>
                <h5>Budget Limit Reached</h5>
                <p>The configured finite step limit was reached while the machine was still active. This is not a proof of non-termination.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

