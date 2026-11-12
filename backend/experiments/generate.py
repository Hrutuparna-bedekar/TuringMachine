"""Deterministic dataset generator for Turing Machine halting prediction.

Generates diverse machines across 5 behavioral families, executes simulations using
the shared simulator up to 1000 steps (with trace_limit=10 for prefix features),
computes ground-truth bounded labels, extracts features, and saves structured artifacts.
"""

import argparse
import json
from hashlib import sha256
import os
import random
import time
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.features import ALL_FEATURE_NAMES, extract_features
from backend.app.schemas import State, Transition, TuringMachine
from backend.app.simulator import simulate


def create_state(sid: str, name: str) -> State:
    return State(id=sid, name=name)


def create_transition(
    from_state: str, read: str, to_state: str, write: str, move: str
) -> Transition:
    return Transition(
        from_state=from_state,
        read=read,
        to_state=to_state,
        write=write,
        move=move,
    )


def generate_random_table_machine(rng: random.Random, mid: str, lineage: str) -> TuringMachine:
    """Generate a random rule table with varied density and states."""
    num_states = rng.randint(2, 5)
    states = [create_state(f"q{i}", f"State_{i}") for i in range(num_states)]
    has_final = rng.random() > 0.3
    final_states = [f"q{num_states - 1}"] if has_final else []

    tape_alphabet = ["0", "1", "B"]
    input_alphabet = ["0", "1"]
    non_final_ids = [s.id for s in states if s.id not in final_states]

    density = rng.uniform(0.3, 0.85)
    transitions: list[Transition] = []

    for sid in non_final_ids:
        for sym in tape_alphabet:
            if rng.random() < density:
                target_state = rng.choice([s.id for s in states])
                write_sym = rng.choice(tape_alphabet)
                move_dir = rng.choice(["L", "R"])
                transitions.append(
                    create_transition(sid, sym, target_state, write_sym, move_dir)
                )

    return TuringMachine(
        states=states,
        input_alphabet=input_alphabet,
        tape_alphabet=tape_alphabet,
        blank_symbol="B",
        start_state="q0",
        final_states=final_states,
        transitions=transitions,
    )


def generate_scan_rewrite_machine(rng: random.Random, mid: str, lineage: str) -> TuringMachine:
    """Machines that scan the tape, rewrite symbols, and halt upon reaching a blank.
    
    Includes single-pass, two-pass, and multi-sweep variants to produce halt steps
    naturally distributed across 10..50, 50..200, and 200..1000 steps.
    """
    mode = rng.choice(["replace", "erase", "invert", "scan_to_end", "two_pass_rewrite", "four_pass_sweep"])
    tape_alphabet = ["0", "1", "B"]
    input_alphabet = ["0", "1"]
    transitions: list[Transition] = []

    if mode == "replace":
        states = [create_state("q_scan", "Scanning"), create_state("q_halt", "Halted")]
        transitions.append(create_transition("q_scan", "0", "q_scan", "1", "R"))
        transitions.append(create_transition("q_scan", "1", "q_scan", "0", "R"))
        transitions.append(create_transition("q_scan", "B", "q_halt", "B", "R"))
    elif mode == "erase":
        states = [create_state("q_scan", "Scanning"), create_state("q_halt", "Halted")]
        transitions.append(create_transition("q_scan", "0", "q_scan", "B", "R"))
        transitions.append(create_transition("q_scan", "1", "q_scan", "B", "R"))
        transitions.append(create_transition("q_scan", "B", "q_halt", "B", "L"))
    elif mode == "invert":
        states = [create_state("q_scan", "Scanning"), create_state("q_halt", "Halted")]
        transitions.append(create_transition("q_scan", "0", "q_scan", "1", "R"))
        transitions.append(create_transition("q_scan", "1", "q_scan", "1", "R"))
        transitions.append(create_transition("q_scan", "B", "q_halt", "B", "R"))
    elif mode == "two_pass_rewrite":
        # Pass 1: scan R, rewrite 0->1. Pass 2: scan L, verify 1s, then halt on B
        states = [
            create_state("q_fwd", "Forward"),
            create_state("q_rev", "Reverse"),
            create_state("q_halt", "Halted"),
        ]
        transitions.append(create_transition("q_fwd", "0", "q_fwd", "1", "R"))
        transitions.append(create_transition("q_fwd", "1", "q_fwd", "1", "R"))
        transitions.append(create_transition("q_fwd", "B", "q_rev", "B", "L"))
        transitions.append(create_transition("q_rev", "1", "q_rev", "1", "L"))
        transitions.append(create_transition("q_rev", "0", "q_rev", "0", "L"))
        transitions.append(create_transition("q_rev", "B", "q_halt", "B", "R"))
    elif mode == "four_pass_sweep":
        # 4 consecutive passes back and forth across input
        states = [
            create_state("q_p1", "Pass1"),
            create_state("q_p2", "Pass2"),
            create_state("q_p3", "Pass3"),
            create_state("q_p4", "Pass4"),
            create_state("q_halt", "Halted"),
        ]
        transitions.append(create_transition("q_p1", "0", "q_p1", "0", "R"))
        transitions.append(create_transition("q_p1", "1", "q_p1", "1", "R"))
        transitions.append(create_transition("q_p1", "B", "q_p2", "B", "L"))

        transitions.append(create_transition("q_p2", "0", "q_p2", "0", "L"))
        transitions.append(create_transition("q_p2", "1", "q_p2", "1", "L"))
        transitions.append(create_transition("q_p2", "B", "q_p3", "B", "R"))

        transitions.append(create_transition("q_p3", "0", "q_p3", "1", "R"))
        transitions.append(create_transition("q_p3", "1", "q_p3", "0", "R"))
        transitions.append(create_transition("q_p3", "B", "q_p4", "B", "L"))

        transitions.append(create_transition("q_p4", "0", "q_p4", "0", "L"))
        transitions.append(create_transition("q_p4", "1", "q_p4", "1", "L"))
        transitions.append(create_transition("q_p4", "B", "q_halt", "B", "R"))
    else:  # scan_to_end
        states = [create_state("q_scan", "Scanning"), create_state("q_halt", "Halted")]
        transitions.append(create_transition("q_scan", "0", "q_scan", "0", "R"))
        transitions.append(create_transition("q_scan", "1", "q_scan", "1", "R"))
        transitions.append(create_transition("q_scan", "B", "q_halt", "B", "R"))

    return TuringMachine(
        states=states,
        input_alphabet=input_alphabet,
        tape_alphabet=tape_alphabet,
        blank_symbol="B",
        start_state=states[0].id,
        final_states=["q_halt"],
        transitions=transitions,
    )


