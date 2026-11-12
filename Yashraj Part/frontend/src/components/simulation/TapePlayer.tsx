import React, { useState, useEffect, useRef } from 'react';
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

interface TapePlayerProps {
  simulationResult: SimulationResponse | null;
  machine: TuringMachine;
  currentStep: number;
  onStepChange: (step: number) => void;
}

export const TapePlayer: React.FC<TapePlayerProps> = ({
  simulationResult,
  machine,
  currentStep,
  onStepChange,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1); // 1 step per sec, 2x, etc.
  const [tapeWindowOffset, setTapeWindowOffset] = useState<number>(0);
  const tapeContainerRef = useRef<HTMLDivElement>(null);

  const totalSteps = simulationResult?.trace?.length || 0;

  // Auto-play interval effect
  useEffect(() => {
    if (!isPlaying || !simulationResult) return;

    const intervalMs = Math.max(100, Math.round(750 / playbackSpeed));
    const interval = setInterval(() => {
      if (currentStep >= totalSteps) {
        setIsPlaying(false);
      } else {
        onStepChange(currentStep + 1);
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [isPlaying, simulationResult, playbackSpeed, totalSteps, currentStep, onStepChange]);

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
  const baseRange = 8; // cells on each side
  const startPos = tapeState.head - baseRange + tapeWindowOffset;
  const endPos = tapeState.head + baseRange + tapeWindowOffset;
  const cellPositions: number[] = [];
  for (let p = startPos; p <= endPos; p++) {
    cellPositions.push(p);
  }

  const handleReset = () => {
    setIsPlaying(false);
    onStepChange(0);
  };

  const handleStepBack = () => {
    setIsPlaying(false);
    onStepChange(Math.max(0, currentStep - 1));
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    onStepChange(Math.min(totalSteps, currentStep + 1));
  };

  const handleJumpToEnd = () => {
    setIsPlaying(false);
    onStepChange(totalSteps);
  };

  const togglePlay = () => {
    if (currentStep >= totalSteps) {
      onStepChange(0);
      setIsPlaying(true);
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const currentStateObj = machine.states.find((s) => s.id === tapeState.state);
  const isFinalStep = currentStep === totalSteps;

  return (
    <div className="tape-player-container">
      {/* Player Header & Current Step Status */}
      <div className="tape-player-header">
        <div className="tape-status-info">
          <span className="step-counter-tag font-mono">
            Step {currentStep} of {totalSteps}
          </span>
          <span className="active-state-tag">
            State: <strong className="font-mono">{tapeState.state}</strong>
            {currentStateObj ? ` (${currentStateObj.name})` : ''}
          </span>
          <span className="head-pos-tag font-mono">
            Head Pos: <strong>{tapeState.head}</strong>
          </span>
        </div>

        {/* Speed Selector */}
        <div className="speed-selector">
          <Clock size={13} />
          <span>Speed:</span>
          {[0.5, 1, 2, 5].map((spd) => (
            <button
              key={spd}
              type="button"
              className={`speed-btn ${playbackSpeed === spd ? 'active' : ''}`}
              onClick={() => setPlaybackSpeed(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>
      </div>

      {/* Interactive Tape Strip Display */}
      <div className="tape-viewport-wrapper" ref={tapeContainerRef}>
        {/* Head Position Pointer Marker */}
        <div className="tape-head-marker">
          <div className="head-pointer-indicator">
            <span className="pointer-arrow">▼</span>
            <span className="pointer-label font-mono">HEAD [Pos {tapeState.head}]</span>
          </div>
        </div>

        {/* Horizontal Tape Cells Row */}
        <div className="tape-cells-row">
          {cellPositions.map((pos) => {
            const sym = tapeState.tapeMap[pos] !== undefined ? tapeState.tapeMap[pos] : machine.blank_symbol;
            const isHead = pos === tapeState.head;
            const isBlank = sym === machine.blank_symbol;

            return (
              <div
                key={pos}
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

      {/* Last Executed Rule Banner */}
      <div className="tape-execution-rule-banner font-mono">
        {tapeState.lastEvent ? (
          <div className="rule-event-display">
            <span className="event-label">Last Rule Executed:</span>
            <span className="event-detail">
              δ({tapeState.lastEvent.state_before}, '{tapeState.lastEvent.symbol_before}') → (
              {tapeState.lastEvent.state_after}, '{tapeState.lastEvent.symbol_after}',{' '}
              {tapeState.lastEvent.head_after > tapeState.lastEvent.head_before ? 'R' : 'L'})
            </span>
          </div>
        ) : (
          <div className="rule-event-display text-muted">
            <span>Configuration snapshot before execution (Step 0)</span>
          </div>
        )}

        {isFinalStep && (
          <div className="terminal-stop-tag">
            <span>Terminal: </span>
            <strong>{simulationResult.stop_reason}</strong>
          </div>
        )}
      </div>

      {/* Scrubbing Range Slider */}
      <div className="tape-scrubber-row">
        <input
          type="range"
          min={0}
          max={totalSteps}
          value={currentStep}
          onChange={(e) => {
            setIsPlaying(false);
            onStepChange(Number(e.target.value));
          }}
          className="tape-range-slider"
        />
      </div>

      {/* Playback Button Controls */}
      <div className="tape-controls-bar">
        <button
          type="button"
          className="playback-btn"
          onClick={handleReset}
          disabled={currentStep === 0}
          title="Reset to step 0"
        >
          <RotateCcw size={15} />
          <span>Reset</span>
        </button>

        <button
          type="button"
          className="playback-btn"
          onClick={handleStepBack}
          disabled={currentStep === 0}
          title="Step backward"
        >
          <SkipBack size={15} />
          <span>Step Back</span>
        </button>

        <button
          type="button"
          className="playback-btn btn-play-primary"
          onClick={togglePlay}
          title={isPlaying ? 'Pause replay' : 'Play replay'}
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
          onClick={handleStepForward}
          disabled={currentStep >= totalSteps}
          title="Step forward"
        >
          <SkipForward size={15} />
          <span>Step Forward</span>
        </button>

        <button
          type="button"
          className="playback-btn"
          onClick={handleJumpToEnd}
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

