import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  TuringMachine,
  NodeLayout,
  SimulationResponse,
  ActiveView,
} from './types';
import { EXAMPLE_MACHINES, ExampleMachineItem } from './utils/examples';
import { simulateMachine, checkHealth } from './api';
import { reconstructTapeAtStep, validateMachineSemantics } from './utils/tape';

import { BootIntro } from './components/BootIntro';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { DashboardPage } from './components/dashboard/DashboardPage';
import { MachineEditor } from './components/workspace/MachineEditor';
import { TransitionTable } from './components/workspace/TransitionTable';
import { MachineConfigurationPanel } from './components/workspace/MachineConfigurationPanel';
import { TapePlayer } from './components/simulation/TapePlayer';
import { ResultsPanel } from './components/simulation/ResultsPanel';
import { PredictorPage } from './components/predictor/PredictorPage';
import { ExamplesPage } from './components/examples/ExamplesPage';
import { ImportExportModal } from './components/modals/ImportExportModal';
import { HelpModal } from './components/help/HelpModal';

export const App: React.FC = () => {
  // 1. Initial State
  const initialExample = EXAMPLE_MACHINES[0];
  const [machine, setMachine] = useState<TuringMachine>(initialExample.data.machine);
  const [layout, setLayout] = useState<Record<string, NodeLayout>>(initialExample.data.layout || {});
  const [activeMachineId, setActiveMachineId] = useState<string>(initialExample.id);
  const [inputText, setInputText] = useState<string>(initialExample.defaultInput);
  const [stepLimit, setStepLimit] = useState<number>(initialExample.defaultStepLimit);

  // 2. Navigation & UI state
  const [activeView, setActiveView] = useState<ActiveView>('dashboard');
  const contentRef = useRef<HTMLElement>(null);
  const [showBootIntro, setShowBootIntro] = useState<boolean>(false);
  const [forceBootIntro, setForceBootIntro] = useState<boolean>(false);
  const [isImportExportOpen, setIsImportExportOpen] = useState<boolean>(false);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

  // 3. Simulation & Trace state
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const simulationRequest = useRef(0);
  const [connectionDraft, setConnectionDraft] = useState<{ source: string; target: string }>();

  // 4. Backend Health state
  const [apiStatus, setApiStatus] = useState<string>('pending');

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 });
  }, [activeView]);

  // Health check on mount and periodic interval
  useEffect(() => {
    let isMounted = true;
    const probeHealth = async () => {
      const res = await checkHealth();
      if (isMounted) setApiStatus(res.status);
    };
    probeHealth();
    const interval = setInterval(probeHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Central playback animation timer
  useEffect(() => {
    if (!isPlaying || !simulationResult) return;

    const totalSteps = simulationResult.trace.length;
    if (currentStep >= totalSteps) {
      setIsPlaying(false);
      return;
    }

    const intervalMs = Math.max(80, Math.round(600 / playbackSpeed));
    const timer = setInterval(() => {
      setCurrentStep((prev) => {
        const next = prev + 1;
        if (next >= totalSteps) {
          setIsPlaying(false);
          return totalSteps;
        }
        return next;
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, simulationResult, playbackSpeed, currentStep]);

  // Invalidate trace when machine, input, or stepLimit changes
  const clearSimulation = useCallback(() => {
    simulationRequest.current += 1;
    setIsSimulating(false);
    setIsPlaying(false);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
  }, []);

  const handleMachineChange = useCallback((updated: TuringMachine) => {
    setMachine(updated);
    clearSimulation();
  }, [clearSimulation]);

  const handleInputChange = useCallback((newInput: string) => {
    setInputText(newInput);
    clearSimulation();
  }, [clearSimulation]);

  const handleStepLimitChange = useCallback((newLimit: number) => {
    setStepLimit(newLimit);
    clearSimulation();
  }, [clearSimulation]);

  // Execute Simulation: Unified deterministic pipeline for both initial run and replay
  const handleRunSimulation = async () => {
    const issue = validateMachineSemantics(machine, inputText).find((item) => item.type === 'error');
    if (issue) {
      setSimulationError(issue.message);
      return;
    }
    const requestId = ++simulationRequest.current;
    setActiveView('simulation');
    setIsSimulating(true);
    setIsPlaying(false);
    setSimulationError(null);
    setSimulationResult(null);
    setCurrentStep(0);
    try {
      const result = await simulateMachine({
        machine,
        input: inputText,
        step_limit: stepLimit,
      });
      if (requestId !== simulationRequest.current) return;
      setSimulationResult(result);
      setCurrentStep(0);
      // Automatically begin animated step-by-step playback so user observes execution
      if (result.trace.length > 0) {
        setIsPlaying(true);
      }
    } catch (err) {
      if (requestId !== simulationRequest.current) return;
      setSimulationError(err instanceof Error ? err.message : String(err));
      setSimulationResult(null);
      setCurrentStep(0);
    } finally {
      if (requestId === simulationRequest.current) setIsSimulating(false);
    }
  };

  // Playback control callbacks
  const handleTogglePlay = useCallback(() => {
    if (!simulationResult) return;
    if (currentStep >= simulationResult.trace.length) {
      setCurrentStep(0);
      setIsPlaying(true);
    } else {
      setIsPlaying((prev) => !prev);
    }
  }, [simulationResult, currentStep]);

  const handleStepChange = useCallback((newStep: number) => {
    setIsPlaying(false);
    setCurrentStep(newStep);
  }, []);

  const handleResetPlayback = useCallback(() => {
    setIsPlaying(false);
    setCurrentStep(0);
  }, []);

  const handleStepBack = useCallback(() => {
    setIsPlaying(false);
    setCurrentStep((prev) => Math.max(0, prev - 1));
  }, []);

  const handleStepForward = useCallback(() => {
    if (!simulationResult) return;
    setIsPlaying(false);
    setCurrentStep((prev) => Math.min(simulationResult.trace.length, prev + 1));
  }, [simulationResult]);

  const handleJumpToEnd = useCallback(() => {
    if (!simulationResult) return;
    setIsPlaying(false);
    setCurrentStep(simulationResult.trace.length);
  }, [simulationResult]);

  // Load Example Machine
  const handleLoadExample = (example: ExampleMachineItem) => {
    setConnectionDraft(undefined);
    setMachine(example.data.machine);
    setLayout(example.data.layout || {});
    setActiveMachineId(example.id);
    setInputText(example.defaultInput);
    setStepLimit(example.defaultStepLimit);
    clearSimulation();
    setActiveView('workspace');
  };

  // Create New Blank Machine Template
  const handleNewMachine = () => {
    setConnectionDraft(undefined);
    const blankMachine: TuringMachine = {
      states: [
        { id: 'q0', name: 'Initial State' },
      ],
      input_alphabet: ['0', '1'],
      tape_alphabet: ['0', '1', '□'],
      blank_symbol: '□',
      start_state: 'q0',
      final_states: [],
      transitions: [],
    };
    const defaultLayout: Record<string, NodeLayout> = {
      q0: { x: 140, y: 180 },
    };
    setMachine(blankMachine);
    setLayout(defaultLayout);
    setActiveMachineId('custom-machine');
    setInputText('101');
    setStepLimit(50);
    clearSimulation();
    setActiveView('workspace');
  };

  // Active state & transition indicators during trace replay
  const replayState = useMemo(() => {
    if (!simulationResult) return { stateId: undefined, transitionIndex: undefined };
    const reconstructed = reconstructTapeAtStep(
      simulationResult.initial,
      simulationResult.trace,
      currentStep,
      machine.blank_symbol
    );
    return {
      stateId: reconstructed.state,
      transitionIndex: reconstructed.lastEvent?.transition_index,
    };
  }, [simulationResult, currentStep, machine.blank_symbol]);

  return (
    <div className="tm-application-root">
      {/* Retro CRT Boot Introduction Sequence */}
      {showBootIntro && (
        <BootIntro
          onComplete={() => {
            setShowBootIntro(false);
            setForceBootIntro(false);
          }}
          forceShow={forceBootIntro}
        />
      )}

      {/* Main App Container Shell */}
      <div className="tm-shell-container">
        {/* Left Dark Sidebar */}
        <Sidebar
          currentView={activeView}
          onSelectView={(view) => {
            if (view === 'help') {
              setIsHelpOpen(true);
            } else {
              setActiveView(view);
            }
          }}
          apiStatus={apiStatus}
          onReplayBoot={() => {
            setForceBootIntro(true);
            setShowBootIntro(true);
          }}
        />

        {/* Right Main Content Area */}
        <div className="tm-main-viewport">
          <TopBar
            currentView={activeView}
            machine={machine}
            onOpenImportExport={() => setIsImportExportOpen(true)}
            onNewMachine={handleNewMachine}
            onRunSimulation={handleRunSimulation}
            isSimulating={isSimulating}
          />

          <main ref={contentRef} className="tm-content-scrollable">
            {/* 1. Dashboard View */}
            {activeView === 'dashboard' && (
              <DashboardPage
                machine={machine}
                onNavigate={setActiveView}
                onLoadExample={handleLoadExample}
                onNewMachine={handleNewMachine}
                apiStatus={apiStatus}
              />
            )}

            {/* 2. Machine Workspace View */}
            {activeView === 'workspace' && (
              <div className="workspace-view-layout">
                <MachineConfigurationPanel
                  machine={machine}
                  inputText={inputText}
                  stepLimit={stepLimit}
                  onChangeMachine={handleMachineChange}
                  onChangeInputText={handleInputChange}
                  onChangeStepLimit={handleStepLimitChange}
                  onLoadExample={() => handleLoadExample(EXAMPLE_MACHINES[0])}
                  onRunSimulation={handleRunSimulation}
                  isSimulating={isSimulating}
                />
                {simulationError && (
                  <ResultsPanel simulationResult={null} machine={machine} loading={false} error={simulationError} />
                )}
                {/* Upper: Interactive Graph Canvas */}
                <div className="workspace-canvas-panel">
                  <MachineEditor
                    machine={machine}
                    layout={layout}
                    onChangeMachine={handleMachineChange}
                    onChangeLayout={setLayout}
                    onConnectStates={setConnectionDraft}
                    activeStateId={replayState.stateId}
                    activeTransitionIndex={replayState.transitionIndex}
                  />
                </div>

                <TransitionTable
                  machine={machine}
                  onChange={handleMachineChange}
                  connectionDraft={connectionDraft}
                  activeTransitionIndex={replayState.transitionIndex}
                />
              </div>
            )}

            {/* 3. Dedicated Simulation / Replay View */}
            {activeView === 'simulation' && (
              <div className="dedicated-simulation-view">
                <div className="simulation-view-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => setActiveView('workspace')}>
                    Back to Machine Editor
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={() => setActiveView('predictor')}>
                    Open ML Predictor
                  </button>
                </div>
                <ResultsPanel
                  simulationResult={simulationResult}
                  machine={machine}
                  loading={isSimulating}
                  error={simulationError}
                />
                <div className="simulation-panels">
                  <div className="simulation-graph-snapshot">
                    <MachineEditor
                      machine={machine}
                      layout={layout}
                      onChangeMachine={handleMachineChange}
                      onChangeLayout={setLayout}
                      activeStateId={replayState.stateId}
                      activeTransitionIndex={replayState.transitionIndex}
                    />
                  </div>
                  <TapePlayer
                    simulationResult={simulationResult}
                    machine={machine}
                    currentStep={currentStep}
                    isPlaying={isPlaying}
                    playbackSpeed={playbackSpeed}
                    onStepChange={handleStepChange}
                    onTogglePlay={handleTogglePlay}
                    onSetSpeed={setPlaybackSpeed}
                    onReset={handleResetPlayback}
                    onStepBack={handleStepBack}
                    onStepForward={handleStepForward}
                    onJumpToEnd={handleJumpToEnd}
                  />
                </div>
              </div>
            )}

            {/* 4. Predictor View (Phase 2 ML Bounded Halting) */}
            {activeView === 'predictor' && (
              <PredictorPage key={JSON.stringify([machine, inputText])} machine={machine} input={inputText} />
            )}

            {/* 5. Examples Library View */}
            {activeView === 'examples' && (
              <ExamplesPage
                onLoadExample={handleLoadExample}
                currentMachineId={activeMachineId}
              />
            )}
          </main>
        </div>
      </div>

      {/* JSON Import / Export Modal */}
      <ImportExportModal
        machine={machine}
        layout={layout}
        isOpen={isImportExportOpen}
        onClose={() => setIsImportExportOpen(false)}
        onImport={(importedMachine, importedLayout) => {
          setConnectionDraft(undefined);
          handleMachineChange(importedMachine);
          setLayout(importedLayout);
          setActiveMachineId('imported-machine');
        }}
      />

      {/* TOC Help & Reference Modal */}
      <HelpModal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  );
};
