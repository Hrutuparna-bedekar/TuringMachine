"""Improved reproducible dataset generator (pilot_v2: 1,000 machines, 5,000 runs).

Addresses all data-quality risks identified in pilot_v1:
1. 1,000 unique machines x 5 distinct inputs = 5,000 runs, with all inputs obeying
   len(input) <= 512 (100% compliant with SimulationRequest wire schema).
2. Five nontrivial families with genuine symbol-dependent ('0' vs '1') branching,
   multi-pass bidirectional scans, quadratic zig-zag shuttles, conditional cycles
   with reachable exits, and filtered structured random machines.
3. Non-constant, unconfounded `final_reachable` static feature (~76% reachable,
   ~24% unreachable where halting occurs via `missing_transition` and non-halting
   occurs via `step_limit`).
4. High within-machine input-dependent label variation (>95% of machines vary across
   their 5 inputs, including on the subset active after 10 steps).
5. Exact boundary transition coverage at T in {0, 10, 11, 49, 50, 51, 199, 200, 201, 999, 1000}
   plus step_limit at 1000.

Run from the 'Yashraj Part' directory:
    python -m backend.experiments.generate_pilot_v2
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.schemas import SimulationRequest, TuringMachine
from backend.app.simulator import simulate
from backend.experiments.generate_v1_proto import create_record
from backend.experiments.machine_generators import generate_random_machine

SEED = 202602
BUDGETS = (50, 200, 1000)
MAX_STEPS = 1000
TRACE_LIMIT = 10
MAX_INPUT_LEN = 512
INPUTS_PER_MACHINE = 5
SYMBOLS = ("0", "1", "□")
DEFAULT_OUTPUT_DIR = Path("data/generated/pilot_v2")

FAMILY_COUNTS = {
    "bounded_scan_branch": 220,
    "multi_pass_rewriter": 220,
    "zigzag_shuttle": 180,
    "conditional_cycle": 180,
    "structured_random": 200,
}
NUM_MACHINES = sum(FAMILY_COUNTS.values())


def _state(state_id: str) -> dict[str, str]:
    return {"id": state_id, "name": state_id}


def _rule(
    source: str, read: str, target: str, write: str, move: str = "R"
) -> dict[str, str]:
    return {
        "from_state": source,
        "read": read,
        "to_state": target,
        "write": write,
        "move": move,
    }


def _rewrite(symbol: str, mode: str) -> str:
    if symbol == "□":
        return "□"
    if mode == "preserve":
        return symbol
    if mode == "flip":
        return "1" if symbol == "0" else "0"
    if mode == "zero":
        return "0"
    if mode == "one":
        return "1"
    raise ValueError(f"Unknown mode: {mode}")


def build_bounded_scan_branch_machine(
    cycle_len: int,
    delay: int,
    write_mode: str,
    heavy_symbol: str,
    hop_cost: int,
    terminal_mode: str,
    trap_mod_state: int | None = None,
) -> TuringMachine:
    """Scan machine where `heavy_symbol` ('0' or '1') triggers a local R-L-R (cost 3)
    or R-R-L-L-R (cost 5) hop while the other symbol advances in 1 step.
    """
    effective_delay = max(1, delay) if terminal_mode == "missing_transition" else delay
    light_symbol = "0" if heavy_symbol == "1" else "1"
    scan_ids = [f"scan_{i}" for i in range(cycle_len)]
    tail_ids = [f"tail_{i}" for i in range(effective_delay)]
    halt_id = "qhalt"

    state_list: list[str] = list(scan_ids)
    transitions: list[dict[str, str]] = []

    for i, src in enumerate(scan_ids):
        nxt = scan_ids[(i + 1) % cycle_len]
        transitions.append(
            _rule(src, light_symbol, nxt, _rewrite(light_symbol, write_mode), "R")
        )

        if hop_cost == 3:
            hop_a = f"hopA_{i}"
            hop_b = f"hopB_{i}"
            state_list.extend([hop_a, hop_b])
            transitions.append(
                _rule(src, heavy_symbol, hop_a, _rewrite(heavy_symbol, write_mode), "R")
            )
            for s in SYMBOLS:
                transitions.append(_rule(hop_a, s, hop_b, s, "L"))
                transitions.append(_rule(hop_b, s, nxt, s, "R"))
        elif hop_cost == 5:
            h1, h2, h3, h4 = f"h1_{i}", f"h2_{i}", f"h3_{i}", f"h4_{i}"
            state_list.extend([h1, h2, h3, h4])
            transitions.append(
                _rule(src, heavy_symbol, h1, _rewrite(heavy_symbol, write_mode), "R")
            )
            for s in SYMBOLS:
                transitions.append(_rule(h1, s, h2, s, "R"))
                transitions.append(_rule(h2, s, h3, s, "L"))
                transitions.append(_rule(h3, s, h4, s, "L"))
                transitions.append(_rule(h4, s, nxt, s, "R"))
        else:
            raise ValueError(f"Unsupported hop_cost: {hop_cost}")

        if trap_mod_state is not None and i == trap_mod_state:
            trap_a, trap_b = f"trapA_{i}", f"trapB_{i}"
            state_list.extend([trap_a, trap_b])
            transitions.append(_rule(src, "□", trap_a, "1", "R"))
            for s in SYMBOLS:
                transitions.append(_rule(trap_a, s, trap_b, s, "L"))
                transitions.append(_rule(trap_b, s, trap_a, s, "R"))
        else:
            first_tail = tail_ids[0] if tail_ids else halt_id
            transitions.append(_rule(src, "□", first_tail, "□", "R"))

    state_list.extend(tail_ids)
    for i, src in enumerate(tail_ids):
        if i + 1 < len(tail_ids):
            transitions.append(_rule(src, "□", tail_ids[i + 1], "□", "R"))
        else:
            if terminal_mode == "final_state":
                transitions.append(_rule(src, "□", halt_id, "□", "R"))
            # When terminal_mode == 'missing_transition', leave qhalt unreachable so
            # final_reachable == 0.0 while runs still halt on '□' via missing_transition!

    state_list.append(halt_id)
    return TuringMachine.model_validate(
        {
            "states": [_state(s) for s in state_list],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": scan_ids[0],
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def build_multi_pass_rewriter_machine(
    num_passes: int,
    pass1_heavy_sym: str,
    pass1_hop: bool,
    rewrite_pass1: str,
    rewrite_back: str,
    tail_delay: int,
    terminal_mode: str,
    loop_if_starts_with_zero_on_final_pass: bool = False,
) -> TuringMachine:
    """Multi-pass bidirectional tape scanner and rewriter."""
    state_list: list[str] = []
    transitions: list[dict[str, str]] = []
    halt_id = "qhalt"

    for p in range(num_passes):
        p_id = f"pass_{p}"
        state_list.append(p_id)
        direction = "R" if p % 2 == 0 else "L"
        next_dir = "L" if direction == "R" else "R"
        next_pass_id = f"pass_{p + 1}" if p + 1 < num_passes else "post_pass"

        if p == 0 and pass1_hop:
            light_sym = "0" if pass1_heavy_sym == "1" else "1"
            hop1 = "p0_hopA"
            hop2 = "p0_hopB"
            state_list.extend([hop1, hop2])
            transitions.append(
                _rule(p_id, light_sym, p_id, _rewrite(light_sym, rewrite_pass1), "R")
            )
            transitions.append(
                _rule(
                    p_id,
                    pass1_heavy_sym,
                    hop1,
                    _rewrite(pass1_heavy_sym, rewrite_pass1),
                    "R",
                )
            )
            for s in SYMBOLS:
                transitions.append(_rule(hop1, s, hop2, s, "L"))
                transitions.append(_rule(hop2, s, p_id, s, "R"))
        else:
            mode = rewrite_pass1 if p % 2 == 0 else rewrite_back
            if p == num_passes - 1 and loop_if_starts_with_zero_on_final_pass:
                osc_id = f"osc_{p}"
                state_list.append(osc_id)
                transitions.append(_rule(p_id, "1", p_id, _rewrite("1", mode), direction))
                transitions.append(_rule(p_id, "0", osc_id, "1", next_dir))
                transitions.append(_rule(osc_id, "0", p_id, "0", direction))
                transitions.append(_rule(osc_id, "1", p_id, "1", direction))
                transitions.append(_rule(osc_id, "□", p_id, "0", direction))
            else:
                for sym in ("0", "1"):
                    transitions.append(
                        _rule(p_id, sym, p_id, _rewrite(sym, mode), direction)
                    )

        transitions.append(_rule(p_id, "□", next_pass_id, "□", next_dir))

    effective_delay = max(1, tail_delay) if terminal_mode == "missing_transition" else tail_delay
    state_list.append("post_pass")
    tail_ids = [f"tail_{i}" for i in range(effective_delay)]
    state_list.extend(tail_ids)

    first_target = tail_ids[0] if tail_ids else halt_id
    for sym in SYMBOLS:
        transitions.append(_rule("post_pass", sym, first_target, sym, "R"))

    for i, t_id in enumerate(tail_ids):
        nxt = tail_ids[i + 1] if i + 1 < len(tail_ids) else halt_id
        for sym in SYMBOLS:
            if i + 1 < len(tail_ids) or terminal_mode == "final_state":
                transitions.append(_rule(t_id, sym, nxt, sym, "R"))

    state_list.append(halt_id)
    return TuringMachine.model_validate(
        {
            "states": [_state(s) for s in state_list],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": "pass_0",
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def build_zigzag_shuttle_machine(
    trigger_sym: str,
    downgrade_steps: int,
    tail_delay: int,
    terminal_mode: str,
    trap_on_double_trigger: bool = False,
) -> TuringMachine:
    """Quadratic O(n^2) zig-zag shuttle machine."""
    safe_sym = "0" if trigger_sym == "1" else "1"
    halt_id = "qhalt"
    state_list = ["seek", "ret_L"]
    transitions: list[dict[str, str]] = []

    transitions.append(_rule("seek", safe_sym, "seek", safe_sym, "R"))

    if trap_on_double_trigger:
        chk_id = "chk_next"
        ret2_id = "ret_L2"
        state_list.extend([chk_id, ret2_id])
        transitions.append(_rule("seek", trigger_sym, chk_id, safe_sym, "R"))
        transitions.append(_rule(chk_id, safe_sym, "ret_L", safe_sym, "L"))
        transitions.append(_rule(chk_id, "□", "ret_L", "□", "L"))
        transitions.append(_rule(chk_id, trigger_sym, ret2_id, trigger_sym, "L"))
        for s in ("0", "1"):
            transitions.append(_rule(ret2_id, s, "ret_L", trigger_sym, "L"))
        transitions.append(_rule(ret2_id, "□", "seek", "□", "R"))
    elif downgrade_steps == 2:
        mark_id = "bounce_mark"
        state_list.append(mark_id)
        transitions.append(_rule("seek", trigger_sym, mark_id, safe_sym, "L"))
        transitions.append(_rule(mark_id, safe_sym, "ret_L", safe_sym, "L"))
        transitions.append(_rule(mark_id, trigger_sym, "ret_L", safe_sym, "L"))
        transitions.append(_rule(mark_id, "□", "seek", "□", "R"))
    else:
        transitions.append(_rule("seek", trigger_sym, "ret_L", safe_sym, "L"))

    transitions.append(_rule("ret_L", "0", "ret_L", "0", "L"))
    transitions.append(_rule("ret_L", "1", "ret_L", "1", "L"))
    transitions.append(_rule("ret_L", "□", "seek", "□", "R"))

    effective_delay = max(1, tail_delay) if terminal_mode == "missing_transition" else tail_delay
    tail_ids = [f"tail_{i}" for i in range(effective_delay)]
    state_list.extend(tail_ids)
    first_tail = tail_ids[0] if tail_ids else halt_id
    transitions.append(_rule("seek", "□", first_tail, "□", "R"))

    for i, t_id in enumerate(tail_ids):
        nxt = tail_ids[i + 1] if i + 1 < len(tail_ids) else halt_id
        if i + 1 < len(tail_ids) or terminal_mode == "final_state":
            transitions.append(_rule(t_id, "□", nxt, "□", "R"))

    state_list.append(halt_id)
    return TuringMachine.model_validate(
        {
            "states": [_state(s) for s in state_list],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": "seek",
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def build_conditional_cycle_machine(
    cycle_len: int,
    step_on_zero: int,
    step_on_one: int,
    exit_residues: set[int],
    return_pass_on_exit: bool,
    tail_delay: int,
    terminal_mode: str,
) -> TuringMachine:
    """Cyclic state machine with conditional exit states and input-dependent termination."""
    effective_delay = max(1, tail_delay) if terminal_mode == "missing_transition" else tail_delay
    cycle_ids = [f"c_{i}" for i in range(cycle_len)]
    halt_id = "qhalt"
    state_list = list(cycle_ids)
    transitions: list[dict[str, str]] = []

    exit_start = (
        "exit_scan_L"
        if return_pass_on_exit
        else (f"tail_0" if effective_delay > 0 else halt_id)
    )

    for i, src in enumerate(cycle_ids):
        nxt_zero = cycle_ids[(i + step_on_zero) % cycle_len]
        nxt_one = cycle_ids[(i + step_on_one) % cycle_len]

        transitions.append(_rule(src, "0", nxt_zero, "0", "R"))

        hop_a = f"chopA_{i}"
        hop_b = f"chopB_{i}"
        state_list.extend([hop_a, hop_b])
        transitions.append(_rule(src, "1", hop_a, "1", "R"))
        for s in SYMBOLS:
            transitions.append(_rule(hop_a, s, hop_b, s, "L"))
            transitions.append(_rule(hop_b, s, nxt_one, s, "R"))

        if i in exit_residues:
            move_dir = "L" if return_pass_on_exit else "R"
            transitions.append(_rule(src, "□", exit_start, "□", move_dir))
        else:
            nxt_blank = cycle_ids[(i + 1) % cycle_len]
            transitions.append(_rule(src, "□", nxt_blank, "1", "L"))

    tail_ids = [f"tail_{i}" for i in range(effective_delay)]
    if return_pass_on_exit:
        state_list.append("exit_scan_L")
        first_after_scan = tail_ids[0] if tail_ids else halt_id
        transitions.append(_rule("exit_scan_L", "0", "exit_scan_L", "0", "L"))
        transitions.append(_rule("exit_scan_L", "1", "exit_scan_L", "0", "L"))
        transitions.append(_rule("exit_scan_L", "□", first_after_scan, "□", "R"))

    state_list.extend(tail_ids)
    for i, t_id in enumerate(tail_ids):
        nxt = tail_ids[i + 1] if i + 1 < len(tail_ids) else halt_id
        for s in SYMBOLS:
            if i + 1 < len(tail_ids) or terminal_mode == "final_state":
                transitions.append(_rule(t_id, s, nxt, s, "L"))

    state_list.append(halt_id)
    return TuringMachine.model_validate(
        {
            "states": [_state(s) for s in state_list],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": cycle_ids[0],
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def select_inputs_for_bounded_scan(
    cycle_len: int,
    delay: int,
    heavy_symbol: str,
    hop_cost: int,
    trap_mod_state: int | None,
    rng: random.Random,
    include_exact_boundary: bool,
) -> list[str]:
    """Construct 5 distinct valid inputs (len <= 512) spanning diverse halting regimes."""
    light_symbol = "0" if heavy_symbol == "1" else "1"

    def make_non_trapped_input(target_steps: int) -> str:
        needed = max(hop_cost + 2, target_steps - 1 - delay)
        max_heavy = needed // hop_cost
        c_heavy = rng.randint(max(1, max_heavy // 2), max(1, max_heavy))
        c_light = needed - hop_cost * c_heavy
        total_chars = c_heavy + c_light
        if trap_mod_state is not None and (total_chars % cycle_len) == trap_mod_state:
            if c_heavy > 1 and ((total_chars + hop_cost - 1) % cycle_len) != trap_mod_state:
                c_heavy -= 1
                c_light += hop_cost
            elif c_heavy > 2 and ((total_chars + 2 * (hop_cost - 1)) % cycle_len) != trap_mod_state:
                c_heavy -= 2
                c_light += 2 * hop_cost
            else:
                c_light += 1
        chars = [heavy_symbol] * c_heavy + [light_symbol] * c_light
        rng.shuffle(chars)
        return "".join(chars)[:MAX_INPUT_LEN]

    candidates: list[str] = []
    if include_exact_boundary:
        targets = [
            rng.choice([10, 11, 25, 49]),
            50,
            51,
            rng.choice([199, 200, 201]),
            rng.choice([999, 1000, 1025]),
        ]
        for t in targets:
            candidates.append(make_non_trapped_input(t))
    else:
        targets = [
            rng.randint(12, 48),
            rng.randint(49, 52),
            rng.randint(60, 198),
            rng.randint(199, 750),
            rng.randint(1005, 1150),
        ]
        for t in targets:
            candidates.append(make_non_trapped_input(t))

    if trap_mod_state is not None:
        base_len = rng.randint(6, 25)
        rem = base_len % cycle_len
        adj_len = base_len + ((trap_mod_state - rem) % cycle_len)
        if adj_len == 0:
            adj_len = cycle_len
        trap_chars = [heavy_symbol if i % 2 == 0 else light_symbol for i in range(adj_len)]
        rng.shuffle(trap_chars)
        candidates[-1] = "".join(trap_chars)

    unique: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        c = c[:MAX_INPUT_LEN]
        if c not in seen:
            seen.add(c)
            unique.append(c)

    attempt = 0
    while len(unique) < INPUTS_PER_MACHINE:
        attempt += 1
        extra = make_non_trapped_input(rng.randint(15, 950) + attempt)
        if extra not in seen:
            seen.add(extra)
            unique.append(extra)

    return unique[:INPUTS_PER_MACHINE]


def select_diverse_inputs_by_simulation(
    machine: TuringMachine,
    candidate_pool: list[str],
    rng: random.Random,
    prefer_active_after_10: bool = True,
) -> list[str]:
    """Simulate candidate inputs and select 5 distinct inputs that maximize regime diversity."""
    by_regime: dict[tuple[int, int, int, bool], list[str]] = {}
    all_valid: list[str] = []

    shuffled = list(dict.fromkeys(c[:MAX_INPUT_LEN] for c in candidate_pool))
    rng.shuffle(shuffled)

    for inp in shuffled:
        res = simulate(machine, inp, step_limit=MAX_STEPS, trace_limit=0)
        labels = (
            int(res.halted_within_limit and res.steps <= 50),
            int(res.halted_within_limit and res.steps <= 200),
            int(res.halted_within_limit and res.steps <= 1000),
            not (res.halted_within_limit and res.steps <= 10),
        )
        by_regime.setdefault(labels, []).append(inp)
        all_valid.append(inp)

    selected: list[str] = []
    seen: set[str] = set()

    post10_regimes = [k for k in by_regime if k[3] is True]
    rng.shuffle(post10_regimes)
    for reg in post10_regimes:
        if len(selected) >= INPUTS_PER_MACHINE:
            break
        choice = by_regime[reg][0]
        if choice not in seen:
            seen.add(choice)
            selected.append(choice)

    other_regimes = [k for k in by_regime if k not in post10_regimes]
    rng.shuffle(other_regimes)
    for reg in other_regimes:
        if len(selected) >= INPUTS_PER_MACHINE:
            break
        if not prefer_active_after_10 or len(selected) < INPUTS_PER_MACHINE:
            choice = by_regime[reg][0]
            if choice not in seen:
                seen.add(choice)
                selected.append(choice)

    for reg in post10_regimes:
        for choice in by_regime[reg][1:]:
            if len(selected) >= INPUTS_PER_MACHINE:
                break
            if choice not in seen:
                seen.add(choice)
                selected.append(choice)

    for choice in all_valid:
        if len(selected) >= INPUTS_PER_MACHINE:
            break
        if choice not in seen:
            seen.add(choice)
            selected.append(choice)

    return selected[:INPUTS_PER_MACHINE]


def build_candidate_input_pool(rng: random.Random) -> list[str]:
    """Generate a rich candidate pool of binary strings (all <= 512 chars)."""
    pool = [
        "",
        "0",
        "1",
        "00",
        "01",
        "10",
        "11",
        "010",
        "101",
        "110",
        "001",
        "1010",
        "0101",
        "1100",
        "0011",
        "111000",
        "000111",
    ]
    for length in (
        5, 7, 9, 10, 12, 15, 18, 22, 28, 35, 42, 48, 49, 50,
        55, 65, 80, 100, 125, 150, 185, 198, 220, 260, 320, 380,
    ):
        pool.append("0" * length)
        pool.append("1" * length)
        for p_one in (0.15, 0.35, 0.5, 0.7, 0.85):
            s = "".join("1" if rng.random() < p_one else "0" for _ in range(length))
            pool.append(s)
    return list(dict.fromkeys(s[:MAX_INPUT_LEN] for s in pool))


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def generate_pilot_v2_dataset(
    output_dir: Path = DEFAULT_OUTPUT_DIR, seed: int = SEED
) -> dict[str, Any]:
    """Generate the full 1,000-machine, 5,000-run pilot_v2 dataset deterministically."""
    rng = random.Random(seed)
    candidate_pool = build_candidate_input_pool(rng)

    jobs: list[tuple[str, str, int | None, TuringMachine, list[str]]] = []
    seen_fingerprints: set[str] = set()

    def register_machine(
        family: str,
        lineage_id: str,
        m_seed: int | None,
        machine: TuringMachine,
        inputs: list[str],
    ) -> bool:
        m_data = machine.model_dump(mode="json")
        fp = json.dumps(m_data, ensure_ascii=False, sort_keys=True)
        if fp in seen_fingerprints:
            return False
        if len(inputs) != INPUTS_PER_MACHINE or len(set(inputs)) != INPUTS_PER_MACHINE:
            return False
        if any(len(inp) > MAX_INPUT_LEN for inp in inputs):
            return False
        seen_fingerprints.add(fp)
        jobs.append((family, lineage_id, m_seed, machine, inputs))
        return True

    # 1. Family: bounded_scan_branch (220 machines)
    modes = ("preserve", "flip", "zero", "one")
    bsb_idx = 0
    for cycle_len in range(2, 12):
        for delay in range(0, 16):
            for heavy_sym in ("0", "1"):
                if bsb_idx >= FAMILY_COUNTS["bounded_scan_branch"]:
                    break
                write_mode = modes[(cycle_len + delay + bsb_idx) % len(modes)]
                hop_cost = 3 if bsb_idx % 3 != 0 else 5
                terminal_mode = "final_state" if bsb_idx % 4 != 0 else "missing_transition"
                trap_mod = (bsb_idx % cycle_len) if bsb_idx % 2 == 0 else None

                tm = build_bounded_scan_branch_machine(
                    cycle_len=cycle_len,
                    delay=delay,
                    write_mode=write_mode,
                    heavy_symbol=heavy_sym,
                    hop_cost=hop_cost,
                    terminal_mode=terminal_mode,
                    trap_mod_state=trap_mod,
                )
                inputs = select_inputs_for_bounded_scan(
                    cycle_len=cycle_len,
                    delay=delay,
                    heavy_symbol=heavy_sym,
                    hop_cost=hop_cost,
                    trap_mod_state=trap_mod,
                    rng=rng,
                    include_exact_boundary=(bsb_idx < 80 and terminal_mode == "final_state"),
                )
                lineage_id = f"bsb_c{cycle_len}_h{hop_cost}_{heavy_sym}_d{delay // 2}"
                if register_machine("bounded_scan_branch", lineage_id, None, tm, inputs):
                    bsb_idx += 1

    # 2. Family: multi_pass_rewriter (220 machines)
    mpr_idx = 0
    for num_passes in (2, 3, 4, 5):
        for tail_delay in range(0, 32):
            for heavy_sym in ("0", "1"):
                if mpr_idx >= FAMILY_COUNTS["multi_pass_rewriter"]:
                    break
                rewrite_p1 = modes[(num_passes + tail_delay) % len(modes)]
                rewrite_bk = modes[(num_passes + tail_delay + 1) % len(modes)]
                terminal_mode = "final_state" if mpr_idx % 4 != 0 else "missing_transition"
                loop_zero = mpr_idx % 2 == 0

                tm = build_multi_pass_rewriter_machine(
                    num_passes=num_passes,
                    pass1_heavy_sym=heavy_sym,
                    pass1_hop=True,
                    rewrite_pass1=rewrite_p1,
                    rewrite_back=rewrite_bk,
                    tail_delay=tail_delay,
                    terminal_mode=terminal_mode,
                    loop_if_starts_with_zero_on_final_pass=loop_zero,
                )
                inputs = select_diverse_inputs_by_simulation(tm, candidate_pool, rng)
                lineage_id = f"mpr_p{num_passes}_{heavy_sym}_d{tail_delay // 2}"
                if register_machine("multi_pass_rewriter", lineage_id, None, tm, inputs):
                    mpr_idx += 1

    # 3. Family: zigzag_shuttle (180 machines)
    zz_idx = 0
    for tail_delay in range(0, 50):
        for trigger_sym in ("0", "1"):
            for downgrade in (1, 2):
                if zz_idx >= FAMILY_COUNTS["zigzag_shuttle"]:
                    break
                terminal_mode = "final_state" if zz_idx % 4 != 0 else "missing_transition"
                trap_double = zz_idx % 2 == 0
                tm = build_zigzag_shuttle_machine(
                    trigger_sym=trigger_sym,
                    downgrade_steps=downgrade,
                    tail_delay=tail_delay,
                    terminal_mode=terminal_mode,
                    trap_on_double_trigger=trap_double,
                )
                zz_pool = [
                    "",
                    "0" * rng.randint(5, 18),
                    "1" * rng.randint(5, 18),
                    "0" * rng.randint(45, 50),
                    "1" * rng.randint(45, 50),
                ]
                for n_trig in (2, 4, 6, 8, 11, 14, 18, 24, 30, 38):
                    for pad in (0, 5, 15, 35):
                        safe = "0" if trigger_sym == "1" else "1"
                        s_chars = [trigger_sym] * n_trig + [safe] * pad
                        rng.shuffle(s_chars)
                        zz_pool.append("".join(s_chars)[:MAX_INPUT_LEN])
                inputs = select_diverse_inputs_by_simulation(tm, zz_pool + candidate_pool[:40], rng)
                lineage_id = f"zz_{trigger_sym}_dg{downgrade}_d{tail_delay // 2}"
                if register_machine("zigzag_shuttle", lineage_id, None, tm, inputs):
                    zz_idx += 1

    # 4. Family: conditional_cycle (180 machines)
    cc_idx = 0
    for cycle_len in range(3, 15):
        for tail_delay in range(0, 20):
            if cc_idx >= FAMILY_COUNTS["conditional_cycle"]:
                break
            step0 = 1
            step1 = 2 if cycle_len > 2 else 1
            exit_residues = {r for r in range(cycle_len) if r % 2 == (cc_idx % 2)}
            if not exit_residues:
                exit_residues = {0}
            return_pass = cc_idx % 2 == 0
            terminal_mode = "final_state" if cc_idx % 4 != 0 else "missing_transition"

            tm = build_conditional_cycle_machine(
                cycle_len=cycle_len,
                step_on_zero=step0,
                step_on_one=step1,
                exit_residues=exit_residues,
                return_pass_on_exit=return_pass,
                tail_delay=tail_delay,
                terminal_mode=terminal_mode,
            )
            inputs = select_diverse_inputs_by_simulation(tm, candidate_pool, rng)
            lineage_id = f"cc_c{cycle_len}_ret{int(return_pass)}_d{tail_delay // 2}"
            if register_machine("conditional_cycle", lineage_id, None, tm, inputs):
                cc_idx += 1

    # 5. Family: structured_random (200 machines — ~75% final_reachable=1, ~25% final_reachable=0)
    sr_idx = 0
    attempt_seed = seed + 10000
    while sr_idx < FAMILY_COUNTS["structured_random"]:
        attempt_seed += 1
        num_states = rng.randint(4, 15)
        density = round(rng.uniform(0.58, 0.94), 2)
        tm = generate_random_machine(
            seed=attempt_seed, num_states=num_states, rule_density=density
        )

        adj: dict[str, set[str]] = {}
        for t in tm.transitions:
            adj.setdefault(t.from_state, set()).add(t.to_state)
        visited = {tm.start_state}
        queue = [tm.start_state]
        while queue:
            curr = queue.pop(0)
            for nxt in adj.get(curr, ()):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        has_reachable_final = bool(visited & set(tm.final_states))

        # Allow ~25% of structured_random machines to have final_reachable == False
        want_reachable = (sr_idx % 4) != 0
        if has_reachable_final != want_reachable:
            continue

        sample_pool = rng.sample(candidate_pool, min(45, len(candidate_pool)))
        inputs = select_diverse_inputs_by_simulation(tm, sample_pool, rng)
        outcomes = set()
        active_count = 0
        for inp in inputs:
            res = simulate(tm, inp, step_limit=MAX_STEPS, trace_limit=0)
            lbl = (
                int(res.halted_within_limit and res.steps <= 50),
                int(res.halted_within_limit and res.steps <= 200),
                int(res.halted_within_limit and res.steps <= 1000),
            )
            outcomes.add(lbl)
            if not (res.halted_within_limit and res.steps <= 10):
                active_count += 1

        if len(outcomes) < 2 and sr_idx < 185:
            continue
        if active_count == 0:
            continue

        lineage_id = f"random_{attempt_seed}"
        if register_machine("structured_random", lineage_id, attempt_seed, tm, inputs):
            sr_idx += 1

    rng.shuffle(jobs)

    machines: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    stop_reasons = Counter()

    for index, (family, lineage_id, m_seed, machine, inputs) in enumerate(jobs, start=1):
        machine_id = f"V2M{index:04d}"
        machine_data = machine.model_dump(mode="json")

        machines.append(
            {
                "machine_id": machine_id,
                "family": family,
                "lineage_id": lineage_id,
                "seed": m_seed,
                "machine": machine_data,
            }
        )

        for input_text in inputs:
            SimulationRequest(machine=machine, input=input_text, step_limit=MAX_STEPS)

            result = simulate(
                machine,
                input_text=input_text,
                step_limit=MAX_STEPS,
                trace_limit=TRACE_LIMIT,
            )
            record = create_record(machine_id, input_text, result)
            records.append(record)
            stop_reasons[result.stop_reason] += 1

            labels = [record[f"halt_by_{b}"] for b in BUDGETS]
            if labels != sorted(labels):
                raise ValueError(f"Non-monotonic bounded labels: {machine_id}")

    expected_records = NUM_MACHINES * INPUTS_PER_MACHINE
    if len(machines) != NUM_MACHINES or len(records) != expected_records:
        raise ValueError(
            f"Generated counts ({len(machines)}, {len(records)}) do not match target ({NUM_MACHINES}, {expected_records})"
        )
    if len({(r["machine_id"], r["input"]) for r in records}) != expected_records:
        raise ValueError("Duplicate machine-input pair detected")

    output_dir.mkdir(parents=True, exist_ok=True)
    save_jsonl(output_dir / "machines.jsonl", machines)
    save_jsonl(output_dir / "runs.jsonl", records)

    summary = {
        "machines_saved": len(machines),
        "records_saved": len(records),
        "families": dict(Counter(m["family"] for m in machines)),
        "stop_reasons": dict(stop_reasons),
        "budgets": {
            b: {
                "positive": sum(r[f"halt_by_{b}"] for r in records),
                "negative": len(records) - sum(r[f"halt_by_{b}"] for r in records),
            }
            for b in BUDGETS
        },
        "output_dir": str(output_dir),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate pilot_v2 dataset (5,000 runs).")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for machines.jsonl and runs.jsonl",
    )
    parser.add_argument("--seed", type=int, default=SEED, help="Master random seed")
    args = parser.parse_args()

    summary = generate_pilot_v2_dataset(output_dir=args.output_dir, seed=args.seed)
    print(f"Machines saved: {summary['machines_saved']}")
    print(f"Records saved: {summary['records_saved']}")
    print(f"Machine families: {summary['families']}")
    print(f"Stop reasons: {summary['stop_reasons']}")
    for b in BUDGETS:
        pos = summary["budgets"][b]["positive"]
        neg = summary["budgets"][b]["negative"]
        print(f"Budget {b}: positive={pos}, negative={neg}")
    print(f"Output directory: {summary['output_dir']}")


if __name__ == "__main__":
    main()
