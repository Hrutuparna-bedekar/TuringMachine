"""Reproducible pilot dataset for bounded Turing-machine halting prediction.

Run from the repository's 'Yashraj Part' directory:
    python -m backend.experiments.generate_pilot

Only machine definitions, inputs, and the first 10 trace steps may be used as
ML features. Full-run outcomes in runs.jsonl are labels/diagnostics, NOT features.
"""

import json
import random
from collections import Counter
from pathlib import Path

from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate
from backend.experiments.generate_v1_proto import create_record
from backend.experiments.machine_generators import generate_random_machine

SEED = 2026
RANDOM_COUNT = 225
SCAN_COUNT = 175
LOOP_COUNT = 100
NUM_MACHINES = RANDOM_COUNT + SCAN_COUNT + LOOP_COUNT
INPUTS_PER_MACHINE = 5
BUDGETS = (50, 200, 1000)
MAX_STEPS = 1000
TRACE_LIMIT = 10
OUTPUT_DIR = Path("data/generated/pilot_v1")
SYMBOLS = ("0", "1", "□")


def state(state_id):
    return {"id": state_id, "name": state_id}


def transition(source, read, target, write, direction="R"):
    return {
        "from_state": source,
        "read": read,
        "to_state": target,
        "write": write,
        "move": direction,
    }


def rewrite_symbol(symbol, mode):
    """Vary tape-writing behavior without changing the machine alphabet."""
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
    raise ValueError(f"Unknown writing mode: {mode}")