def generate_input_dependent_machine(rng: random.Random, mid: str, lineage: str) -> TuringMachine:
    """Machines whose halting behavior or steps strictly depend on the input symbols."""
    behavior = rng.choice(["parity", "has_one", "prefix_match"])
    states = [
        create_state("q0", "Start"),
        create_state("q1", "State1"),
        create_state("q_halt", "Halt"),
    ]
    tape_alphabet = ["0", "1", "B"]
    input_alphabet = ["0", "1"]
    transitions: list[Transition] = []

    if behavior == "parity":
        # Even number of 1s halts; odd number of 1s loops on blank
        transitions.append(create_transition("q0", "0", "q0", "0", "R"))
        transitions.append(create_transition("q0", "1", "q1", "1", "R"))
        transitions.append(create_transition("q0", "B", "q_halt", "B", "R"))

        transitions.append(create_transition("q1", "0", "q1", "0", "R"))
        transitions.append(create_transition("q1", "1", "q0", "1", "R"))
        # on B in q1, loops forever moving R
        transitions.append(create_transition("q1", "B", "q1", "B", "R"))

    elif behavior == "has_one":
        # Halts if '1' is present, loops if only '0's
        transitions.append(create_transition("q0", "1", "q_halt", "1", "R"))
        transitions.append(create_transition("q0", "0", "q0", "0", "R"))
        # on B in q0, loops
        transitions.append(create_transition("q0", "B", "q0", "B", "R"))

    else:  # prefix_match
        # If starts with '1', replaces with '0' and halts; if starts with '0', loops left
        transitions.append(create_transition("q0", "1", "q_halt", "0", "R"))
        transitions.append(create_transition("q0", "0", "q1", "0", "L"))
        transitions.append(create_transition("q0", "B", "q_halt", "B", "R"))
        transitions.append(create_transition("q1", "B", "q1", "B", "L"))
        transitions.append(create_transition("q1", "0", "q1", "0", "L"))

    return TuringMachine(
        states=states,
        input_alphabet=input_alphabet,
        tape_alphabet=tape_alphabet,
        blank_symbol="B",
        start_state="q0",
        final_states=["q_halt"],
        transitions=transitions,
    )


