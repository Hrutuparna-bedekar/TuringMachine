"""Framework-independent deterministic Turing Machine simulation engine.

This module provides a pure Python, high-performance, stateless implementation of a
Deterministic Turing Machine with a bidirectional unbounded sparse tape.
It has zero dependencies on web frameworks (e.g. FastAPI) and is designed for direct
import by both backend API routes and offline ML batch execution pipelines.
"""

from backend.app.schemas import (
    InitialConfiguration,
    SimulationResponse,
    TapeCell,
    TraceEvent,
    TuringMachine,
)


def simulate(
    machine: TuringMachine,
    input_text: str,
    step_limit: int,
    *,
    trace_limit: int | None = None,
) -> SimulationResponse:
    """Execute a deterministic Turing Machine on an input string up to a step budget.

    Parameters
    ----------
    machine : TuringMachine
        The validated Turing Machine definition containing states, alphabets,
        and transitions.
    input_text : str
        The input string written on the tape starting at position 0.
    step_limit : int
        Maximum number of transitions permitted to execute. Must be >= 0.
    trace_limit : int | None, optional
        Maximum number of execution trace events to record. If None, all executed
        transitions are recorded. If 0, no trace events are recorded. If N > 0,
        at most the first N transitions are recorded. Note that trace_limit only
        governs observation and has no effect on execution semantics or step counting.

    Returns
    -------
    SimulationResponse
        Structured outcome containing halted status, stop reason, executed steps,
        initial tape snapshot, and recorded trace events.
    """
    # 1. Parameter validation
    if isinstance(step_limit, bool) or not isinstance(step_limit, int) or step_limit < 0:
        raise ValueError(
            f"step_limit must be a non-negative integer (booleans not accepted), got {step_limit!r}"
        )

    if trace_limit is not None:
        if isinstance(trace_limit, bool) or not isinstance(trace_limit, int) or trace_limit < 0:
            raise ValueError(
                f"trace_limit must be None or a non-negative integer (booleans not accepted), got {trace_limit!r}"
            )

    if not isinstance(input_text, str):
        raise ValueError(f"input_text must be a string, got {type(input_text).__name__}")

    input_alphabet_set = set(machine.input_alphabet)
    for idx, ch in enumerate(input_text):
        if ch not in input_alphabet_set:
            raise ValueError(
                f"Character {ch!r} at index {idx} does not belong to the machine's input_alphabet"
            )

    # 2. Tape initialization (sparse dict: only non-blank cells stored)
    tape: dict[int, str] = {}
    for pos, char in enumerate(input_text):
        if char != machine.blank_symbol:
            tape[pos] = char

    # 3. Create initial configuration snapshot (immutable, non-blank cells sorted by position)
    initial_cells = [
        TapeCell(position=pos, symbol=sym) for pos, sym in sorted(tape.items())
    ]
    initial_config = InitialConfiguration(
        state=machine.start_state,
        head=0,
        cells=initial_cells,
    )

    # 4. Pre-index transitions for O(1) constant-time lookup
    # Key: (from_state, read_symbol) -> (original_index, Transition)
    lookup = {
        (t.from_state, t.read): (idx, t)
        for idx, t in enumerate(machine.transitions)
    }

    # 5. Simulation loop state
    current_state = machine.start_state
    head = 0
    steps = 0
    trace: list[TraceEvent] = []
    final_states_set = set(machine.final_states)

    # 6. Core execution loop with strict priority ordering
    while True:
        # CHECK 1: Terminal condition — Current state is in final_states
        if current_state in final_states_set:
            return SimulationResponse(
                halted_within_limit=True,
                stop_reason="final_state",
                steps=steps,
                initial=initial_config,
                trace=trace,
            )

        # Current symbol under the head
        current_symbol = tape.get(head, machine.blank_symbol)

        # CHECK 2: Terminal condition — No applicable transition exists (stuck)
        # Note: A failed lookup consumes ZERO transitions.
        if (current_state, current_symbol) not in lookup:
            return SimulationResponse(
                halted_within_limit=True,
                stop_reason="missing_transition",
                steps=steps,
                initial=initial_config,
                trace=trace,
            )

        # CHECK 3: Budget check — Step limit reached while transition is still executable
        if steps == step_limit:
            return SimulationResponse(
                halted_within_limit=False,
                stop_reason="step_limit",
                steps=steps,
                initial=initial_config,
                trace=trace,
            )

        # CHECK 4: Execute transition
        rule_idx, rule = lookup[(current_state, current_symbol)]
        next_head = head + (1 if rule.move == "R" else -1)

        # Record trace event if budget remains in trace_limit
        if trace_limit is None or len(trace) < trace_limit:
            trace.append(
                TraceEvent(
                    step=steps + 1,
                    transition_index=rule_idx,
                    state_before=current_state,
                    state_after=rule.to_state,
                    head_before=head,
                    head_after=next_head,
                    symbol_before=current_symbol,
                    symbol_after=rule.write,
                )
            )

        # Tape write: normalize by removing blank entries from sparse dictionary
        if rule.write == machine.blank_symbol:
            tape.pop(head, None)
        else:
            tape[head] = rule.write

        # Head move & state transition
        head = next_head
        current_state = rule.to_state
        steps += 1
