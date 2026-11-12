"""Shared static and 10-step prefix feature extractor with strict anti-leakage guarantees.

Conforms to the Feature Protocol in AGENTS.md / DATA_AND_ML_PLAN.md:
- Static ordered columns (9):
    state_count, tape_alphabet_size, rule_density, final_reachable,
    self_loop_fraction, left_move_fraction, right_move_fraction,
    input_length, input_symbol_diversity
- Prefix ordered columns (5):
    prefix_states_visited, prefix_head_displacement, prefix_tape_span,
    prefix_symbol_changes, prefix_rule_repeats

Only the validated TuringMachine definition, the input string, and at most the first
10 transitions of simulation may be used. End-of-run outcomes (executed_steps,
halt_step, stop_reason, labels) and dataset metadata (machine_id, family, lineage_id)
are never accepted or read by feature extraction.
"""

from __future__ import annotations

from typing import Any

from backend.app.schemas import TraceEvent, TuringMachine
from backend.app.simulator import simulate

PREFIX_STEP_LIMIT = 10

STATIC_FEATURE_COLUMNS: tuple[str, ...] = (
    "state_count",
    "tape_alphabet_size",
    "rule_density",
    "final_reachable",
    "self_loop_fraction",
    "left_move_fraction",
    "right_move_fraction",
    "input_length",
    "input_symbol_diversity",
)

PREFIX_FEATURE_COLUMNS: tuple[str, ...] = (
    "prefix_states_visited",
    "prefix_head_displacement",
    "prefix_tape_span",
    "prefix_symbol_changes",
    "prefix_rule_repeats",
)

ALL_FEATURE_COLUMNS: tuple[str, ...] = STATIC_FEATURE_COLUMNS + PREFIX_FEATURE_COLUMNS

FORBIDDEN_LEAKAGE_KEYS: frozenset[str] = frozenset(
    {
        "executed_steps",
        "halt_step",
        "stop_reason",
        "halt_by_50",
        "halt_by_200",
        "halt_by_1000",
        "machine_id",
        "family",
        "lineage_id",
        "seed",
    }
)


def is_final_state_reachable(machine: TuringMachine) -> bool:
    """Return True if any state in machine.final_states is reachable from start_state."""
    final_set = set(machine.final_states)
    if not final_set:
        return False
    if machine.start_state in final_set:
        return True

    adj: dict[str, set[str]] = {}
    for t in machine.transitions:
        adj.setdefault(t.from_state, set()).add(t.to_state)

    visited = {machine.start_state}
    queue = [machine.start_state]
    while queue:
        curr = queue.pop(0)
        for nxt in adj.get(curr, ()):
            if nxt in final_set:
                return True
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return False


def extract_static_features(machine: TuringMachine, input_text: str) -> dict[str, float]:
    """Compute the 9 ordered static features from machine definition and input string."""
    n_states = len(machine.states)
    n_final = len(machine.final_states)
    n_non_final = max(0, n_states - n_final)
    n_tape_alpha = len(machine.tape_alphabet)
    n_input_alpha = max(1, len(machine.input_alphabet))
    n_rules = len(machine.transitions)

    possible_rules = n_non_final * n_tape_alpha
    rule_density = (n_rules / possible_rules) if possible_rules > 0 else 0.0

    if n_rules > 0:
        self_loops = sum(1 for t in machine.transitions if t.from_state == t.to_state)
        left_moves = sum(1 for t in machine.transitions if t.move == "L")
        right_moves = sum(1 for t in machine.transitions if t.move == "R")
        self_loop_fraction = self_loops / n_rules
        left_move_fraction = left_moves / n_rules
        right_move_fraction = right_moves / n_rules
    else:
        self_loop_fraction = 0.0
        left_move_fraction = 0.0
        right_move_fraction = 0.0

    input_len = len(input_text)
    symbol_diversity = (len(set(input_text)) / n_input_alpha) if input_len > 0 else 0.0

    return {
        "state_count": float(n_states),
        "tape_alphabet_size": float(n_tape_alpha),
        "rule_density": round(rule_density, 6),
        "final_reachable": 1.0 if is_final_state_reachable(machine) else 0.0,
        "self_loop_fraction": round(self_loop_fraction, 6),
        "left_move_fraction": round(left_move_fraction, 6),
        "right_move_fraction": round(right_move_fraction, 6),
        "input_length": float(input_len),
        "input_symbol_diversity": round(symbol_diversity, 6),
    }


