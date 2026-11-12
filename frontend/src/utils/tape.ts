import { InitialConfiguration, TraceEvent, TuringMachine, State, Transition, NodeLayout } from '../types';

export interface ReconstructedTapeState {
  tapeMap: Record<number, string>;
  head: number;
  state: string;
  lastEvent: TraceEvent | null;
  minPos: number;
  maxPos: number;
}

/**
 * Reconstructs the exact tape, head position, and state at any step in the trace.
 * Step 0 represents the initial configuration before any transitions occur.
 */
export function reconstructTapeAtStep(
  initial: InitialConfiguration,
  trace: TraceEvent[],
  step: number,
  blankSymbol: string
): ReconstructedTapeState {
  // 1. Initialize tape with initial non-blank cells
  const tapeMap: Record<number, string> = {};
  for (const cell of initial.cells) {
    tapeMap[cell.position] = cell.symbol;
  }

  let head = initial.head ?? 0;
  let state = initial.state;
  let lastEvent: TraceEvent | null = null;

  // 2. Bound step between 0 and trace.length
  const safeStep = Math.max(0, Math.min(step, trace.length));

  // 3. Replay transitions chronologically up to safeStep
  for (let i = 0; i < safeStep; i++) {
    const event = trace[i];
    tapeMap[event.head_before] = event.symbol_after;
    head = event.head_after;
    state = event.state_after;
    lastEvent = event;
  }

  // 4. Calculate bounds for rendering
  const positions = Object.keys(tapeMap).map(Number);
  positions.push(head);
  // Ensure a comfortable margin of cells around the head and written tape
  const minPos = Math.min(-3, Math.min(...positions) - 2);
  const maxPos = Math.max(5, Math.max(...positions) + 2);

  // Fill in blanks if undefined in range
  for (let pos = minPos; pos <= maxPos; pos++) {
    if (tapeMap[pos] === undefined) {
      tapeMap[pos] = blankSymbol;
    }
  }

  return {
    tapeMap,
    head,
    state,
    lastEvent,
    minPos,
    maxPos,
  };
}

export interface ValidationIssue {
  type: 'error' | 'warning';
  message: string;
  field?: string;
}

/**
 * Client-side semantic validator matching backend Pydantic model validation.
 */
