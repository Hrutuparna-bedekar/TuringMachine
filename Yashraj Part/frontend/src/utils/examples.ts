import { MachineExportEnvelope } from '../types';

export interface ExampleMachineItem {
  id: string;
  title: string;
  tagline: string;
  description: string;
  accentColor: 'yellow' | 'pink' | 'sage' | 'blue';
  defaultInput: string;
  defaultStepLimit: number;
  data: MachineExportEnvelope;
}

export const EXAMPLE_MACHINES: ExampleMachineItem[] = [
  {
    id: 'scan-to-blank',
    title: 'Scan to Blank',
    tagline: 'Linear Search & Halting',
    description: 'Scans rightward over binary 0s and 1s until encountering the designated blank symbol □, where it halts gracefully in accepting state q_halt.',
    accentColor: 'blue',
    defaultInput: '101',
    defaultStepLimit: 50,
    data: {
      schema_version: 1,
      machine: {
        states: [
          { id: 'q_scan', name: 'Scanning Tape' },
          { id: 'q_halt', name: 'Halt on Blank' },
        ],
        input_alphabet: ['0', '1'],
        tape_alphabet: ['0', '1', '□'],
        blank_symbol: '□',
        start_state: 'q_scan',
        final_states: ['q_halt'],
        transitions: [
          { from_state: 'q_scan', read: '0', to_state: 'q_scan', write: '0', move: 'R' },
          { from_state: 'q_scan', read: '1', to_state: 'q_scan', write: '1', move: 'R' },
          { from_state: 'q_scan', read: '□', to_state: 'q_halt', write: '□', move: 'R' },
        ],
      },
      layout: {
        q_scan: { x: 140, y: 180 },
        q_halt: { x: 420, y: 180 },
      },
    },
  },
  {
    id: 'replace-symbol',
    title: 'Replace Symbol (0 → 1)',
    tagline: 'Tape In-Place Mutation',
    description: 'Traverses the tape replacing every binary 0 with 1 while keeping 1s intact, demonstrating in-place tape modification before halting on blank.',
    accentColor: 'sage',
    defaultInput: '01001',
    defaultStepLimit: 50,
    data: {
      schema_version: 1,
      machine: {
        states: [
          { id: 'q_replace', name: 'Replacing Zero with One' },
          { id: 'q_done', name: 'Replacement Complete' },
        ],
        input_alphabet: ['0', '1'],
        tape_alphabet: ['0', '1', '□'],
        blank_symbol: '□',
        start_state: 'q_replace',
        final_states: ['q_done'],
        transitions: [
          { from_state: 'q_replace', read: '0', to_state: 'q_replace', write: '1', move: 'R' },
          { from_state: 'q_replace', read: '1', to_state: 'q_replace', write: '1', move: 'R' },
          { from_state: 'q_replace', read: '□', to_state: 'q_done', write: '□', move: 'R' },
        ],
      },
      layout: {
        q_replace: { x: 140, y: 180 },
        q_done: { x: 420, y: 180 },
      },
    },
  },
  {
    id: 'loop-ping-pong',
    title: 'Ping-Pong Looping Machine',
    tagline: 'Infinite State Cycle',
    description: 'Alternates between cell 0 and cell 1, toggling symbols back and forth perpetually without halting. Designed to verify step-limit termination handling.',
    accentColor: 'pink',
    defaultInput: '0',
    defaultStepLimit: 100,
    data: {
      schema_version: 1,
      machine: {
        states: [
          { id: 'q_toggle_to_one', name: 'Toggle Cell 0 to 1' },
          { id: 'q_return_one', name: 'Step Back to Cell 0' },
          { id: 'q_toggle_to_zero', name: 'Toggle Cell 0 to 0' },
          { id: 'q_return_zero', name: 'Step Back to Cell 0' },
        ],
        input_alphabet: ['0', '1'],
        tape_alphabet: ['0', '1', '□'],
        blank_symbol: '□',
        start_state: 'q_toggle_to_one',
        final_states: [],
        transitions: [
          { from_state: 'q_toggle_to_one', read: '0', to_state: 'q_return_one', write: '1', move: 'R' },
          { from_state: 'q_return_one', read: '□', to_state: 'q_toggle_to_zero', write: '□', move: 'L' },
          { from_state: 'q_toggle_to_zero', read: '1', to_state: 'q_return_zero', write: '0', move: 'R' },
          { from_state: 'q_return_zero', read: '□', to_state: 'q_toggle_to_one', write: '□', move: 'L' },
        ],
      },
      layout: {
        q_toggle_to_one: { x: 120, y: 120 },
        q_return_one: { x: 400, y: 120 },
        q_toggle_to_zero: { x: 400, y: 300 },
        q_return_zero: { x: 120, y: 300 },
      },
    },
  },
  {
    id: 'binary-incrementer',
    title: 'Binary Incrementer (+1)',
    tagline: 'Arithmetic Computation',
    description: 'Travels to the least significant bit of a binary number and adds 1, correctly propagating carries leftward and rewriting bits.',
    accentColor: 'yellow',
    defaultInput: '1011',
    defaultStepLimit: 80,
    data: {
      schema_version: 1,
      machine: {
        states: [
          { id: 'q_scan_end', name: 'Find End of Word' },
          { id: 'q_carry', name: 'Add 1 & Propagate Carry' },
          { id: 'q_halt', name: 'Arithmetic Done' },
        ],
        input_alphabet: ['0', '1'],
        tape_alphabet: ['0', '1', '□'],
        blank_symbol: '□',
        start_state: 'q_scan_end',
        final_states: ['q_halt'],
        transitions: [
          { from_state: 'q_scan_end', read: '0', to_state: 'q_scan_end', write: '0', move: 'R' },
          { from_state: 'q_scan_end', read: '1', to_state: 'q_scan_end', write: '1', move: 'R' },
          { from_state: 'q_scan_end', read: '□', to_state: 'q_carry', write: '□', move: 'L' },
          { from_state: 'q_carry', read: '1', to_state: 'q_carry', write: '0', move: 'L' },
          { from_state: 'q_carry', read: '0', to_state: 'q_halt', write: '1', move: 'L' },
          { from_state: 'q_carry', read: '□', to_state: 'q_halt', write: '1', move: 'L' },
        ],
      },
      layout: {
        q_scan_end: { x: 100, y: 180 },
        q_carry: { x: 340, y: 180 },
        q_halt: { x: 580, y: 180 },
      },
    },
  },
];