def extract_prefix_features_from_trace(
    start_state: str, trace: list[TraceEvent]
) -> dict[str, float]:
    """Compute the 5 ordered prefix features from at most 10 TraceEvents."""
    if len(trace) > PREFIX_STEP_LIMIT:
        raise ValueError(
            f"Anti-leakage violation: trace length {len(trace)} exceeds PREFIX_STEP_LIMIT={PREFIX_STEP_LIMIT}"
        )
    for ev in trace:
        if ev.step > PREFIX_STEP_LIMIT:
            raise ValueError(
                f"Anti-leakage violation: trace event at step {ev.step} > {PREFIX_STEP_LIMIT}"
            )

    states_visited = {start_state}
    positions_visited = {0}
    symbol_changes = 0
    rules_used: list[int] = []

    for ev in trace:
        states_visited.add(ev.state_before)
        states_visited.add(ev.state_after)
        positions_visited.add(ev.head_before)
        positions_visited.add(ev.head_after)
        if ev.symbol_before != ev.symbol_after:
            symbol_changes += 1
        rules_used.append(ev.transition_index)

    head_displacement = trace[-1].head_after if trace else 0
    tape_span = (max(positions_visited) - min(positions_visited) + 1) if positions_visited else 1
    rule_repeats = len(rules_used) - len(set(rules_used))

    return {
        "prefix_states_visited": float(len(states_visited)),
        "prefix_head_displacement": float(head_displacement),
        "prefix_tape_span": float(tape_span),
        "prefix_symbol_changes": float(symbol_changes),
        "prefix_rule_repeats": float(rule_repeats),
    }


def extract_features(
    machine: TuringMachine,
    input_text: str,
    *,
    precomputed_trace: list[TraceEvent] | None = None,
) -> dict[str, float]:
    """Extract the 14 ordered static + 10-step prefix features.

    If `precomputed_trace` is omitted, runs `simulate(machine, input_text, step_limit=10, trace_limit=10)`.
    """
    static_feats = extract_static_features(machine, input_text)
    if precomputed_trace is None:
        prefix_res = simulate(
            machine,
            input_text=input_text,
            step_limit=PREFIX_STEP_LIMIT,
            trace_limit=PREFIX_STEP_LIMIT,
        )
        trace = prefix_res.trace
    else:
        trace = precomputed_trace

    prefix_feats = extract_prefix_features_from_trace(machine.start_state, trace)
    combined = {**static_feats, **prefix_feats}

    # Verify exact column order and ensure no forbidden keys exist
    assert tuple(combined.keys()) == ALL_FEATURE_COLUMNS
    assert not (set(combined.keys()) & FORBIDDEN_LEAKAGE_KEYS)
    return combined


def extract_feature_vector(
    machine: TuringMachine,
    input_text: str,
    *,
    precomputed_trace: list[TraceEvent] | None = None,
) -> list[float]:
    """Return the 14 features as an ordered float vector matching ALL_FEATURE_COLUMNS."""
    feat_dict = extract_features(
        machine, input_text, precomputed_trace=precomputed_trace
    )
    return [feat_dict[col] for col in ALL_FEATURE_COLUMNS]


def observe_prefix_and_extract(
    machine: TuringMachine, input_text: str
) -> dict[str, Any]:
    """Run the 10-step prefix simulation once for online inference or dataset preparation.

    Separates observed early halts (T <= 10) from runs that remain active after
    10 steps and require learned model predictions.
    """
    prefix_res = simulate(
        machine,
        input_text=input_text,
        step_limit=PREFIX_STEP_LIMIT,
        trace_limit=PREFIX_STEP_LIMIT,
    )
    features = extract_features(
        machine, input_text, precomputed_trace=prefix_res.trace
    )
    observed_early_halt = prefix_res.halted_within_limit
    return {
        "observed_early_halt": observed_early_halt,
        "prefix_steps_executed": prefix_res.steps,
        "prefix_stop_reason": prefix_res.stop_reason if observed_early_halt else None,
        "exact_early_labels": (
            {"halt_by_50": 1, "halt_by_200": 1, "halt_by_1000": 1}
            if observed_early_halt
            else None
        ),
        "features": features,
        "feature_vector": [features[col] for col in ALL_FEATURE_COLUMNS],
    }