export function validateMachineSemantics(machine: TuringMachine, inputString?: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const scalar = (value: unknown): value is string =>
    typeof value === 'string' && Array.from(value).length === 1 &&
    !/^[\uD800-\uDFFF]$/.test(value);

  if (!Array.isArray(machine.states) || machine.states.length < 1 || machine.states.length > 64) {
    return [{ type: 'error', message: 'Machine must have between 1 and 64 states.' }];
  }
  if (!Array.isArray(machine.final_states) || !Array.isArray(machine.transitions) ||
      machine.transitions.length > 1024) {
    return [{ type: 'error', message: 'Expected an array of final states and up to 1,024 transition rules.' }];
  }
  for (const alphabet of [machine.input_alphabet, machine.tape_alphabet]) {
    if (!Array.isArray(alphabet) || alphabet.length < 1 || alphabet.length > 32 ||
        !alphabet.every(scalar) || new Set(alphabet).size !== alphabet.length) {
      return [{ type: 'error', message: 'Each alphabet must contain 1 to 32 distinct Unicode symbols.' }];
    }
  }

  const stateIds = new Set<string>();
  for (const s of machine.states) {
    if (!s || typeof s.id !== 'string' || typeof s.name !== 'string' ||
        !s.id.trim() || !s.name.trim() || Array.from(s.id).length > 64 || Array.from(s.name).length > 64) {
      return [{ type: 'error', message: 'State IDs and names must be nonempty and at most 64 characters.' }];
    }
    if (stateIds.has(s.id)) {
      issues.push({ type: 'error', message: `Duplicate state ID detected: "${s.id}".` });
    }
    stateIds.add(s.id);
  }

  // 2. Start state check
  if (!machine.start_state || !stateIds.has(machine.start_state)) {
    issues.push({ type: 'error', message: `Start state "${machine.start_state}" does not exist in declared states.` });
  }

  // 3. Final states check
  const finalSet = new Set<string>();
  for (const f of machine.final_states) {
    if (finalSet.has(f)) {
      issues.push({ type: 'error', message: `Duplicate final state: "${f}".` });
    }
    if (!stateIds.has(f)) {
      issues.push({ type: 'error', message: `Final state "${f}" does not exist in declared states.` });
    }
    finalSet.add(f);
  }

  // 4. Alphabets & Blank Symbol check
  const inputSet = new Set(machine.input_alphabet);
  const tapeSet = new Set(machine.tape_alphabet);

  if (!scalar(machine.blank_symbol)) {
    issues.push({ type: 'error', message: 'Blank symbol must be exactly one Unicode code point.' });
  }

  if (!tapeSet.has(machine.blank_symbol)) {
    issues.push({ type: 'error', message: `Blank symbol "${machine.blank_symbol}" must belong to tape_alphabet.` });
  }

  if (inputSet.has(machine.blank_symbol)) {
    issues.push({ type: 'error', message: `Blank symbol "${machine.blank_symbol}" must NOT be in input_alphabet.` });
  }

  for (const sym of machine.input_alphabet) {
    if (!tapeSet.has(sym)) {
      issues.push({ type: 'error', message: `Input symbol "${sym}" must be present in tape_alphabet.` });
    }
  }

  // 5. Transitions check
  const seenKeys = new Set<string>();
  for (let i = 0; i < machine.transitions.length; i++) {
    const t = machine.transitions[i];
    if (!t || (t.move !== 'L' && t.move !== 'R')) {
      issues.push({ type: 'error', message: `Rule #${i + 1}: movement must be L or R.` });
      continue;
    }
    if (!stateIds.has(t.from_state)) {
      issues.push({ type: 'error', message: `Rule #${i + 1}: unknown from_state "${t.from_state}".` });
    }
    if (!stateIds.has(t.to_state)) {
      issues.push({ type: 'error', message: `Rule #${i + 1}: unknown to_state "${t.to_state}".` });
    }
    if (!tapeSet.has(t.read)) {
      issues.push({ type: 'error', message: `Rule #${i + 1}: read symbol "${t.read}" not in tape_alphabet.` });
    }
    if (!tapeSet.has(t.write)) {
      issues.push({ type: 'error', message: `Rule #${i + 1}: write symbol "${t.write}" not in tape_alphabet.` });
    }
    if (finalSet.has(t.from_state)) {
      issues.push({
        type: 'error',
        message: `Rule #${i + 1}: outgoing transition from final state "${t.from_state}". Final states must have no outgoing rules.`,
      });
    }

    const key = JSON.stringify([t.from_state, t.read]);
    if (seenKeys.has(key)) {
      issues.push({
        type: 'error',
        message: `Non-deterministic conflict: multiple rules for state "${t.from_state}" reading "${t.read}".`,
      });
    }
    seenKeys.add(key);
  }

  // 6. Optional input string check
  if (inputString !== undefined) {
    const symbols = Array.from(inputString);
    if (symbols.length > 512) {
      issues.push({ type: 'error', message: 'The input must contain at most 512 symbols.' });
    }
    for (const char of symbols) {
      if (!inputSet.has(char)) {
        issues.push({
          type: 'error',
          message: `Input character "${char}" does not belong to input_alphabet.`,
        });
      }
    }
  }

  return issues;
}

/**
 * Computes neat coordinates for state nodes when no saved layout is available.
 */
export function generateAutoLayout(
  states: State[],
  _transitions: Transition[],
  startState: string
): Record<string, NodeLayout> {
  const layout: Record<string, NodeLayout> = {};
  const n = states.length;
  if (n === 0) return layout;

  if (n <= 3) {
    // Linear horizontal layout
    const ordered = [
      ...states.filter((s) => s.id === startState),
      ...states.filter((s) => s.id !== startState),
    ];
    ordered.forEach((s, idx) => {
      layout[s.id] = {
        x: 100 + idx * 240,
        y: 180,
      };
    });
    return layout;
  }

  // Circle or grid layout for larger graphs
  const centerX = 360;
  const centerY = 240;
  const radius = Math.min(220, 80 + n * 25);

  // Put start state on the left
  const otherStates = states.filter((s) => s.id !== startState);
  const ordered = states.find((s) => s.id === startState)
    ? [states.find((s) => s.id === startState)!, ...otherStates]
    : states;

  ordered.forEach((s, idx) => {
    const angle = (idx / n) * 2 * Math.PI - Math.PI; // start from -PI (left)
    layout[s.id] = {
      x: Math.round(centerX + radius * Math.cos(angle)),
      y: Math.round(centerY + radius * Math.sin(angle)),
    };
  });

  return layout;
}

