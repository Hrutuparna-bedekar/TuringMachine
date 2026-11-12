import { MachineExportEnvelope, Transition } from '../types';
import { generateAutoLayout } from './tape';

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

type Rule = [from: string, read: string, write: string, move: 'L' | 'R', next: string];

function exampleMachine(
  names: Record<string, string>,
  inputAlphabet: string[],
  extraSymbols: string[],
  finalState: string,
  rules: Rule[],
): MachineExportEnvelope {
  const states = Object.entries(names).map(([id, name]) => ({ id, name }));
  const startState = states[0].id;
  const transitions: Transition[] = rules.map(([from_state, read, write, move, to_state]) => ({
    from_state, read, write, move, to_state,
  }));
  const layout = states.length <= 8
    ? generateAutoLayout(states, transitions, startState)
    : Object.fromEntries(states.map(({ id }, index) => [
        id, { x: 100 + (index % 4) * 280, y: 100 + Math.floor(index / 4) * 180 },
      ]));
  return {
    schema_version: 1,
    machine: {
      states,
      input_alphabet: inputAlphabet,
      tape_alphabet: [...inputAlphabet, ...extraSymbols, '□'],
      blank_symbol: '□',
      start_state: startState,
      final_states: [finalState],
      transitions,
    },
    layout,
  };
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
  {
    id: 'contains-101',
    title: 'Find 101 anywhere',
    tagline: 'Substring detection',
    description: 'Reaches Found 101 if three consecutive symbols are 101. Try 001011 for a match or 1001 for no match.',
    accentColor: 'blue',
    defaultInput: '001011',
    defaultStepLimit: 50,
    data: exampleMachine(
      { scan: 'Find a 1', seen1: 'Saw 1', seen10: 'Saw 10', found: 'Found 101' },
      ['0', '1'], [], 'found', [
        ['scan', '0', '0', 'R', 'scan'],
        ['scan', '1', '1', 'R', 'seen1'],
        ['seen1', '0', '0', 'R', 'seen10'],
        ['seen1', '1', '1', 'R', 'seen1'],
        ['seen10', '0', '0', 'R', 'scan'],
        ['seen10', '1', '1', 'R', 'found'],
      ],
    ),
  },
  {
    id: 'ones-then-zeros',
    title: 'Check 1ᵐ0ⁿ',
    tagline: 'Language recognition',
    description: 'Accepts strings with all the ones before the zeros. Either group may be empty. Try 11100 or 101.',
    accentColor: 'sage',
    defaultInput: '11100',
    defaultStepLimit: 50,
    data: exampleMachine(
      { ones: 'Read ones', zeros: 'Read zeros', accepted: 'Pattern accepted' },
      ['0', '1'], [], 'accepted', [
        ['ones', '1', '1', 'R', 'ones'],
        ['ones', '0', '0', 'R', 'zeros'],
        ['ones', '□', '□', 'R', 'accepted'],
        ['zeros', '0', '0', 'R', 'zeros'],
        ['zeros', '□', '□', 'R', 'accepted'],
      ],
    ),
  },
  {
    id: 'equal-ones-and-zeros',
    title: 'Check 1ᵐ0ᵐ',
    tagline: 'Equal counts',
    description: 'Crosses off one 1 and one 0 per pass. It accepts 1100 and rejects 11100 and 1010. The empty input is accepted for m = 0.',
    accentColor: 'blue',
    defaultInput: '1100',
    defaultStepLimit: 1000,
    data: exampleMachine(
      {
        take: 'Mark a 1', seek: 'Find a matching 0', zeros: 'Skip paired zeros',
        rewind: 'Return to the start', verify: 'Check for leftovers', done: 'Counts match',
      },
      ['0', '1'], ['X', 'Y'], 'done', [
        ['take', 'X', 'X', 'R', 'take'],
        ['take', '1', 'X', 'R', 'seek'],
        ['take', 'Y', 'Y', 'R', 'verify'],
        ['take', '□', '□', 'R', 'done'],
        ['seek', '1', '1', 'R', 'seek'],
        ['seek', 'Y', 'Y', 'R', 'zeros'],
        ['seek', '0', 'Y', 'L', 'rewind'],
        ['zeros', 'Y', 'Y', 'R', 'zeros'],
        ['zeros', '0', 'Y', 'L', 'rewind'],
        ['rewind', '1', '1', 'L', 'rewind'],
        ['rewind', 'X', 'X', 'L', 'rewind'],
        ['rewind', 'Y', 'Y', 'L', 'rewind'],
        ['rewind', '□', '□', 'R', 'take'],
        ['verify', 'Y', 'Y', 'R', 'verify'],
        ['verify', '□', '□', 'R', 'done'],
      ],
    ),
  },
  {
    id: 'unary-addition',
    title: 'Unary addition',
    tagline: 'Compute 4 + 5',
    description: 'Each 1 counts as one. Run 1111+11111 to leave nine ones on the tape. Use an empty group for zero.',
    accentColor: 'yellow',
    defaultInput: '1111+11111',
    defaultStepLimit: 1000,
    data: exampleMachine(
      { left: 'Find plus', right: 'Find end', trim: 'Remove extra 1', rewind: 'Find result start', done: 'Sum ready' },
      ['1', '+'], [], 'done', [
        ['left', '1', '1', 'R', 'left'],
        ['left', '+', '1', 'R', 'right'],
        ['right', '1', '1', 'R', 'right'],
        ['right', '□', '□', 'L', 'trim'],
        ['trim', '1', '□', 'L', 'rewind'],
        ['rewind', '1', '1', 'L', 'rewind'],
        ['rewind', '□', '□', 'R', 'done'],
      ],
    ),
  },
  {
    id: 'unary-subtraction',
    title: 'Signed unary subtraction',
    tagline: 'Compute 4 − 5',
    description: 'Crosses off one 1 from each side. Run 1111-11111 to leave -1. An empty result represents zero.',
    accentColor: 'pink',
    defaultInput: '1111-11111',
    defaultStepLimit: 1000,
    data: exampleMachine(
      {
        left: 'Find minus', check: 'Check right input', seek: 'Return to minus',
        take: 'Cross off left 1', separator: 'Cross to right', pair: 'Cross off right 1',
        clearLeft: 'Erase left marks', clearRight: 'Erase right marks', sign: 'Write minus',
        clearPaired: 'Clear paired right', undo: 'Clear left marks', restore: 'Restore unpaired 1',
        rewind: 'Find result start', done: 'Difference ready',
      },
      ['1', '-'], ['X', 'Y'], 'done', [
        ['left', '1', '1', 'R', 'left'],
        ['left', '-', '-', 'R', 'check'],
        ['check', '1', '1', 'R', 'check'],
        ['check', '□', '□', 'L', 'seek'],
        ['seek', '1', '1', 'L', 'seek'],
        ['seek', 'Y', 'Y', 'L', 'seek'],
        ['seek', '-', '-', 'L', 'take'],
        ['take', 'X', 'X', 'L', 'take'],
        ['take', '1', 'X', 'R', 'separator'],
        ['separator', 'X', 'X', 'R', 'separator'],
        ['separator', '-', '-', 'R', 'pair'],
        ['pair', 'Y', 'Y', 'R', 'pair'],
        ['pair', '1', 'Y', 'L', 'seek'],

        // The left group is exhausted. Erase the crossed-off pairs.
        ['take', '□', '□', 'R', 'clearLeft'],
        ['clearLeft', 'X', '□', 'R', 'clearLeft'],
        ['clearLeft', '-', '□', 'R', 'clearRight'],
        ['clearRight', 'Y', '□', 'R', 'clearRight'],
        ['clearRight', '1', '1', 'L', 'sign'],
        ['clearRight', '□', '□', 'L', 'done'],
        ['sign', '□', '-', 'R', 'done'],

        // The right group is exhausted. Undo the last unpaired left mark.
        ['pair', '□', '□', 'L', 'clearPaired'],
        ['clearPaired', 'Y', '□', 'L', 'clearPaired'],
        ['clearPaired', '-', '□', 'L', 'undo'],
        ['undo', 'X', '□', 'L', 'undo'],
        ['undo', '1', '1', 'R', 'restore'],
        ['undo', '□', '□', 'R', 'restore'],
        ['restore', '□', '1', 'L', 'rewind'],
        ['rewind', '1', '1', 'L', 'rewind'],
        ['rewind', '□', '□', 'R', 'done'],
      ],
    ),
  },
];