def generate_delayed_halt_machine(rng: random.Random, mid: str, lineage: str) -> TuringMachine:
    """Machines designed with shuttle bounces or multi-pass sweeps to halt between 30 and 800 steps."""
    sweep_type = rng.choice(["bounce_erase", "double_scan", "counter_decrement"])
    tape_alphabet = ["0", "1", "B"]
    input_alphabet = ["0", "1"]

    if sweep_type == "bounce_erase":
        # Scans right, finds last symbol, erases it, bounces left to start, repeats until tape is blank
        states = [
            create_state("q_right", "SeekRight"),
            create_state("q_erase", "EraseEnd"),
            create_state("q_left", "ReturnLeft"),
            create_state("q_halt", "Halt"),
        ]
        transitions = [
            # Move right to blank
            create_transition("q_right", "0", "q_right", "0", "R"),
            create_transition("q_right", "1", "q_right", "1", "R"),
            create_transition("q_right", "B", "q_erase", "B", "L"),
            # In erase state:
            create_transition("q_erase", "0", "q_left", "B", "L"),
            create_transition("q_erase", "1", "q_left", "B", "L"),
            create_transition("q_erase", "B", "q_halt", "B", "R"),  # all erased!
            # Move left to blank
            create_transition("q_left", "0", "q_left", "0", "L"),
            create_transition("q_left", "1", "q_left", "1", "L"),
            create_transition("q_left", "B", "q_right", "B", "R"),
        ]
    elif sweep_type == "double_scan":
        # Pass 1: scan right changing 0->1. Pass 2: scan left changing 1->0. Pass 3: halt.
        states = [
            create_state("q_pass1", "Pass1"),
            create_state("q_pass2", "Pass2"),
            create_state("q_pass3", "Pass3"),
            create_state("q_halt", "Halt"),
        ]
        transitions = [
            create_transition("q_pass1", "0", "q_pass1", "1", "R"),
            create_transition("q_pass1", "1", "q_pass1", "1", "R"),
            create_transition("q_pass1", "B", "q_pass2", "B", "L"),
            create_transition("q_pass2", "1", "q_pass2", "0", "L"),
            create_transition("q_pass2", "0", "q_pass2", "0", "L"),
            create_transition("q_pass2", "B", "q_pass3", "B", "R"),
            create_transition("q_pass3", "0", "q_pass3", "0", "R"),
            create_transition("q_pass3", "B", "q_halt", "B", "R"),
        ]
    else:  # counter_decrement
        # Shuttle bouncing between two markers
        states = [
            create_state("q_fwd", "Forward"),
            create_state("q_bwd", "Backward"),
            create_state("q_check", "Check"),
            create_state("q_halt", "Halt"),
        ]
        transitions = [
            create_transition("q_fwd", "0", "q_fwd", "0", "R"),
            create_transition("q_fwd", "1", "q_fwd", "0", "R"),
            create_transition("q_fwd", "B", "q_bwd", "B", "L"),
            create_transition("q_bwd", "0", "q_bwd", "0", "L"),
            create_transition("q_bwd", "B", "q_check", "B", "R"),
            create_transition("q_check", "0", "q_halt", "0", "R"),
            create_transition("q_check", "B", "q_halt", "B", "R"),
        ]

    return TuringMachine(
        states=states,
        input_alphabet=input_alphabet,
        tape_alphabet=tape_alphabet,
        blank_symbol="B",
        start_state=states[0].id,
        final_states=["q_halt"],
        transitions=transitions,
    )


def generate_long_running_machine(rng: random.Random, mid: str, lineage: str) -> TuringMachine:
    """Machines guaranteed or heavily predisposed to run past 1000 steps."""
    loop_type = rng.choice(["infinite_right", "infinite_left", "ping_pong_loop", "cyclical_2state"])
    tape_alphabet = ["0", "1", "B"]
    input_alphabet = ["0", "1"]

    if loop_type == "infinite_right":
        states = [create_state("q_run", "Runner")]
        transitions = [
            create_transition("q_run", "0", "q_run", "0", "R"),
            create_transition("q_run", "1", "q_run", "1", "R"),
            create_transition("q_run", "B", "q_run", "B", "R"),
        ]
    elif loop_type == "infinite_left":
        states = [create_state("q_run", "LeftRunner")]
        transitions = [
            create_transition("q_run", "0", "q_run", "0", "L"),
            create_transition("q_run", "1", "q_run", "1", "L"),
            create_transition("q_run", "B", "q_run", "B", "L"),
        ]
    elif loop_type == "ping_pong_loop":
        states = [
            create_state("q_right", "PingRight"),
            create_state("q_left", "PingLeft"),
        ]
        transitions = [
            create_transition("q_right", "0", "q_right", "0", "R"),
            create_transition("q_right", "1", "q_right", "1", "R"),
            create_transition("q_right", "B", "q_left", "B", "L"),
            create_transition("q_left", "0", "q_left", "0", "L"),
            create_transition("q_left", "1", "q_left", "1", "L"),
            create_transition("q_left", "B", "q_right", "B", "R"),
        ]
    else:  # cyclical_2state
        states = [
            create_state("q_a", "StateA"),
            create_state("q_b", "StateB"),
        ]
        transitions = [
            create_transition("q_a", "0", "q_b", "1", "R"),
            create_transition("q_a", "1", "q_b", "0", "R"),
            create_transition("q_a", "B", "q_b", "1", "R"),
            create_transition("q_b", "0", "q_a", "1", "L"),
            create_transition("q_b", "1", "q_a", "0", "L"),
            create_transition("q_b", "B", "q_a", "1", "L"),
        ]

    return TuringMachine(
        states=states,
        input_alphabet=input_alphabet,
        tape_alphabet=tape_alphabet,
        blank_symbol="B",
        start_state=states[0].id,
        final_states=[],
        transitions=transitions,
    )


