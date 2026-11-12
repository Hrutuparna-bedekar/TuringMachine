import React, { useEffect, useRef, useState } from 'react';
import { TuringMachine, Transition } from '../../types';
import { Plus, Trash2, AlertTriangle, ArrowRight, CornerDownRight } from 'lucide-react';

interface TransitionTableProps {
  machine: TuringMachine;
  onChange: (updated: TuringMachine) => void;
  activeTransitionIndex?: number;
  connectionDraft?: { source: string; target: string };
}

export const TransitionTable: React.FC<TransitionTableProps> = ({
  machine,
  onChange,
  activeTransitionIndex,
  connectionDraft,
}) => {
  const [newFromState, setNewFromState] = useState(machine.start_state || machine.states[0]?.id || '');
  const [newReadSymbol, setNewReadSymbol] = useState(machine.input_alphabet[0] || '0');
  const [newToState, setNewToState] = useState(machine.states[0]?.id || '');
  const [newWriteSymbol, setNewWriteSymbol] = useState(machine.input_alphabet[0] || '0');
  const [newMove, setNewMove] = useState<'L' | 'R'>('R');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const ruleForm = useRef<HTMLFormElement>(null);
  useEffect(() => {
    if (!connectionDraft) return;
    setNewFromState(connectionDraft.source);
    setNewToState(connectionDraft.target);
    setErrorMsg(null);
    ruleForm.current?.scrollIntoView({ block: 'nearest' });
    ruleForm.current?.querySelector('input')?.focus();
  }, [connectionDraft]);

  const tapeSet = new Set(machine.tape_alphabet);
  const finalSet = new Set(machine.final_states);

  // Check duplicate (from_state, read) keys
  const seenKeys = new Map<string, number>();
  const duplicateIndices = new Set<number>();

  machine.transitions.forEach((t, idx) => {
    const key = JSON.stringify([t.from_state, t.read]);
    if (seenKeys.has(key)) {
      duplicateIndices.add(idx);
      duplicateIndices.add(seenKeys.get(key)!);
    } else {
      seenKeys.set(key, idx);
    }
  });

  const handleDeleteRule = (index: number) => {
    const updated = machine.transitions.filter((_, idx) => idx !== index);
    onChange({ ...machine, transitions: updated });
  };

  const handleUpdateRule = (index: number, patch: Partial<Transition>) => {
    const updated = machine.transitions.map((t, idx) => (idx === index ? { ...t, ...patch } : t));
    onChange({ ...machine, transitions: updated });
  };

  const handleAddRule = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!machine.states.some((state) => state.id === newFromState)
        || !machine.states.some((state) => state.id === newToState)) {
      setErrorMsg('Please select valid From and To states.');
      return;
    }

    if (finalSet.has(newFromState)) {
      setErrorMsg(`State "${newFromState}" is marked as Final. Final states cannot have outgoing transitions.`);
      return;
    }

    if (!newReadSymbol || Array.from(newReadSymbol).length !== 1) {
      setErrorMsg('Read symbol must be exactly one character.');
      return;
    }

    if (!newWriteSymbol || Array.from(newWriteSymbol).length !== 1) {
      setErrorMsg('Write symbol must be exactly one character.');
      return;
    }

    // Auto-add read/write symbols to tape_alphabet if not already present
    let updatedTapeAlphabet = [...machine.tape_alphabet];
    if (!tapeSet.has(newReadSymbol)) {
      updatedTapeAlphabet.push(newReadSymbol);
    }
    if (!tapeSet.has(newWriteSymbol) && newWriteSymbol !== newReadSymbol) {
      updatedTapeAlphabet.push(newWriteSymbol);
    }

    const newRule: Transition = {
      from_state: newFromState,
      read: newReadSymbol,
      to_state: newToState,
      write: newWriteSymbol,
      move: newMove,
    };

    // Check determinism conflict
    const conflict = machine.transitions.some(
      (t) => t.from_state === newRule.from_state && t.read === newRule.read
    );
    if (conflict) {
      setErrorMsg(
        `Conflict: A rule for state "${newRule.from_state}" reading "${newRule.read}" already exists. Deterministic TMs permit only one rule per (state, symbol).`
      );
      return;
    }

    onChange({
      ...machine,
      tape_alphabet: updatedTapeAlphabet,
      transitions: [...machine.transitions, newRule],
    });

    // Reset default read symbol
    setErrorMsg(null);
  };

  return (
    <div className="table-panel-container">
      <div className="table-header-bar">
        <div className="table-title-group">
          <h3 className="section-title">Rules</h3>
          <span className="table-count-tag">{machine.transitions.length} rules</span>
        </div>
      </div>
      <p className="rule-help">A rule matches the current state and the symbol under the head. It tells the machine what to write, which way to move, and which state to enter.</p>

      {errorMsg && (
        <div className="table-alert-banner">
          <AlertTriangle size={14} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Rules Table */}
      <div className="table-scroll-wrapper">
        <table className="transition-matrix-table">
          <thead>
            <tr>
              <th style={{ width: '40px' }}>#</th>
              <th>From state</th>
              <th>Read</th>
              <th>Next state</th>
              <th>Write</th>
              <th>Move</th>
              <th style={{ width: '60px', textAlign: 'center' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {machine.transitions.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-table-cell">
                  No transition rules defined yet. Use the quick-add form below or create one on the canvas.
                </td>
              </tr>
            ) : (
              machine.transitions.map((t, idx) => {
                const isDuplicate = duplicateIndices.has(idx);
                const isFinalConflict = finalSet.has(t.from_state);
                const isReadMissing = !tapeSet.has(t.read);
                const isWriteMissing = !tapeSet.has(t.write);
                const hasError = isDuplicate || isFinalConflict || isReadMissing || isWriteMissing;
                const isActiveReplay = activeTransitionIndex === idx;

                return (
                  <tr
                    key={idx}
                    className={`transition-row ${hasError ? 'row-has-error' : ''} ${
                      isActiveReplay ? 'row-active-replay' : ''
                    }`}
                  >
                    <td className="row-num font-mono">{idx + 1}</td>

                    {/* From State */}
                    <td>
                      <select
                        aria-label={`From state for rule ${idx + 1}`}
                        value={t.from_state}
                        onChange={(e) => handleUpdateRule(idx, { from_state: e.target.value })}
                        className="table-select font-mono"
                      >
                        {machine.states.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.id} ({s.name})
                          </option>
                        ))}
                      </select>
                      {isFinalConflict && (
                        <div className="cell-error-tag">Final state cannot have outgoing rule!</div>
                      )}
                    </td>

                    {/* Read Symbol */}
                    <td>
                      <input
                        aria-label={`Read symbol for rule ${idx + 1}`}
                        type="text"
                        maxLength={2}
                        value={t.read}
                        onChange={(e) => handleUpdateRule(idx, { read: e.target.value })}
                        className="table-input-sym font-mono"
                      />
                      {isReadMissing && (
                        <div className="cell-error-tag">Not in tape alphabet</div>
                      )}
                      {isDuplicate && (
                        <div className="cell-error-tag">Non-deterministic duplicate key!</div>
                      )}
                    </td>

                    {/* To State */}
                    <td>
                      <select
                        aria-label={`Next state for rule ${idx + 1}`}
                        value={t.to_state}
                        onChange={(e) => handleUpdateRule(idx, { to_state: e.target.value })}
                        className="table-select font-mono"
                      >
                        {machine.states.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.id} ({s.name})
                          </option>
                        ))}
                      </select>
                    </td>

                    {/* Write Symbol */}
                    <td>
                      <input
                        aria-label={`Write symbol for rule ${idx + 1}`}
                        type="text"
                        maxLength={2}
                        value={t.write}
                        onChange={(e) => handleUpdateRule(idx, { write: e.target.value })}
                        className="table-input-sym font-mono"
                      />
                      {isWriteMissing && (
                        <div className="cell-error-tag">Not in tape alphabet</div>
                      )}
                    </td>

                    {/* Direction */}
                    <td>
                      <select
                        aria-label={`Move direction for rule ${idx + 1}`}
                        value={t.move}
                        onChange={(e) => handleUpdateRule(idx, { move: e.target.value as 'L' | 'R' })}
                        className="table-select-move font-mono"
                      >
                        <option value="R">Right</option>
                        <option value="L">Left</option>
                      </select>
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: 'center' }}>
                      <button
                        type="button"
                        onClick={() => handleDeleteRule(idx)}
                        className="table-del-btn"
                        title="Delete transition rule"
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Quick Add Rule Inline Form */}
      <form ref={ruleForm} onSubmit={handleAddRule} className="quick-add-rule-form">
        <div className="form-legend">
          <CornerDownRight size={14} />
          <span>Add a rule</span>
        </div>

        <div className="form-inputs-row">
          <div className="input-group">
            <label htmlFor="rule-from">From state</label>
            <select
              id="rule-from"
              value={newFromState}
              onChange={(e) => setNewFromState(e.target.value)}
              className="quick-select font-mono"
            >
              {machine.states.map((s) => (
                <option key={s.id} value={s.id} disabled={finalSet.has(s.id)}>
                  {s.id} {finalSet.has(s.id) ? '(Final - Invalid)' : `(${s.name})`}
                </option>
              ))}
            </select>
          </div>

          <div className="input-group symbol-group">
            <label htmlFor="rule-read">Read</label>
            <input
              id="rule-read"
              type="text"
              maxLength={2}
              value={newReadSymbol}
              onChange={(e) => setNewReadSymbol(e.target.value)}
              className="quick-input font-mono"
              placeholder="0"
            />
          </div>

          <div className="arrow-divider">
            <ArrowRight size={16} />
          </div>

          <div className="input-group">
            <label htmlFor="rule-next">Next state</label>
            <select
              id="rule-next"
              value={newToState}
              onChange={(e) => setNewToState(e.target.value)}
              className="quick-select font-mono"
            >
              {machine.states.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} ({s.name})
                </option>
              ))}
            </select>
          </div>

          <div className="input-group symbol-group">
            <label htmlFor="rule-write">Write</label>
            <input
              id="rule-write"
              type="text"
              maxLength={2}
              value={newWriteSymbol}
              onChange={(e) => setNewWriteSymbol(e.target.value)}
              className="quick-input font-mono"
              placeholder="1"
            />
          </div>

          <div className="input-group move-group">
            <label htmlFor="rule-move">Move</label>
            <select
              id="rule-move"
              value={newMove}
              onChange={(e) => setNewMove(e.target.value as 'L' | 'R')}
              className="quick-select font-mono"
            >
              <option value="R">Right</option>
              <option value="L">Left</option>
            </select>
          </div>

          <div className="input-group btn-group">
            <label>&nbsp;</label>
            <button type="submit" className="btn btn-primary-soft add-rule-btn">
              <Plus size={14} />
              <span>Add Rule</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

