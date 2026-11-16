import React, { useState } from 'react';
import {
  SimulationResponse,
  TuringMachine,
} from '../../types';
import { reconstructTapeAtStep } from '../../utils/tape';
import {
  RotateCcw,
  SkipBack,
  Play,
  Pause,
  SkipForward,
  FastForward,
  ChevronLeft,
  ChevronRight,
  Clock,
  Navigation,
} from 'lucide-react';

export interface TapePlayerProps {
  simulationResult: SimulationResponse | null;
  machine: TuringMachine;
  currentStep: number;
  isPlaying: boolean;
  playbackSpeed: number;
  onStepChange: (step: number) => void;
  onTogglePlay: () => void;
  onSetSpeed: (speed: number) => void;
  onReset: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onJumpToEnd: () => void;
}

export const TapePlayer: React.FC<TapePlayerProps> = ({
  simulationResult,
  machine,
  currentStep,
  isPlaying,
  playbackSpeed,
  onStepChange,
  onTogglePlay,
  onSetSpeed,
  onReset,
  onStepBack,
  onStepForward,
  onJumpToEnd,
}) => {
  const [tapeWindowOffset, setTapeWindowOffset] = useState<number>(0);

  const totalSteps = simulationResult?.trace?.length || 0;

  if (!simulationResult) {
    return (
      <div className="tape-player-empty-card">
        <div className="empty-tape-icon">
          <Navigation size={28} />
        </div>
        <h4 className="empty-tape-title">Virtual Tape Controller Ready</h4>
        <p className="empty-tape-desc">
          Click <strong>Run Simulation</strong> to compute the execution trace and explore step-by-step tape playback.
        </p>
      </div>
    );
  }

  // Reconstruct exact tape state at current step
  const tapeState = reconstructTapeAtStep(
    simulationResult.initial,
    simulationResult.trace,
    currentStep,
    machine.blank_symbol
  );

  // Compute rendered range centered around head + user offset
  const baseRange = 4; // cells on each side
  const startPos = tapeState.head - baseRange + tapeWindowOffset;
  const endPos = tapeState.head + baseRange + tapeWindowOffset;
  const cellPositions: number[] = [];
  for (let p = startPos; p <= endPos; p++) {
    cellPositions.push(p);
  }

  const currentStateObj = machine.states.find((s) => s.id === tapeState.state);
  const nextEvent = currentStep < totalSteps ? simulationResult.trace[currentStep] : null;
  const currentScannedSym =
    tapeState.tapeMap[tapeState.head] !== undefined ? tapeState.tapeMap[tapeState.head] : machine.blank_symbol;

  return (
    <div className="tape-player-container">
      <h3 className="section-title">Tape playback</h3>
      {/* Player Header & Current Step Status */}
      <div className="tape-player-header">
        <div className="tape-status-info">
          <span className="step-counter-tag font-mono">
            Step {currentStep} of {totalSteps}
          </span>
          <span className="active-state-tag">
            Current state <strong>{currentStateObj?.name ?? tapeState.state}</strong>
          </span>
          <span className="head-pos-tag font-mono">
            Head at cell <strong>{tapeState.head}</strong>
          </span>
        </div>

        {/* Speed Selector */}
        <div className="speed-selector">
          <Clock size={13} />
          <span>Speed:</span>
          {[0.5, 1, 2, 5, 10].map((spd) => (
            <button
              key={spd}
              type="button"
              className={`speed-btn ${playbackSpeed === spd ? 'active' : ''}`}
              onClick={() => onSetSpeed(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>

      {/* Interactive Tape Strip Display */}
      <div className="tape-viewport-wrapper">
        {/* Horizontal Tape Cells Row */}
        <div className="tape-cells-row">
          {cellPositions.map((pos) => {
            const sym = tapeState.tapeMap[pos] !== undefined ? tapeState.tapeMap[pos] : machine.blank_symbol;
            const isHead = pos === tapeState.head;
            const isBlank = sym === machine.blank_symbol;

            return (
              <div
                key={pos}
                aria-label={`Cell ${pos}: ${isBlank ? 'blank' : sym}${isHead ? ', tape head' : ''}`}
                className={`tape-cell ${isHead ? 'cell-head' : ''} ${isBlank ? 'cell-blank' : 'cell-symbol'}`}
              >
                <div className="cell-pos-index font-mono">{pos}</div>
                <div className="cell-symbol font-mono">{sym}</div>
              </div>
            );
          })}
        </div>

        {/* Scroll Tape Left / Right Controls */}
        <div className="tape-scroll-controls">
          <button
            type="button"
            className="tape-pan-btn"
            onClick={() => setTapeWindowOffset((o) => o - 3)}
            title="Pan tape view left"
          >
            <ChevronLeft size={14} />
          </button>
          {tapeWindowOffset !== 0 && (
            <button
              type="button"
              className="tape-pan-reset"
              onClick={() => setTapeWindowOffset(0)}
              title="Center on tape head"
            >
              Center Head
            </button>
          )}
          <button
            type="button"
            className="tape-pan-btn"
            onClick={() => setTapeWindowOffset((o) => o + 3)}
            title="Pan tape view right"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Informative Execution & Decision Banner */}
      <div className="tape-execution-rule-banner font-mono">
        <div className="execution-banner-main">
          {tapeState.lastEvent ? (
            <div className="rule-event-display">
              <span className="event-label">Last Transition (Step {currentStep}):</span>
              <span className="event-detail">
                δ({tapeState.lastEvent.state_before}, &apos;{tapeState.lastEvent.symbol_before}&apos;) → (
                {tapeState.lastEvent.state_after}, &apos;{tapeState.lastEvent.symbol_after}&apos;,{' '}
                {tapeState.lastEvent.head_after > tapeState.lastEvent.head_before ? 'R' : 'L'})
              </span>
              <span className="event-explanation">
                · Wrote &apos;{tapeState.lastEvent.symbol_after}&apos; at cell {tapeState.lastEvent.head_before}, moved head{' '}
                {tapeState.lastEvent.head_after > tapeState.lastEvent.head_before ? 'Right' : 'Left'} to cell{' '}
                {tapeState.lastEvent.head_after}
              </span>
            </div>
          ) : (
            <div className="rule-event-display text-muted">
              <span className="event-label">Initial State:</span>
              <span>
                Machine ready at start state {machine.start_state}, head at cell 0 scanning &apos;{currentScannedSym}&apos;
              </span>
            </div>
          )}

          {nextEvent ? (
            <div className="rule-next-display text-muted">
              <span className="event-label">Next Action (Step {currentStep + 1}):</span>
              <span>
                Scanned symbol is &apos;{currentScannedSym}&apos; in state {tapeState.state} → evaluating rule δ(
                {nextEvent.state_before}, &apos;{nextEvent.symbol_before}&apos;)
              </span>
            </div>
          ) : (
            <div className="rule-next-display">
              <span className="event-label">Computation Status:</span>
              <span className="terminal-status-text">
                {simulationResult.stop_reason === 'final_state' && 'Halted: Reached accepting final state (Accepted)'}
                {simulationResult.stop_reason === 'missing_transition' &&
                  'Halted: Undefined transition for scanned symbol (Rejected)'}
                {simulationResult.stop_reason === 'step_limit' &&
                  `Execution Budget: Safety step limit (${totalSteps} steps) reached`}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Scrubbing Range Slider */}
      <div className="tape-scrubber-row">
        <input
          type="range"
          aria-label="Playback step"
          min={0}
          max={totalSteps}
          value={currentStep}
          onChange={(e) => onStepChange(Number(e.target.value))}
          className="tape-range-slider"
        />
      </div>

      {/* Playback Button Controls */}
      <div className="tape-controls-bar">
        <button
          type="button"
          className="playback-btn"
          onClick={onReset}
          disabled={currentStep === 0}
          title="Reset to step 0"
        >
          <RotateCcw size={15} />
          <span>Reset</span>
        </button>

        <button
          type="button"
          className="playback-btn"
          onClick={onStepBack}
          disabled={currentStep === 0}
          title="Step backward"
        >
          <SkipBack size={15} />
          <span>Step Back</span>
        </button>

        <button
          type="button"
          className="playback-btn btn-play-primary"
          onClick={onTogglePlay}
          disabled={totalSteps === 0}
          title={isPlaying ? 'Pause simulation' : currentStep >= totalSteps ? 'Replay simulation from start' : 'Play simulation'}
        >
          {isPlaying ? (
            <>
              <Pause size={16} />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play size={16} />
              <span>{currentStep >= totalSteps ? 'Replay' : 'Play'}</span>
            </>
          )}
        </button>

        <button
          type="button"
          className="playback-btn"
          onClick={onStepForward}
          disabled={currentStep >= totalSteps}
          title="Step forward"
        >
          <SkipForward size={15} />
          <span>Step Forward</span>
        </button>

        <button
          type="button"
          className="playback-btn"
          onClick={onJumpToEnd}
          disabled={currentStep >= totalSteps}
          title="Jump to end of trace"
        >
          <FastForward size={15} />
          <span>Jump to End</span>
        </button>
      </div>
    </div>
  );
};
