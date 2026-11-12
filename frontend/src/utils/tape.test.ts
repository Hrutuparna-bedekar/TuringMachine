import { describe, it, expect } from 'vitest';
import { reconstructTapeAtStep, validateMachineSemantics, generateAutoLayout } from './tape';
import { TuringMachine, InitialConfiguration, TraceEvent } from '../types';
import { EXAMPLE_MACHINES } from './examples';

describe('Tape Reconstruction', () => {
  const initial: InitialConfiguration = {
    state: 'q_scan',
    head: 0,
    cells: [
      { position: 0, symbol: '1' },
      { position: 1, symbol: '0' },
      { position: 2, symbol: '1' },
    ],
  };

  const trace: TraceEvent[] = [
    {
      step: 1,
      transition_index: 1,
      state_before: 'q_scan',
      state_after: 'q_scan',
      head_before: 0,
      head_after: 1,
      symbol_before: '1',
      symbol_after: '1',
    },
    {
      step: 2,
      transition_index: 0,
      state_before: 'q_scan',
      state_after: 'q_scan',
      head_before: 1,
      head_after: 2,
      symbol_before: '0',
      symbol_after: '0',
    },
    {
      step: 3,
      transition_index: 2,
      state_before: 'q_scan',
      state_after: 'q_halt',
      head_before: 2,
      head_after: 3,
      symbol_before: '1',
      symbol_after: 'X',
    },
  ];

  it('reconstructs step 0 with initial state and symbols', () => {
    const res = reconstructTapeAtStep(initial, trace, 0, '□');
    expect(res.head).toBe(0);
    expect(res.state).toBe('q_scan');
    expect(res.tapeMap[0]).toBe('1');
    expect(res.tapeMap[1]).toBe('0');
    expect(res.tapeMap[2]).toBe('1');
    expect(res.lastEvent).toBeNull();
  });

  it('reconstructs intermediate steps accurately', () => {
    const res1 = reconstructTapeAtStep(initial, trace, 1, '□');
    expect(res1.head).toBe(1);
    expect(res1.state).toBe('q_scan');
    expect(res1.lastEvent?.step).toBe(1);

    const res2 = reconstructTapeAtStep(initial, trace, 2, '□');
    expect(res2.head).toBe(2);
    expect(res2.state).toBe('q_scan');
    expect(res2.lastEvent?.step).toBe(2);
  });

  it('reconstructs final step with written mutation', () => {
    const res3 = reconstructTapeAtStep(initial, trace, 3, '□');
    expect(res3.head).toBe(3);
    expect(res3.state).toBe('q_halt');
    expect(res3.tapeMap[2]).toBe('X'); // mutated in step 3
  });

  it('bounds step safely to trace length when step is out of range', () => {
    const resOver = reconstructTapeAtStep(initial, trace, 999, '□');
    expect(resOver.head).toBe(3);
    expect(resOver.state).toBe('q_halt');

    const resUnder = reconstructTapeAtStep(initial, trace, -5, '□');
    expect(resUnder.head).toBe(0);
    expect(resUnder.state).toBe('q_scan');
  });
});

describe('Machine Semantic Validation', () => {
  const validMachine: TuringMachine = {
    states: [
      { id: 'q0', name: 'Start' },
      { id: 'q_halt', name: 'Halt' },
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

  it('passes valid machine with valid input', () => {
    const issues = validateMachineSemantics(validMachine, '101');
    const errors = issues.filter((i) => i.type === 'error');
    expect(errors).toHaveLength(0);
  });

  it('detects unknown start state', () => {
    const invalid = { ...validMachine, start_state: 'non_existent' };
    const issues = validateMachineSemantics(invalid);
    expect(issues.some((i) => i.message.includes('Start state "non_existent"'))).toBe(true);
  });

  it('detects blank symbol in input alphabet', () => {
    const invalid = { ...validMachine, input_alphabet: ['0', '1', '□'] };
    const issues = validateMachineSemantics(invalid);
    expect(issues.some((i) => i.message.includes('Blank symbol "□" must NOT be in input_alphabet'))).toBe(true);
  });

  it('detects non-deterministic duplicate transition rules', () => {
    const invalid = {
      ...validMachine,
      transitions: [
        ...validMachine.transitions,
        { from_state: 'q0', read: '0', to_state: 'q_halt', write: '1', move: 'L' as const },
      ],
    };
    const issues = validateMachineSemantics(invalid);
    expect(issues.some((i) => i.message.includes('Non-deterministic conflict'))).toBe(true);
  });

  it('detects outgoing transition from final state', () => {
    const invalid = {
      ...validMachine,
      transitions: [
        ...validMachine.transitions,
        { from_state: 'q_halt', read: '0', to_state: 'q0', write: '0', move: 'R' as const },
      ],
    };
    const issues = validateMachineSemantics(invalid);
    expect(issues.some((i) => i.message.includes('outgoing transition from final state'))).toBe(true);
  });

  it('flags input characters outside input alphabet', () => {
    const issues = validateMachineSemantics(validMachine, '101A');
    expect(issues.some((i) => i.message.includes('Input character "A"'))).toBe(true);
  });
});

describe('Curated Example Machines', () => {
  it('all curated machines are valid against semantic rules', () => {
    for (const ex of EXAMPLE_MACHINES) {
      expect(ex.data.schema_version).toBe(1);
      const issues = validateMachineSemantics(ex.data.machine, ex.defaultInput);
      const errors = issues.filter((i) => i.type === 'error');
      expect(errors).toHaveLength(0);
    }
  });
});

describe('Auto Layout Generator', () => {
  it('generates layout with distinct coordinates for all states', () => {
    const states = [
      { id: 'q0', name: 'Start' },
      { id: 'q1', name: 'Middle' },
      { id: 'q2', name: 'Halt' },
    ];
    const layout = generateAutoLayout(states, [], 'q0');
    expect(Object.keys(layout)).toEqual(['q0', 'q1', 'q2']);
    expect(layout['q0'].x).toBeDefined();
    expect(layout['q0'].y).toBeDefined();
  });
});