def generate_inputs_for_machine(rng: random.Random, family: str, count: int = 5) -> list[str]:
    """Generate diverse inputs of varying lengths and symbol distributions."""
    inputs: list[str] = [""]  # empty string is always checked

    short_candidates = ["0", "1", "00", "01", "10", "11", "010", "101", "111"]
    inputs.append(rng.choice(short_candidates))

    # Length 10..30 (exercises step 10..50)
    medium_len = rng.randint(10, 30)
    inputs.append("".join(rng.choice(["0", "1"]) for _ in range(medium_len)))

    # Length 45..90 (exercises step 50..200 on multi-pass)
    longer_len = rng.randint(45, 90)
    if rng.random() > 0.5:
        inputs.append("01" * (longer_len // 2))
    else:
        inputs.append("".join(rng.choice(["0", "1"]) for _ in range(longer_len)))

    # Length 100..220 (exercises step 200..1000 on multi-pass)
    deep_len = rng.randint(100, 220)
    inputs.append("".join(rng.choice(["0", "1"]) for _ in range(deep_len)))

    # Deduplicate while preserving order, pad if needed
    seen: set[str] = set()
    deduped: list[str] = []
    for inp in inputs:
        if inp not in seen:
            seen.add(inp)
            deduped.append(inp)

    while len(deduped) < count:
        extra = "".join(rng.choice(["0", "1"]) for _ in range(rng.randint(5, 50)))
        if extra not in seen:
            seen.add(extra)
            deduped.append(extra)

    return deduped[:count]


def machine_fingerprint(machine: dict) -> str:
    """Identify matching machines independently of list order and display labels."""
    normalized = {
        **machine,
        "states": sorted(state["id"] for state in machine["states"]),
        "final_states": sorted(machine["final_states"]),
        "input_alphabet": sorted(machine["input_alphabet"]),
        "tape_alphabet": sorted(machine["tape_alphabet"]),
        "transitions": sorted(machine["transitions"], key=lambda rule: (rule["from_state"], rule["read"])),
    }
    return sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def run_generation(config_path: str, run_id: str, is_pilot: bool = False) -> Path:
    start_time = time.time()
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    seed = cfg.get("seed", 42)
    if is_pilot:
        seed += 1000  # separate seed for pilot
        total_machines = cfg.get("pilot_machines", 500)
    else:
        total_machines = cfg.get("final_machines", 2500)

    inputs_per_machine = cfg.get("inputs_per_machine", 5)
    rng = random.Random(seed)

    family_weights = cfg.get(
        "family_weights",
        {
            "random_tables": 0.25,
            "scans_rewrites": 0.25,
            "input_dependent": 0.20,
            "delayed_halts": 0.15,
            "long_running": 0.15,
        },
    )

    families = list(family_weights.keys())
    weights = [family_weights[f] for f in families]

    out_dir = Path("data") / "generated" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    machines_file = out_dir / "machines.jsonl"
    runs_file = out_dir / "runs.parquet"
    features_file = out_dir / "features.parquet"
    summary_file = out_dir / "summary.json"

    print(f"[{run_id}] Generating {total_machines} machines (approx {total_machines * inputs_per_machine} pairs)...")

    generators = {
        "random_tables": generate_random_table_machine,
        "scans_rewrites": generate_scan_rewrite_machine,
        "input_dependent": generate_input_dependent_machine,
        "delayed_halts": generate_delayed_halt_machine,
        "long_running": generate_long_running_machine,
    }

    runs_data: list[dict[str, Any]] = []
    features_data: list[dict[str, Any]] = []

    pair_counter = 0

    with open(machines_file, "w", encoding="utf-8") as m_f:
        for m_idx in range(total_machines):
            family = rng.choices(families, weights=weights, k=1)[0]
            machine_id = f"m_{m_idx:05d}"

            machine = generators[family](rng, machine_id, family)
            lineage_id = f"{family}_{machine_fingerprint(machine.model_dump())}"

            # Write machine record
            m_record = {
                "machine_id": machine_id,
                "family": family,
                "lineage_id": lineage_id,
                "seed": seed + m_idx,
                "machine": machine.model_dump(),
            }
            m_f.write(json.dumps(m_record) + "\n")

            # Generate inputs
            inputs = generate_inputs_for_machine(rng, family, count=inputs_per_machine)

            for inp in inputs:
                pair_counter += 1
                run_key = f"r_{pair_counter:07d}"

                # Run simulation up to 1000 steps with 10 trace events captured
                sim_res = simulate(machine, inp, step_limit=1000, trace_limit=10)

                if sim_res.halted_within_limit:
                    halt_step = sim_res.steps
                    halt_by_50 = 1 if halt_step <= 50 else 0
                    halt_by_200 = 1 if halt_step <= 200 else 0
                    halt_by_1000 = 1 if halt_step <= 1000 else 0
                else:
                    halt_step = None
                    halt_by_50 = 0
                    halt_by_200 = 0
                    halt_by_1000 = 0

                active_at_prefix = bool(halt_step is None or halt_step > 10)

                runs_data.append(
                    {
                        "run_id": run_key,
                        "machine_id": machine_id,
                        "family": family,
                        "lineage_id": lineage_id,
                        "input": inp,
                        "executed_steps": sim_res.steps,
                        "halt_step": halt_step,
                        "stop_reason": sim_res.stop_reason,
                        "halt_by_50": halt_by_50,
                        "halt_by_200": halt_by_200,
                        "halt_by_1000": halt_by_1000,
                        "active_at_prefix": active_at_prefix,
                    }
                )

                # Extract features using shared module
                feat_dict = extract_features(machine, inp, sim_res.trace)
                feat_dict["run_id"] = run_key
                features_data.append(feat_dict)

    # Save to Parquet
    runs_df = pd.DataFrame(runs_data)
    runs_df.to_parquet(runs_file, index=False)

    features_df = pd.DataFrame(features_data)
    # Ensure run_id is first column
    cols = ["run_id"] + [c for c in ALL_FEATURE_NAMES if c in features_df.columns]
    features_df = features_df[cols]
    features_df.to_parquet(features_file, index=False)

    elapsed = time.time() - start_time

    summary = {
        "run_id": run_id,
        "is_pilot": is_pilot,
        "seed": seed,
        "total_machines": total_machines,
        "total_runs": len(runs_df),
        "runtime_seconds": round(elapsed, 2),
        "class_counts_all": {
            "halt_by_50": runs_df["halt_by_50"].value_counts().to_dict(),
            "halt_by_200": runs_df["halt_by_200"].value_counts().to_dict(),
            "halt_by_1000": runs_df["halt_by_1000"].value_counts().to_dict(),
        },
        "active_at_prefix_count": int(runs_df["active_at_prefix"].sum()),
        "class_counts_active_at_prefix": {
            "halt_by_50": runs_df[runs_df["active_at_prefix"]]["halt_by_50"].value_counts().to_dict(),
            "halt_by_200": runs_df[runs_df["active_at_prefix"]]["halt_by_200"].value_counts().to_dict(),
            "halt_by_1000": runs_df[runs_df["active_at_prefix"]]["halt_by_1000"].value_counts().to_dict(),
        },
        "family_counts": runs_df["family"].value_counts().to_dict(),
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[{run_id}] Finished in {elapsed:.2f}s! Total pairs: {len(runs_df)}.")
    print(f"[{run_id}] Active at prefix (>10 steps): {summary['active_at_prefix_count']}")
    print(f"[{run_id}] Class balance for still-active at prefix:")
    for b in [50, 200, 1000]:
        print(f"    halt_by_{b}: {summary['class_counts_active_at_prefix'][f'halt_by_{b}']}")

    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Generate labeled Turing Machine dataset.")
    parser.add_argument(
        "--config",
        default="backend/experiments/config.json",
        help="Path to generator configuration JSON.",
    )
    parser.add_argument("--run-id", default="pilot", help="Identifier for output directory.")
    parser.add_argument("--pilot", action="store_true", help="Generate smaller pilot batch.")
    args = parser.parse_args()

    run_generation(args.config, args.run_id, is_pilot=args.pilot or (args.run_id == "pilot"))


if __name__ == "__main__":
    main()
