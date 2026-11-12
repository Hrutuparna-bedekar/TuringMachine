import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TuringMachine,
  NodeLayout,
  SimulationResponse,
  ActiveView,
} from './types';
import { EXAMPLE_MACHINES, ExampleMachineItem } from './utils/examples';
import { simulateMachine, checkHealth } from './api';
import { reconstructTapeAtStep } from './utils/tape';

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
  const [showBootIntro, setShowBootIntro] = useState<boolean>(true);
  const [forceBootIntro, setForceBootIntro] = useState<boolean>(false);
  const [isImportExportOpen, setIsImportExportOpen] = useState<boolean>(false);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);

  // 3. Simulation & Trace state
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  // 4. Backend Health state
  const [apiStatus, setApiStatus] = useState<string>('pending');

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

  // Invalidate trace when machine, input, or stepLimit changes
  const handleMachineChange = useCallback((updated: TuringMachine) => {
    setMachine(updated);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
  }, []);

  const handleInputChange = useCallback((newInput: string) => {
    setInputText(newInput);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
  }, []);

  const handleStepLimitChange = useCallback((newLimit: number) => {
    setStepLimit(newLimit);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
  }, []);

  // Execute Simulation
  const handleRunSimulation = async () => {
    setIsSimulating(true);
    setSimulationError(null);
    try {
      const result = await simulateMachine({
        machine,
        input: inputText,
        step_limit: stepLimit,
      });
      setSimulationResult(result);
      setCurrentStep(result.trace.length); // Start at final position so outcome is clear
    } catch (err) {
      setSimulationError(err instanceof Error ? err.message : String(err));
      setSimulationResult(null);
    } finally {
      setIsSimulating(false);
    }
  };

  // Load Example Machine
  const handleLoadExample = (example: ExampleMachineItem) => {
    setMachine(example.data.machine);
    setLayout(example.data.layout || {});
    setActiveMachineId(example.id);
    setInputText(example.defaultInput);
    setStepLimit(example.defaultStepLimit);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
    setActiveView('workspace');
  };

  // Create New Blank Machine Template
  const handleNewMachine = () => {
    const blankMachine: TuringMachine = {
      states: [
        { id: 'q0', name: 'Initial State' },
        { id: 'q_halt', name: 'Halt State' },
      ],
      input_alphabet: ['0', '1'],
      tape_alphabet: ['0', '1', '□'],
      blank_symbol: '□',
      start_state: 'q0',
      final_states: ['q_halt'],
      transitions: [
        { from_state: 'q0', read: '0', to_state: 'q0', write: '0', move: 'R' },
        { from_state: 'q0', read: '1', to_state: 'q0', write: '1', move: 'R' },
        { from_state: 'q0', read: '□', to_state: 'q_halt', write: '□', move: 'R' },
      ],
    };
    const defaultLayout: Record<string, NodeLayout> = {
      q0: { x: 140, y: 180 },
      q_halt: { x: 420, y: 180 },
    };
    setMachine(blankMachine);
    setLayout(defaultLayout);
    setActiveMachineId('custom-machine');
    setInputText('101');
    setStepLimit(50);
    setSimulationResult(null);
    setCurrentStep(0);
    setSimulationError(null);
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

          <main className="tm-content-scrollable">
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
                {/* Upper: Interactive Graph Canvas */}
                <div className="workspace-canvas-panel">
                  <MachineEditor
                    machine={machine}
                    layout={layout}
                    onChangeMachine={handleMachineChange}
                    onChangeLayout={setLayout}
                    activeStateId={replayState.stateId}
                    activeTransitionIndex={replayState.transitionIndex}
                  />
                </div>

                {/* Middle: Configuration & Rules Matrix */}
                <div className="workspace-rules-config-grid">
                  <MachineConfigurationPanel
                    machine={machine}
                    inputText={inputText}
                    stepLimit={stepLimit}
                    onChangeMachine={handleMachineChange}
                    onChangeInputText={handleInputChange}
                    onChangeStepLimit={handleStepLimitChange}
                  />
                  <TransitionTable
                    machine={machine}
                    onChange={handleMachineChange}
                    activeTransitionIndex={replayState.transitionIndex}
                  />
                </div>

                {/* Bottom: Tape Replay & Execution Diagnostics */}
                <div className="workspace-simulation-grid">
                  <TapePlayer
                    simulationResult={simulationResult}
                    machine={machine}
                    currentStep={currentStep}
                    onStepChange={setCurrentStep}
                  />
                  <ResultsPanel
                    simulationResult={simulationResult}
                    machine={machine}
                    loading={isSimulating}
                    error={simulationError}
                  />
                </div>
              </div>
            )}

            {/* 3. Dedicated Simulation / Replay View */}
            {activeView === 'simulation' && (
              <div className="dedicated-simulation-view">
                <div className="simulation-overview-banner">
                  <div className="overview-title-group">
                    <h2 className="section-title">Execution Chronicle & Virtual Tape</h2>
                    <p className="section-subtitle">
                      Inspect tape dynamics at any execution transition. Step backward restores tape symbols, head position, and state with 100% mathematical fidelity.
                    </p>
                  </div>
                </div>

                <div className="simulation-panels-grid">
                  <TapePlayer
                    simulationResult={simulationResult}
                    machine={machine}
                    currentStep={currentStep}
                    onStepChange={setCurrentStep}
                  />
                  <ResultsPanel
                    simulationResult={simulationResult}
                    machine={machine}
                    loading={isSimulating}
                    error={simulationError}
                  />
                </div>

                <div className="simulation-graph-snapshot">
                  <h3 className="section-title">Active Transition State Diagram</h3>
                  <MachineEditor
                    machine={machine}
                    layout={layout}
                    onChangeMachine={handleMachineChange}
                    onChangeLayout={setLayout}
                    activeStateId={replayState.stateId}
                    activeTransitionIndex={replayState.transitionIndex}
                  />
                </div>
              </div>
            )}

            {/* 4. Predictor View (Phase 2 ML Bounded Halting) */}
            {activeView === 'predictor' && (
              <PredictorPage machine={machine} input={inputText} />
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
