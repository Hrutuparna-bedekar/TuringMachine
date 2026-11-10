/**
 * Canonical TypeScript data models for Turing Machine simulation.
 * Perfectly mirrors backend schemas and JSON import/export contracts.
 */

export interface State {
  id: string;
  name: string;
}

export interface Transition {
  from_state: string;
  read: string;
  to_state: string;
  write: string;
  move: 'L' | 'R';
}

export interface TuringMachine {
  states: State[];
  input_alphabet: string[];
  tape_alphabet: string[];
  blank_symbol: string;
  start_state: string;
  final_states: string[];
  transitions: Transition[];
}

export interface NodeLayout {
  x: number;
  y: number;
}

export interface MachineExportEnvelope {
  schema_version: 1;
  machine: TuringMachine;
  layout?: Record<string, NodeLayout>;
}

export interface TapeCell {
  position: number;
  symbol: string;
}

export interface InitialConfiguration {
  state: string;
  head: number;
  cells: TapeCell[];
}

export interface TraceEvent {
  step: number;
  transition_index: number;
  state_before: string;
  state_after: string;
  head_before: number;
  head_after: number;
  symbol_before: string;
  symbol_after: string;
}

export type StopReason = 'final_state' | 'missing_transition' | 'step_limit';

export interface SimulationResponse {
  halted_within_limit: boolean;
  stop_reason: StopReason;
  steps: number;
  initial: InitialConfiguration;
  trace: TraceEvent[];
}

export interface SimulationRequest {
  machine: TuringMachine;
  input: string;
  step_limit: number;
}
