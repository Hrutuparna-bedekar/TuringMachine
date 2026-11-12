import React, { useEffect, useState } from 'react';
import { Terminal } from 'lucide-react';

interface BootIntroProps {
  onComplete: () => void;
  forceShow?: boolean;
}

export const BootIntro: React.FC<BootIntroProps> = ({ onComplete, forceShow = false }) => {
  const [stage, setStage] = useState<number>(0);
  const [progress, setProgress] = useState<number>(10);
  const [flicker, setFlicker] = useState<boolean>(true);

  useEffect(() => {
    // Check if user prefers reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion && !forceShow) {
      onComplete();
      return;
    }

    // Check session storage
    if (!forceShow && sessionStorage.getItem('tm_boot_seen') === 'true') {
      onComplete();
      return;
    }

    // Sequence stages
    const timerFlicker = setTimeout(() => setFlicker(false), 200);

    const timer1 = setTimeout(() => {
      setStage(1);
      setProgress(35);
    }, 400);

    const timer2 = setTimeout(() => {
      setStage(2);
      setProgress(70);
    }, 1000);

    const timer3 = setTimeout(() => {
      setStage(3);
      setProgress(100);
    }, 1800);

    const timerComplete = setTimeout(() => {
      sessionStorage.setItem('tm_boot_seen', 'true');
      onComplete();
    }, 2500);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
        sessionStorage.setItem('tm_boot_seen', 'true');
        onComplete();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timerFlicker);
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timerComplete);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [forceShow, onComplete]);

  const handleSkip = () => {
    sessionStorage.setItem('tm_boot_seen', 'true');
    onComplete();
  };

  return (
    <div className={`boot-overlay ${flicker ? 'boot-flicker' : ''}`}>
      {/* CRT Scanline and Vignette Layer */}
      <div className="crt-scanlines" />
      <div className="crt-vignette" />

      {/* Retro Desktop / Monitor Window */}
      <div className="retro-monitor-window">
        {/* Retro Window Header */}
        <div className="retro-window-header">
          <div className="retro-window-dots">
            <span className="dot dot-close" />
            <span className="dot dot-min" />
            <span className="dot dot-max" />
          </div>
          <div className="retro-window-title">
            <Terminal size={14} className="retro-icon" />
            <span>ALAN_OS // TM_BOOT.EXE v1.0.4</span>
          </div>
          <button className="retro-skip-btn" onClick={handleSkip} title="Skip boot sequence">
            SKIP [ESC]
          </button>
        </div>

        {/* Retro CRT Display Screen */}
        <div className="retro-screen-content">
          <div className="boot-terminal-log">
            <p className="log-line text-dim">BIOS DATE 11/12/26 23:30:00 // VIRTUAL CPU 64-BIT</p>
            <p className="log-line text-dim">VERIFYING MEMORY PARITY ............ [ OK ]</p>
            <p className="log-line text-dim">ALLOCATING BIDIRECTIONAL TAPE BUFFER [ OK ]</p>
            {stage >= 1 && (
              <p className="log-line text-teal">
                TRANSITION MATRIX: DETERMINISTIC MONTE CARLO ENGINE READY.
              </p>
            )}
          </div>

          {/* Prominent "TURING MACHINE" Branding */}
          <div className={`boot-brand-banner ${stage >= 1 ? 'visible' : ''}`}>
            <div className="banner-sub">THEORY OF COMPUTATION LABORATORY</div>
            <h1 className="boot-title">TURING MACHINE</h1>
            <div className="banner-tagline">
              <span>EXACT SIMULATION</span>
              <span className="banner-separator">•</span>
              <span>BOUNDED HALTING PREDICTOR</span>
            </div>
          </div>

          {/* Progress Bar & Status */}
          <div className="boot-progress-container">
            <div className="boot-progress-track">
              <div
                className="boot-progress-fill"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="boot-status-text">
              {stage === 0 && 'INITIALIZING SYSTEM REGISTERS...'}
              {stage === 1 && 'CONFIGURING TAPE ALPHABET (Σ ⊂ Γ)...'}
              {stage === 2 && 'SYNCING REPLAY CHRONICLE TRACE...'}
              {stage === 3 && 'SYSTEM READY. LAUNCHING WORKSPACE...'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