def generate_scan_variant(cycle_length, delay, write_mode):
    """Scan right to first blank, then take 'delay' additional steps to halt.

    On an input of length n, the halt step is n + 1 + delay.
    Cycling scan states and writing modes create distinct machine definitions.
    """
    scan_ids = [f"scan_{i}" for i in range(cycle_length)]
    tail_ids = [f"tail_{i}" for i in range(delay)]
    halt_id = "qhalt"
    transitions = []

    for i, source in enumerate(scan_ids):
        next_scan = scan_ids[(i + 1) % cycle_length]
        for symbol in ("0", "1"):
            transitions.append(
                transition(source, symbol, next_scan, rewrite_symbol(symbol, write_mode))
            )
        transitions.append(
            transition(source, "□", tail_ids[0] if tail_ids else halt_id, "□")
        )

    for i, source in enumerate(tail_ids):
        next_state = tail_ids[i + 1] if i + 1 < len(tail_ids) else halt_id
        transitions.append(transition(source, "□", next_state, "□"))

    return TuringMachine.model_validate(
        {
            "states": [state(s) for s in (*scan_ids, *tail_ids, halt_id)],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": scan_ids[0],
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def generate_cycle_variant(cycle_length, direction, write_mode):
    """Total transition table whose final state is unreachable.

    These runs reach the configured step budget; this does not constitute a
    general mathematical proof of non-halting for arbitrary machines.
    """
    cycle_ids = [f"q{i}" for i in range(cycle_length)]
    halt_id = "qhalt"
    transitions = []

    for i, source in enumerate(cycle_ids):
        next_state = cycle_ids[(i + 1) % cycle_length]
        for symbol in SYMBOLS:
            transitions.append(
                transition(
                    source,
                    symbol,
                    next_state,
                    rewrite_symbol(symbol, write_mode),
                    direction,
                )
            )

    return TuringMachine.model_validate(
        {
            "states": [state(s) for s in (*cycle_ids, halt_id)],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": list(SYMBOLS),
            "blank_symbol": "□",
            "start_state": cycle_ids[0],
            "final_states": [halt_id],
            "transitions": transitions,
        }
    )


def save_jsonl(path, rows):
    # Overwrite instead of append: rerunning with the same seed is idempotent.
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main():
    rng = random.Random(SEED)
    modes = ("preserve", "flip", "zero", "one")

    scan_options = [
        (cycle, delay, mode)
        for cycle in range(1, 11)
        for delay in range(6)
        for mode in modes
    ]
    loop_options = [
        (cycle, direction, mode)
        for cycle in range(2, 16)
        for direction in ("L", "R")
        for mode in modes
    ]

    # Sampling without replacement gives distinct configurations per family.
    jobs = [("random_rule_tables", SEED + i) for i in range(RANDOM_COUNT)]
    jobs += [("scan_delay", config) for config in rng.sample(scan_options, SCAN_COUNT)]
    jobs += [("cyclic_loop", config) for config in rng.sample(loop_options, LOOP_COUNT)]
    rng.shuffle(jobs)

    machines = []
    records = []
    seen_definitions = set()
    stop_reasons = Counter()

    random_input_pool = [
        "", "0", "1", "00", "11", "101", "111", "00101",
        "010101", "111000", "0" * 50, "1" * 200,
    ]

    for index, (family, config) in enumerate(jobs, start=1):
        machine_id = f"P{index:04d}"
        seed = None

        if family == "random_rule_tables":
            seed = config
            machine = generate_random_machine(
                seed=seed,
                num_states=rng.randint(3, 15),
                rule_density=round(rng.uniform(0.5, 1.0), 2),
            )
            lineage_id = f"random_{seed}"
            inputs = rng.sample(random_input_pool, INPUTS_PER_MACHINE)

        elif family == "scan_delay":
            cycle, delay, mode = config
            machine = generate_scan_variant(cycle, delay, mode)
            lineage_id = f"scan_cycle{cycle}_mode_{mode}"
            # Exact budget-boundary cases plus one short case.
            # Halt step = input length + 1 + delay.
            lengths = [rng.randint(0, 10), 49 - delay, 50 - delay, 200 - delay, 1000 - delay]
            inputs = ["1" * n for n in lengths]

        else:
            cycle, direction, mode = config
            machine = generate_cycle_variant(cycle, direction, mode)
            lineage_id = f"loop_cycle{cycle}_{direction}"
            inputs = rng.sample(random_input_pool, INPUTS_PER_MACHINE)

        machine_data = machine.model_dump(mode="json")
        fingerprint = json.dumps(machine_data, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen_definitions:
            raise ValueError(f"Duplicate machine definition: {machine_id}")
        seen_definitions.add(fingerprint)

        machines.append(
            {
                "machine_id": machine_id,
                "family": family,
                "lineage_id": lineage_id,
                "seed": seed,
                "machine": machine_data,
            }
        )

        if len(inputs) != INPUTS_PER_MACHINE or len(set(inputs)) != INPUTS_PER_MACHINE:
            raise ValueError(f"Expected five distinct inputs for {machine_id}")

        for input_text in inputs:
            result = simulate(
                machine,
                input_text=input_text,
                step_limit=MAX_STEPS,
                trace_limit=TRACE_LIMIT,
            )
            record = create_record(machine_id, input_text, result)
            records.append(record)
            stop_reasons[result.stop_reason] += 1

            labels = [record[f"halt_by_{budget}"] for budget in BUDGETS]
            if labels != sorted(labels):
                raise ValueError(f"Non-monotonic bounded labels: {machine_id}")

    expected_records = NUM_MACHINES * INPUTS_PER_MACHINE
    if len(machines) != NUM_MACHINES or len(records) != expected_records:
        raise ValueError("Generated record counts do not match target")
    if len({(r["machine_id"], r["input"]) for r in records}) != expected_records:
        raise ValueError("Duplicate machine-input pair detected")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_jsonl(OUTPUT_DIR / "machines.jsonl", machines)
    save_jsonl(OUTPUT_DIR / "runs.jsonl", records)

    print(f"Machines saved: {len(machines)}")
    print(f"Records saved: {len(records)}")
    print(f"Machine families: {dict(Counter(m['family'] for m in machines))}")
    print(f"Stop reasons: {dict(stop_reasons)}")
    for budget in BUDGETS:
        positives = sum(r[f"halt_by_{budget}"] for r in records)
        print(f"Budget {budget}: positive={positives}, negative={len(records) - positives}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
