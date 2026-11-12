"""Ordered, versioned feature extraction for Turing Machine halting prediction.

Provides deterministic feature extraction for static machine graph properties
and execution trace prefix properties (first 10 transitions).
Shared between training, evaluation, and online API inference.
"""

from collections import deque
from typing import Sequence

from backend.app.schemas import TraceEvent, TuringMachine

# 1. Authoritative Feature Column Lists (Exact Order Specified in Plan)
STATIC_FEATURE_NAMES: list[str] = [
    "state_count",
    "tape_alphabet_size",
    "rule_density",
    "final_reachable",
    "self_loop_fraction",
    "left_move_fraction",
    "right_move_fraction",
    "input_length",
    "input_symbol_diversity",
]

PREFIX_FEATURE_NAMES: list[str] = [
    "prefix_states_visited",
    "prefix_head_displacement",
    "prefix_tape_span",
    "prefix_symbol_changes",
    "prefix_rule_repeats",
]

ALL_FEATURE_NAMES: list[str] = STATIC_FEATURE_NAMES + PREFIX_FEATURE_NAMES

FEATURE_VERSION: int = 1


def is_final_state_reachable(machine: TuringMachine) -> bool:
    """Check if any final state is reachable from the start state in the transition graph."""
    final_states_set = set(machine.final_states)
    if not final_states_set:
        return False
    if machine.start_state in final_states_set:
        return True

    # Adjacency list: from_state -> set of to_states
    adj: dict[str, set[str]] = {}
    for t in machine.transitions:
        adj.setdefault(t.from_state, set()).add(t.to_state)

    visited: set[str] = {machine.start_state}
    queue: deque[str] = deque([machine.start_state])

    while queue:
        curr = queue.popleft()
        for nxt in adj.get(curr, ()):
            if nxt in final_states_set:
                return True
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    return False


def extract_static_features(machine: TuringMachine, input_text: str) -> dict[str, float]:
    """Extract graph and structural features of the Turing Machine and input string."""
    state_count = len(machine.states)
    tape_alphabet_size = len(machine.tape_alphabet)
    num_rules = len(machine.transitions)
    num_final_states = len(machine.final_states)

    # Rule density: defined rules / possible non-final state and tape symbol pairs
    denom = (state_count - num_final_states) * tape_alphabet_size
    rule_density = (num_rules / denom) if denom > 0 else 0.0

    final_reachable = 1.0 if is_final_state_reachable(machine) else 0.0

    # Fractions over total rules
    if num_rules > 0:
        self_loop_count = sum(1 for t in machine.transitions if t.from_state == t.to_state)
        left_moves = sum(1 for t in machine.transitions if t.move == "L")
        right_moves = sum(1 for t in machine.transitions if t.move == "R")
        self_loop_fraction = self_loop_count / num_rules
        left_move_fraction = left_moves / num_rules
        right_move_fraction = right_moves / num_rules
    else:
        self_loop_fraction = 0.0
        left_move_fraction = 0.0
        right_move_fraction = 0.0

    input_length = float(len(input_text))
    input_symbol_diversity = float(len(set(input_text)))

    return {
        "state_count": float(state_count),
        "tape_alphabet_size": float(tape_alphabet_size),
        "rule_density": float(rule_density),
        "final_reachable": final_reachable,
        "self_loop_fraction": float(self_loop_fraction),
        "left_move_fraction": float(left_move_fraction),
        "right_move_fraction": float(right_move_fraction),
        "input_length": input_length,
        "input_symbol_diversity": input_symbol_diversity,
    }


def extract_prefix_features(
    machine: TuringMachine,
    input_text: str,
    trace: Sequence[TraceEvent],
) -> dict[str, float]:
    """Extract behavioral features from an execution trace prefix (up to 10 transitions)."""
    # Visited states include the start state and all states reached after transitions
    visited_states = {machine.start_state}
    for e in trace:
        visited_states.add(e.state_after)
    prefix_states_visited = float(len(visited_states))

    # Visited positions include initial head position (0) and head after each event
    visited_positions = {0}
    for e in trace:
        visited_positions.add(e.head_after)
    min_pos = min(visited_positions)
    max_pos = max(visited_positions)
    prefix_tape_span = float(max_pos - min_pos + 1)

    # Signed head displacement (final head position - initial head position 0)
    prefix_head_displacement = float(trace[-1].head_after if trace else 0)

    # Symbol changes: count of events where symbol_after != symbol_before
    prefix_symbol_changes = float(
        sum(1 for e in trace if e.symbol_after != e.symbol_before)
    )

    # Rule repeats: count of repeated rule executions after a rule's first use
    # Total transitions in prefix minus number of unique rules used
    unique_rules = {e.transition_index for e in trace}
    prefix_rule_repeats = float(len(trace) - len(unique_rules))

    return {
        "prefix_states_visited": prefix_states_visited,
        "prefix_head_displacement": prefix_head_displacement,
        "prefix_tape_span": prefix_tape_span,
        "prefix_symbol_changes": prefix_symbol_changes,
        "prefix_rule_repeats": prefix_rule_repeats,
    }


def extract_features(
    machine: TuringMachine,
    input_text: str,
    trace: Sequence[TraceEvent],
    feature_names: list[str] | None = None,
) -> dict[str, float]:
    """Extract ordered features according to specified feature_names (or ALL_FEATURE_NAMES)."""
    target_names = feature_names if feature_names is not None else ALL_FEATURE_NAMES
    static_feats = extract_static_features(machine, input_text)
    prefix_feats = extract_prefix_features(machine, input_text, trace)

    all_feats = {**static_feats, **prefix_feats}
    return {name: all_feats[name] for name in target_names}


extract_all_features = extract_features


def extract_feature_vector(
    machine: TuringMachine,
    input_text: str,
    trace: Sequence[TraceEvent],
    feature_names: list[str] | None = None,
) -> list[float]:
    """Extract features as an ordered numerical list suitable for scikit-learn models."""
    feats = extract_features(machine, input_text, trace, feature_names)
    return list(feats.values())
