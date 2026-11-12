import React, { useState } from 'react';
import { TuringMachine } from '../../types';
import { validateMachineSemantics } from '../../utils/tape';
import { Sliders, AlertCircle } from 'lucide-react';

interface MachineConfigurationPanelProps {
  machine: TuringMachine;
  inputText: string;
  stepLimit: number;
  onChangeMachine: (updated: TuringMachine) => void;
  onChangeInputText: (val: string) => void;
  onChangeStepLimit: (val: number) => void;
  onLoadExample: () => void;
}

export const MachineConfigurationPanel: React.FC<MachineConfigurationPanelProps> = ({
  machine,
  inputText,
  stepLimit,
  onChangeMachine,
  onChangeInputText,
  onChangeStepLimit,
  onLoadExample,
}) => {
  const [newTapeSym, setNewTapeSym] = useState('');
  const [newInputSym, setNewInputSym] = useState('');

  const issues = validateMachineSemantics(machine, inputText);
  const errorCount = issues.filter((i) => i.type === 'error').length;

  const handleAddInputSymbol = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newInputSym || Array.from(newInputSym).length !== 1) return;
    if (machine.input_alphabet.includes(newInputSym)) return;
    if (newInputSym === machine.blank_symbol) {
      alert('Blank symbol cannot belong to input alphabet.');
      return;
    }

    const updatedInputAlpha = [...machine.input_alphabet, newInputSym];
    let updatedTapeAlpha = [...machine.tape_alphabet];
    if (!updatedTapeAlpha.includes(newInputSym)) {
      updatedTapeAlpha.push(newInputSym);
    }

    onChangeMachine({
      ...machine,
      input_alphabet: updatedInputAlpha,
      tape_alphabet: updatedTapeAlpha,
    });
    setNewInputSym('');
  };

  const handleRemoveInputSymbol = (sym: string) => {
    if (machine.input_alphabet.length <= 1) {
      alert('Input alphabet must have at least one symbol.');
      return;
    }
    onChangeMachine({
      ...machine,
      input_alphabet: machine.input_alphabet.filter((s) => s !== sym),
    });
  };

  const handleAddTapeSymbol = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTapeSym || Array.from(newTapeSym).length !== 1) return;
    if (machine.tape_alphabet.includes(newTapeSym)) return;

    onChangeMachine({
      ...machine,
      tape_alphabet: [...machine.tape_alphabet, newTapeSym],
    });
    setNewTapeSym('');
  };

  const handleRemoveTapeSymbol = (sym: string) => {
    if (sym === machine.blank_symbol) {
      alert('Cannot remove designated blank symbol from tape alphabet.');
      return;
    }
    if (machine.input_alphabet.includes(sym)) {
      alert('Cannot remove a symbol that is still in the input alphabet.');
      return;
    }
    onChangeMachine({
      ...machine,
      tape_alphabet: machine.tape_alphabet.filter((s) => s !== sym),
    });
  };

  const handleSetBlankSymbol = (newBlank: string) => {
    if (!newBlank || Array.from(newBlank).length !== 1) return;
    if (machine.input_alphabet.includes(newBlank)) {
      alert('Blank symbol must not belong to input alphabet.');
      return;
    }
    let updatedTapeAlpha = [...machine.tape_alphabet];
    if (!updatedTapeAlpha.includes(newBlank)) {
      updatedTapeAlpha.push(newBlank);
    }
    onChangeMachine({
      ...machine,
      blank_symbol: newBlank,
      tape_alphabet: updatedTapeAlpha,
    });
  };

  return (
    <div className="config-panel-container">
      <div className="config-header">
        <Sliders size={16} className="config-icon" />
        <h3 className="section-title">Simulation setup</h3>
      </div>

      <div className="simulation-inputs-bar">
        <div className="sim-input-field">
          <label className="sim-label" htmlFor="tape-input">Tape input</label>
          <input
            id="tape-input"
            type="text"
            value={inputText}
            onChange={(e) => onChangeInputText(e.target.value)}
            placeholder="e.g. 101"
            className="input-text-field font-mono"
          />
        </div>
        <div className="sim-step-field">
          <label className="sim-label" htmlFor="step-budget">Step limit</label>
          <input
            id="step-budget"
            type="number"
            min={0}
            max={1000}
            value={stepLimit}
            onChange={(e) => onChangeStepLimit(Math.max(0, Math.min(1000, Math.trunc(Number(e.target.value) || 0))))}
            className="input-step-field font-mono"
          />
        </div>
      </div>

      <div className="workspace-example">
        <button type="button" className="btn btn-secondary" onClick={onLoadExample}>
          Load Scan to Blank
        </button>
        <p>Load the example, then click <strong>Run Simulation</strong>. With input <code>101</code>, it halts at step 4.</p>
      </div>

      <details className="machine-settings">
        <summary>Symbols and start state</summary>
        <div className="config-grid">
          {/* Alphabets Configuration Card */}
          <div className="config-card">
            <div className="card-label">Allowed input symbols</div>
            <div className="chips-container">
              {machine.input_alphabet.map((sym) => (
                <span key={sym} className="alphabet-chip font-mono">
                  {sym}
                  <button
                    type="button"
                    onClick={() => handleRemoveInputSymbol(sym)}
                    className="chip-remove-btn"
                    title="Remove symbol"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <form onSubmit={handleAddInputSymbol} className="chip-add-form">
              <input
                type="text"
                maxLength={2}
                value={newInputSym}
                aria-label="Add input symbol"
                onChange={(e) => setNewInputSym(e.target.value)}
                placeholder="+ add"
                className="chip-add-input font-mono"
              />
            </form>
          </div>

          {/* Tape Alphabet Configuration Card */}
          <div className="config-card">
            <div className="card-label">Symbols the tape can hold</div>
            <div className="chips-container">
              {machine.tape_alphabet.map((sym) => (
                <span
                  key={sym}
                  className={`alphabet-chip font-mono ${sym === machine.blank_symbol ? 'chip-blank' : ''}`}
                >
                  {sym}
                  {sym === machine.blank_symbol ? (
                    <span className="blank-tag">Blank</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleRemoveTapeSymbol(sym)}
                      className="chip-remove-btn"
                      title="Remove symbol"
                    >
                      ×
                    </button>
                  )}
                </span>
              ))}
            </div>
            <form onSubmit={handleAddTapeSymbol} className="chip-add-form">
              <input
                type="text"
                maxLength={2}
                value={newTapeSym}
                aria-label="Add tape symbol"
                onChange={(e) => setNewTapeSym(e.target.value)}
                placeholder="+ add"
                className="chip-add-input font-mono"
              />
            </form>
          </div>

          {/* Blank Symbol & Start State */}
          <div className="config-card">
            <div className="card-label">Blank symbol</div>
            <div className="blank-selector-row">
              {['□', '_', '#', 'B'].map((sym) => (
                <button
                  key={sym}
                  type="button"
                  className={`blank-select-btn font-mono ${machine.blank_symbol === sym ? 'active' : ''}`}
                  onClick={() => handleSetBlankSymbol(sym)}
                >
                  {sym}
                </button>
              ))}
              <input
                type="text"
                maxLength={2}
                value={machine.blank_symbol}
                aria-label="Custom blank symbol"
                onChange={(e) => handleSetBlankSymbol(e.target.value)}
                className="blank-custom-input font-mono"
                title="Custom single unicode character"
              />
            </div>
          </div>

          {/* Start State & Final States */}
          <div className="config-card">
            <label className="card-label" htmlFor="start-state">Start state</label>
            <select
              id="start-state"
              value={machine.start_state}
              onChange={(e) => onChangeMachine({ ...machine, start_state: e.target.value })}
              className="config-select font-mono"
            >
              {machine.states.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} ({s.name})
                </option>
              ))}
            </select>
          </div>
        </div>
      </details>

      {/* Validation Checklist / Alert Banner */}
      {issues.length > 0 && (
        <div className={`validation-summary ${errorCount > 0 ? 'has-errors' : 'has-warnings'}`}>
          <div className="summary-title">
            <AlertCircle size={15} />
            <span>Check your machine or input</span>
          </div>
          <ul className="issues-list">
            {issues.map((issue, idx) => (
              <li key={idx} className={`issue-item ${issue.type}`}>
                {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

