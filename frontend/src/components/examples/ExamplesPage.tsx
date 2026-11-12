import React from 'react';
import { EXAMPLE_MACHINES, ExampleMachineItem } from '../../utils/examples';
import { Play, Check } from 'lucide-react';

interface ExamplesPageProps {
  onLoadExample: (example: ExampleMachineItem) => void;
  currentMachineId?: string;
}

export const ExamplesPage: React.FC<ExamplesPageProps> = ({ onLoadExample, currentMachineId }) => {
  return (
    <div className="examples-page-container">
      {/* Header Banner */}
      <div className="examples-header-banner">
        <div className="header-sticker-tag">AUTOMATA ARCHIVE</div>
        <h2 className="page-title">Curated Machine Library</h2>
        <p className="page-subtitle">
          Classical deterministic Turing machine configurations demonstrating scanning, rewriting, cycling, and binary arithmetic. Click any machine to load it into your active workspace.
        </p>
      </div>

      {/* Examples Grid */}
      <div className="examples-grid">
        {EXAMPLE_MACHINES.map((item) => {
          const isLoaded = currentMachineId === item.id;
          return (
            <div key={item.id} className={`example-card card-${item.accentColor}`}>
              <div className="example-card-top">
                <span className="card-tagline">{item.tagline}</span>
                <span className="card-badge font-mono">{item.data.machine.states.length} States</span>
              </div>

              <h3 className="card-title">{item.title}</h3>
              <p className="card-desc">{item.description}</p>

              <div className="example-spec-details font-mono">
                <div className="spec-row">
                  <span className="spec-label">Input Alphabet (Σ):</span>
                  <span className="spec-val">[{item.data.machine.input_alphabet.join(', ')}]</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Tape Alphabet (Γ):</span>
                  <span className="spec-val">[{item.data.machine.tape_alphabet.join(', ')}]</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Default Input:</span>
                  <span className="spec-val">"{item.defaultInput}"</span>
                </div>
                <div className="spec-row">
                  <span className="spec-label">Rules Count (δ):</span>
                  <span className="spec-val">{item.data.machine.transitions.length} transitions</span>
                </div>
              </div>

              <div className="example-card-actions">
                <button
                  type="button"
                  className={`btn-load-example ${isLoaded ? 'already-loaded' : ''}`}
                  onClick={() => onLoadExample(item)}
                >
                  {isLoaded ? (
                    <>
                      <Check size={15} />
                      <span>Currently Loaded</span>
                    </>
                  ) : (
                    <>
                      <Play size={15} />
                      <span>Load into Workspace</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

