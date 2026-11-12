"""Standalone reproducible data-quality audit for Turing Machine halting datasets.

Run from the 'Yashraj Part' directory:
    python -m backend.experiments.audit_pilot
    python -m backend.experiments.audit_pilot --data-dir data/generated/pilot_v1
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.app.schemas import SimulationRequest, State, Transition, TuringMachine
from backend.app.simulator import simulate

BUDGETS = (50, 200, 1000)
MAX_STEPS = 1000
PREFIX_STEPS = 10
BOUNDARY_STEPS = (0, 10, 11, 49, 50, 51, 199, 200, 201, 999, 1000)
BEHAVIORAL_PROBE_INPUTS = (
    "",
    "0",
    "1",
    "00",
    "01",
    "10",
    "11",
    "101",
    "0101",
    "111000",
    "1" * 15,
    "0" * 15,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_num} of {path}: {exc}") from exc
    return rows


def canonical_machine_fingerprint(machine_dict: dict[str, Any]) -> str:
    return json.dumps(machine_dict, ensure_ascii=False, sort_keys=True)


def structural_transition_signature(machine: TuringMachine) -> tuple[Any, ...]:
    """Graph-level signature independent of state naming where possible."""
    final_set = set(machine.final_states)
    out_degrees = Counter()
    self_loops = 0
    moves = Counter()
    writes_blank = 0
    writes_same = 0
    symbol_agnostic_states = 0

    by_state: dict[str, list[Transition]] = defaultdict(list)
    for t in machine.transitions:
        out_degrees[t.from_state] += 1
        by_state[t.from_state].append(t)
        if t.from_state == t.to_state:
            self_loops += 1
        moves[t.move] += 1
        if t.write == machine.blank_symbol:
            writes_blank += 1
        if t.write == t.read:
            writes_same += 1

    for state_id, rules in by_state.items():
        by_read = {r.read: (r.to_state, r.write, r.move) for r in rules}
        if "0" in by_read and "1" in by_read:
            if by_read["0"][0] == by_read["1"][0] and by_read["0"][2] == by_read["1"][2]:
                symbol_agnostic_states += 1

    non_final_states = len(machine.states) - len(final_set)
    return (
        len(machine.states),
        len(final_set),
        len(machine.transitions),
        self_loops,
        moves["L"],
        moves["R"],
        writes_blank,
        writes_same,
        symbol_agnostic_states,
        non_final_states,
    )


def behavioral_signature(machine: TuringMachine) -> tuple[tuple[str, int], ...]:
    """Evaluate machine on a fixed canonical input suite to detect behavioral clones."""
    sig = []
    for probe in BEHAVIORAL_PROBE_INPUTS:
        res = simulate(machine, probe, step_limit=250, trace_limit=0)
        sig.append((res.stop_reason, res.steps))
    return tuple(sig)


def compute_effective_sample_size(group_counts: dict[str, int] | Counter[str]) -> float:
    """Kish's effective number of clusters: (sum N_g)^2 / sum(N_g^2)."""
    counts = [c for c in group_counts.values() if c > 0]
    if not counts:
        return 0.0
    total = sum(counts)
    sum_sq = sum(c * c for c in counts)
    return round((total * total) / sum_sq, 2)


def verify_canonical_boundary_fixtures() -> dict[str, Any]:
    """Verify simulator and label semantics at exact transition boundaries T=0,50,51,200,201,1000."""
    scan_machine = TuringMachine(
        states=[State(id="q0", name="Scan"), State(id="qhalt", name="Halt")],
        input_alphabet=["0", "1"],
        tape_alphabet=["0", "1", "□"],
        blank_symbol="□",
        start_state="q0",
        final_states=["qhalt"],
        transitions=[
            Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
            Transition(from_state="q0", read="□", to_state="qhalt", write="□", move="R"),
        ],
    )
    immediate_halt_machine = TuringMachine(
        states=[State(id="qhalt", name="Halt")],
        input_alphabet=["0", "1"],
        tape_alphabet=["0", "1", "□"],
        blank_symbol="□",
        start_state="qhalt",
        final_states=["qhalt"],
        transitions=[],
    )

    probes = [
        ("T=0_final_state", immediate_halt_machine, "0", 0, "final_state", [1, 1, 1]),
        ("T=0_missing_transition", scan_machine, "0", 0, "missing_transition", [1, 1, 1]),
        ("T=50_exact_budget", scan_machine, "1" * 49, 50, "final_state", [1, 1, 1]),
        ("T=51_just_over_50", scan_machine, "1" * 50, 51, "final_state", [0, 1, 1]),
        ("T=200_exact_budget", scan_machine, "1" * 199, 200, "final_state", [0, 1, 1]),
        ("T=201_just_over_200", scan_machine, "1" * 200, 201, "final_state", [0, 0, 1]),
        ("T=1000_exact_halt", scan_machine, "1" * 999, 1000, "final_state", [0, 0, 1]),
        ("T=1000_step_limit", scan_machine, "1" * 1000, 1000, "step_limit", [0, 0, 0]),
    ]

    results = []
    all_passed = True
    for name, machine, inp, expected_steps, expected_reason, expected_labels in probes:
        res = simulate(machine, inp, step_limit=MAX_STEPS, trace_limit=PREFIX_STEPS)
        actual_labels = [
            int(res.halted_within_limit and res.steps <= b) for b in BUDGETS
        ]
        passed = (
            res.steps == expected_steps
            and res.stop_reason == expected_reason
            and actual_labels == expected_labels
        )
        if not passed:
            all_passed = False
        results.append(
            {
                "probe": name,
                "steps": res.steps,
                "stop_reason": res.stop_reason,
                "halted_within_limit": res.halted_within_limit,
                "labels": actual_labels,
                "passed": passed,
            }
        )

    return {"all_passed": all_passed, "probes": results}


def audit_dataset(data_dir: Path) -> dict[str, Any]:
    """Perform a comprehensive, deterministic audit of a generated dataset directory."""
    machines_path = data_dir / "machines.jsonl"
    runs_path = data_dir / "runs.jsonl"

    if not machines_path.exists():
        raise FileNotFoundError(f"Missing machines file: {machines_path}")
    if not runs_path.exists():
        raise FileNotFoundError(f"Missing runs file: {runs_path}")

    raw_machines = load_jsonl(machines_path)
    raw_runs = load_jsonl(runs_path)

    # 1. Machine ID, Schema, and Fingerprint Validation
    machine_id_counts = Counter()
    fingerprint_counts = Counter()
    schema_errors: list[dict[str, Any]] = []
    validated_machines: dict[str, TuringMachine] = {}
    machine_meta: dict[str, dict[str, Any]] = {}
    family_counts = Counter()
    lineage_counts = Counter()
    behavioral_groups: dict[tuple[tuple[str, int], ...], list[str]] = defaultdict(list)
    symbol_agnostic_machines = 0
    final_unreachable_machines = 0

    for idx, row in enumerate(raw_machines):
        mid = row.get("machine_id")
        if not isinstance(mid, str) or not mid:
            schema_errors.append({"index": idx, "error": "Missing or invalid machine_id"})
            continue
        machine_id_counts[mid] += 1
        family = str(row.get("family", "unknown"))
        lineage = str(row.get("lineage_id", "unknown"))
        family_counts[family] += 1
        lineage_counts[lineage] += 1

        m_dict = row.get("machine")
        if not isinstance(m_dict, dict):
            schema_errors.append({"machine_id": mid, "error": "machine field is not a dict"})
            continue

        fp = canonical_machine_fingerprint(m_dict)
        fingerprint_counts[fp] += 1

        try:
            tm = TuringMachine.model_validate(m_dict)
            validated_machines[mid] = tm
            machine_meta[mid] = {
                "family": family,
                "lineage_id": lineage,
                "seed": row.get("seed"),
            }
            beh_sig = behavioral_signature(tm)
            behavioral_groups[beh_sig].append(mid)

            # Check if final state is reachable in static transition graph
            adj: dict[str, set[str]] = defaultdict(set)
            by_state_read: dict[str, dict[str, Transition]] = defaultdict(dict)
            for t in tm.transitions:
                adj[t.from_state].add(t.to_state)
                by_state_read[t.from_state][t.read] = t
            visited = {tm.start_state}
            queue = [tm.start_state]
            while queue:
                curr = queue.pop(0)
                for nxt in adj.get(curr, ()):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)
            if not (visited & set(tm.final_states)):
                final_unreachable_machines += 1

            # Check whether '0' and '1' have identical transitions in every state
            is_agnostic = True
            for s in tm.states:
                if s.id in tm.final_states:
                    continue
                r0 = by_state_read[s.id].get("0")
                r1 = by_state_read[s.id].get("1")
                if (r0 is None) != (r1 is None):
                    is_agnostic = False
                    break
                if r0 is not None and r1 is not None:
                    if r0.to_state != r1.to_state or r0.move != r1.move:
                        is_agnostic = False
                        break
            if is_agnostic:
                symbol_agnostic_machines += 1

        except ValidationError as exc:
            schema_errors.append({"machine_id": mid, "error": str(exc)})

    duplicate_machine_ids = [mid for mid, c in machine_id_counts.items() if c > 1]
    duplicate_fingerprints = sum(1 for c in fingerprint_counts.values() if c > 1)

    # 2. Runs Validation, Re-simulation, Boundaries, and Prefix Activity
    pair_counts = Counter()
    runs_per_machine = Counter()
    dangling_machine_refs: list[str] = []
    invalid_inputs: list[dict[str, Any]] = []
    oversized_api_inputs = 0
    monotonicity_violations: list[dict[str, Any]] = []
    label_formula_violations: list[dict[str, Any]] = []
    resimulation_mismatches: list[dict[str, Any]] = []

    stop_reasons_overall = Counter()
    stop_reasons_by_family: dict[str, Counter[str]] = defaultdict(Counter)
    boundary_step_counts: Counter[str] = Counter()

    budget_counts_all = {b: {"positive": 0, "negative": 0} for b in BUDGETS}
    budget_counts_by_family: dict[str, dict[int, dict[str, int]]] = {
        fam: {b: {"positive": 0, "negative": 0} for b in BUDGETS}
        for fam in family_counts
    }

    early_halt_count = 0  # Halts within <= 10 steps (observed during prefix)
    active_after_10_count = 0  # Still active after 10 steps (requires ML prediction)
    early_halt_by_family = Counter()
    active_after_10_by_family = Counter()

    active10_budget_counts = {b: {"positive": 0, "negative": 0} for b in BUDGETS}
    active10_budget_by_family: dict[str, dict[int, dict[str, int]]] = {
        fam: {b: {"positive": 0, "negative": 0} for b in BUDGETS}
        for fam in family_counts
    }
    active10_stop_reasons_by_family: dict[str, Counter[str]] = defaultdict(Counter)

    runs_by_machine: dict[str, list[dict[str, Any]]] = defaultdict(list)
    active10_runs_by_machine: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unary_only_inputs_count = 0

    for idx, r in enumerate(raw_runs):
        mid = r.get("machine_id")
        inp = r.get("input")
        pair_counts[(mid, inp)] += 1
        runs_per_machine[mid] += 1

        if mid not in validated_machines:
            dangling_machine_refs.append(str(mid))
            continue

        tm = validated_machines[mid]
        fam = machine_meta[mid]["family"]

        if not isinstance(inp, str):
            invalid_inputs.append({"index": idx, "machine_id": mid, "error": "input not str"})
            continue

        alphabet_set = set(tm.input_alphabet)
        bad_chars = [ch for ch in inp if ch not in alphabet_set]
        if bad_chars:
            invalid_inputs.append(
                {"index": idx, "machine_id": mid, "bad_chars": list(set(bad_chars))}
            )
            continue

        if len(inp) > 512:
            oversized_api_inputs += 1
        else:
            # Verify SimulationRequest wire contract compatibility
            try:
                SimulationRequest(machine=tm, input=inp, step_limit=MAX_STEPS)
            except ValidationError as exc:
                invalid_inputs.append({"index": idx, "machine_id": mid, "error": str(exc)})

        if len(set(inp)) <= 1:
            unary_only_inputs_count += 1

        # Re-simulate with authoritative simulator
        sim = simulate(tm, inp, step_limit=MAX_STEPS, trace_limit=PREFIX_STEPS)
        expected_halt_step = sim.steps if sim.halted_within_limit else None
        expected_labels = [
            int(sim.halted_within_limit and sim.steps <= b) for b in BUDGETS
        ]

        recorded_labels = [r.get(f"halt_by_{b}") for b in BUDGETS]
        if recorded_labels != sorted(recorded_labels):
            monotonicity_violations.append(
                {"index": idx, "machine_id": mid, "labels": recorded_labels}
            )

        # Check recorded fields against formula and re-simulation
        if (
            r.get("executed_steps") != sim.steps
            or r.get("halt_step") != expected_halt_step
            or r.get("stop_reason") != sim.stop_reason
            or recorded_labels != expected_labels
        ):
            resimulation_mismatches.append(
                {
                    "index": idx,
                    "machine_id": mid,
                    "input_len": len(inp),
                    "recorded": {
                        "executed_steps": r.get("executed_steps"),
                        "halt_step": r.get("halt_step"),
                        "stop_reason": r.get("stop_reason"),
                        "labels": recorded_labels,
                    },
                    "simulated": {
                        "executed_steps": sim.steps,
                        "halt_step": expected_halt_step,
                        "stop_reason": sim.stop_reason,
                        "labels": expected_labels,
                    },
                }
            )

        # Check formula consistency directly on recorded values
        rec_halted = r.get("stop_reason") in ("final_state", "missing_transition")
        rec_steps = r.get("executed_steps")
        formula_labels = [int(rec_halted and rec_steps <= b) for b in BUDGETS]
        if recorded_labels != formula_labels or (
            rec_halted and r.get("halt_step") != rec_steps
        ) or (not rec_halted and r.get("halt_step") is not None):
            label_formula_violations.append({"index": idx, "machine_id": mid})

        stop_reasons_overall[sim.stop_reason] += 1
        stop_reasons_by_family[fam][sim.stop_reason] += 1

        if sim.halted_within_limit and sim.steps in BOUNDARY_STEPS:
            boundary_step_counts[f"halt_T={sim.steps}"] += 1
        elif not sim.halted_within_limit and sim.steps == MAX_STEPS:
            boundary_step_counts[f"step_limit_{MAX_STEPS}"] += 1

        for b, lbl in zip(BUDGETS, expected_labels):
            key = "positive" if lbl == 1 else "negative"
            budget_counts_all[b][key] += 1
            budget_counts_by_family[fam][b][key] += 1

        is_early_halt = sim.halted_within_limit and sim.steps <= PREFIX_STEPS
        enriched_run = {
            **r,
            "labels_tuple": tuple(expected_labels),
            "is_early_halt": is_early_halt,
        }
        runs_by_machine[mid].append(enriched_run)

        if is_early_halt:
            early_halt_count += 1
            early_halt_by_family[fam] += 1
        else:
            active_after_10_count += 1
            active_after_10_by_family[fam] += 1
            active10_runs_by_machine[mid].append(enriched_run)
            active10_stop_reasons_by_family[fam][sim.stop_reason] += 1
            for b, lbl in zip(BUDGETS, expected_labels):
                key = "positive" if lbl == 1 else "negative"
                active10_budget_counts[b][key] += 1
                active10_budget_by_family[fam][b][key] += 1

    duplicate_pairs = [
        {"machine_id": mid, "input": inp, "count": c}
        for (mid, inp), c in pair_counts.items()
        if c > 1
    ]
    machines_without_runs = [
        mid for mid in validated_machines if runs_per_machine[mid] == 0
    ]

    # 3. Within-Machine Label Variation Analysis
    machines_constant_all_budgets = 0
    machines_varying_any_budget = 0
    constant_by_family = Counter()
    varying_by_family = Counter()
    within_machine_variation_by_budget = {b: 0 for b in BUDGETS}
    active10_machines_with_runs = 0
    active10_machines_varying = 0
    active10_varying_by_family = Counter()

    for mid, m_runs in runs_by_machine.items():
        fam = machine_meta[mid]["family"]
        label_tuples = {mr["labels_tuple"] for mr in m_runs}
        if len(label_tuples) <= 1:
            machines_constant_all_budgets += 1
            constant_by_family[fam] += 1
        else:
            machines_varying_any_budget += 1
            varying_by_family[fam] += 1

        for b_idx, b in enumerate(BUDGETS):
            b_vals = {mr["labels_tuple"][b_idx] for mr in m_runs}
            if len(b_vals) > 1:
                within_machine_variation_by_budget[b] += 1

    for mid, m_runs in active10_runs_by_machine.items():
        fam = machine_meta[mid]["family"]
        active10_machines_with_runs += 1
        label_tuples = {mr["labels_tuple"] for mr in m_runs}
        if len(label_tuples) > 1:
            active10_machines_varying += 1
            active10_varying_by_family[fam] += 1

    # 4. Lineage, Behavioral Equivalence, and Effective Sample Size
    runs_per_lineage = Counter()
    runs_per_family = Counter()
    runs_per_behavioral_group = Counter()
    machine_to_beh_group: dict[str, int] = {}
    for g_idx, (sig, mids) in enumerate(behavioral_groups.items()):
        for mid in mids:
            machine_to_beh_group[mid] = g_idx

    for r in raw_runs:
        mid = r.get("machine_id")
        if mid in machine_meta:
            runs_per_lineage[machine_meta[mid]["lineage_id"]] += 1
            runs_per_family[machine_meta[mid]["family"]] += 1
            runs_per_behavioral_group[str(machine_to_beh_group[mid])] += 1

    multi_machine_lineages = {
        lin: c for lin, c in lineage_counts.items() if c > 1
    }
    multi_machine_behavioral_clones = [
        {
            "clone_count": len(mids),
            "sample_machines": mids[:5],
            "families": sorted({machine_meta[m]["family"] for m in mids}),
            "sample_outcome_profile": [
                {"input": inp, "stop_reason": sr, "steps": st}
                for inp, (sr, st) in zip(BEHAVIORAL_PROBE_INPUTS[:4], sig[:4])
            ],
        }
        for sig, mids in sorted(
            behavioral_groups.items(), key=lambda kv: len(kv[1]), reverse=True
        )
        if len(mids) > 1
    ]

    boundary_fixtures_check = verify_canonical_boundary_fixtures()

    # 5. Diagnose Key Risks Automatically
    risks_identified: list[str] = []
    if oversized_api_inputs > 0:
        risks_identified.append(
            f"{oversized_api_inputs} runs have input length > 512 characters, violating SimulationRequest.input max_length=512 API wire limit."
        )
    if machines_constant_all_budgets / max(len(validated_machines), 1) > 0.5:
        risks_identified.append(
            f"{machines_constant_all_budgets}/{len(validated_machines)} machines ({machines_constant_all_budgets / len(validated_machines):.1%}) have identical labels across all 5 inputs (zero within-machine label variance)."
        )
    for fam, counts in stop_reasons_by_family.items():
        total_fam_runs = sum(counts.values())
        for sr, cnt in counts.items():
            if total_fam_runs > 0 and cnt == total_fam_runs:
                risks_identified.append(
                    f"Family '{fam}' is 100% '{sr}' ({cnt}/{total_fam_runs} runs) — target is deterministically confounded with family identity."
                )
    if symbol_agnostic_machines > 0:
        risks_identified.append(
            f"{symbol_agnostic_machines}/{len(validated_machines)} machines treat input symbols '0' and '1' identically (length-only behavior without symbol-dependent branching)."
        )
    if len(behavioral_groups) < len(validated_machines) * 0.8:
        risks_identified.append(
            f"{len(validated_machines)} machines collapse into only {len(behavioral_groups)} distinct behavioral equivalence classes on canonical probes ({len(validated_machines) - len(behavioral_groups)} redundant clone machines)."
        )
    if boundary_step_counts.get("halt_T=200", 0) == 0 or boundary_step_counts.get("halt_T=1000", 0) == 0:
        risks_identified.append(
            f"Missing exact upper-budget halting boundary examples in dataset: halt_T=200 has {boundary_step_counts.get('halt_T=200', 0)} runs, halt_T=1000 has {boundary_step_counts.get('halt_T=1000', 0)} runs."
        )

    integrity_passed = (
        len(schema_errors) == 0
        and len(duplicate_machine_ids) == 0
        and duplicate_fingerprints == 0
        and len(dangling_machine_refs) == 0
        and len([e for e in invalid_inputs if "bad_chars" in e or "input not str" in e]) == 0
        and len(duplicate_pairs) == 0
        and len(monotonicity_violations) == 0
        and len(label_formula_violations) == 0
        and len(resimulation_mismatches) == 0
        and boundary_fixtures_check["all_passed"]
    )

    return {
        "data_dir": str(data_dir),
        "integrity_passed": integrity_passed,
        "counts": {
            "raw_machines": len(raw_machines),
            "validated_machines": len(validated_machines),
            "raw_runs": len(raw_runs),
            "runs_per_machine_dist": dict(Counter(runs_per_machine.values())),
            "unique_machine_input_pairs": len(pair_counts),
        },
        "validation_checks": {
            "schema_errors": len(schema_errors),
            "duplicate_machine_ids": duplicate_machine_ids,
            "duplicate_machine_fingerprints": duplicate_fingerprints,
            "dangling_machine_refs": dangling_machine_refs,
            "machines_without_runs": machines_without_runs,
            "duplicate_machine_input_pairs": len(duplicate_pairs),
            "invalid_alphabet_inputs": len(
                [e for e in invalid_inputs if "bad_chars" in e]
            ),
            "oversized_api_inputs_gt_512": oversized_api_inputs,
            "monotonicity_violations": len(monotonicity_violations),
            "label_formula_violations": len(label_formula_violations),
            "resimulation_mismatches": len(resimulation_mismatches),
            "canonical_boundary_fixtures_passed": boundary_fixtures_check["all_passed"],
        },
        "families_and_lineages": {
            "machine_counts_by_family": dict(family_counts),
            "unique_lineages": len(lineage_counts),
            "multi_machine_lineages_count": len(multi_machine_lineages),
            "multi_machine_lineages": multi_machine_lineages,
            "unique_behavioral_equivalence_classes": len(behavioral_groups),
            "symbol_agnostic_machines": symbol_agnostic_machines,
            "final_unreachable_machines": final_unreachable_machines,
            "unary_only_inputs_count": unary_only_inputs_count,
            "behavioral_clone_groups": multi_machine_behavioral_clones[:10],
        },
        "effective_sample_sizes": {
            "raw_rows": len(raw_runs),
            "effective_machines_n_eff": compute_effective_sample_size(runs_per_machine),
            "effective_lineages_n_eff": compute_effective_sample_size(runs_per_lineage),
            "effective_behavioral_classes_n_eff": compute_effective_sample_size(
                runs_per_behavioral_group
            ),
            "effective_families_n_eff": compute_effective_sample_size(runs_per_family),
        },
        "stop_reasons": {
            "overall": dict(stop_reasons_overall),
            "by_family": {fam: dict(cnt) for fam, cnt in stop_reasons_by_family.items()},
        },
        "boundary_coverage_in_dataset": {
            f"halt_T={t}": boundary_step_counts.get(f"halt_T={t}", 0)
            for t in BOUNDARY_STEPS
        }
        | {f"step_limit_{MAX_STEPS}": boundary_step_counts.get(f"step_limit_{MAX_STEPS}", 0)},
        "class_balance_all_runs": {
            "overall": {f"budget_{b}": budget_counts_all[b] for b in BUDGETS},
            "by_family": {
                fam: {f"budget_{b}": budget_counts_by_family[fam][b] for b in BUDGETS}
                for fam in family_counts
            },
        },
        "prefix_and_active_after_10_steps": {
            "early_halts_le_10_steps": early_halt_count,
            "early_halts_fraction": round(early_halt_count / max(len(raw_runs), 1), 4),
            "active_after_10_steps": active_after_10_count,
            "active_after_10_fraction": round(
                active_after_10_count / max(len(raw_runs), 1), 4
            ),
            "early_halts_by_family": dict(early_halt_by_family),
            "active_after_10_by_family": dict(active_after_10_by_family),
            "active_after_10_stop_reasons_by_family": {
                fam: dict(cnt) for fam, cnt in active10_stop_reasons_by_family.items()
            },
            "active_after_10_class_balance_overall": {
                f"budget_{b}": active10_budget_counts[b] for b in BUDGETS
            },
            "active_after_10_class_balance_by_family": {
                fam: {f"budget_{b}": active10_budget_by_family[fam][b] for b in BUDGETS}
                for fam in family_counts
            },
        },
        "within_machine_label_variation": {
            "machines_constant_across_all_inputs": machines_constant_all_budgets,
            "machines_varying_across_inputs": machines_varying_any_budget,
            "varying_fraction": round(
                machines_varying_any_budget / max(len(validated_machines), 1), 4
            ),
            "constant_by_family": dict(constant_by_family),
            "varying_by_family": dict(varying_by_family),
            "machines_varying_by_budget": {
                f"budget_{b}": within_machine_variation_by_budget[b] for b in BUDGETS
            },
            "active_after_10_machines_with_runs": active10_machines_with_runs,
            "active_after_10_machines_varying": active10_machines_varying,
            "active_after_10_varying_by_family": dict(active10_varying_by_family),
        },
        "canonical_boundary_probes": boundary_fixtures_check,
        "risks_identified": risks_identified,
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    """Render a concise, human-readable Markdown report from the audit dictionary."""
    c = report["counts"]
    vc = report["validation_checks"]
    fl = report["families_and_lineages"]
    ess = report["effective_sample_sizes"]
    sr = report["stop_reasons"]
    bc = report["boundary_coverage_in_dataset"]
    cb = report["class_balance_all_runs"]
    pa = report["prefix_and_active_after_10_steps"]
    wm = report["within_machine_label_variation"]

    lines = [
        f"# Data Quality Audit Report — `{report['data_dir']}`",
        "",
        "## 1. Executive Summary & Integrity Checks",
        f"- **Integrity Passed (Schema, Re-simulation, Monotonicity, Uniqueness)**: `{report['integrity_passed']}`",
        f"- **Machines Validated**: `{c['validated_machines']} / {c['raw_machines']}`",
        f"- **Simulation Runs Validated**: `{c['raw_runs']}` (Unique `(machine_id, input)` pairs: `{c['unique_machine_input_pairs']}`)",
        f"- **Re-simulation Mismatches**: `{vc['resimulation_mismatches']}`",
        f"- **Monotonicity / Label Formula Violations**: `{vc['monotonicity_violations']} / {vc['label_formula_violations']}`",
        f"- **Inputs > 512 chars (exceeding `SimulationRequest` wire limit)**: `{vc['oversized_api_inputs_gt_512']}`",
        "",
        "## 2. Effective Sample Size & Template/Lineage Overlap",
        f"- **Raw Run Rows**: `{ess['raw_rows']}`",
        f"- **Effective Machines ($N_{{\\text{{eff}}}}$)**: `{ess['effective_machines_n_eff']}` (out of `{c['validated_machines']}` machines)",
        f"- **Unique `lineage_id`s**: `{fl['unique_lineages']}` ($N_{{\\text{{eff}}}}$ = `{ess['effective_lineages_n_eff']}`; lineages with >1 machine: `{fl['multi_machine_lineages_count']}`)",
        f"- **Unique Behavioral Equivalence Classes (on 12 canonical probes)**: `{fl['unique_behavioral_equivalence_classes']}` ($N_{{\\text{{eff}}}}$ = `{ess['effective_behavioral_classes_n_eff']}`)",
        f"- **Symbol-Agnostic Machines ('0' and '1' treated identically)**: `{fl['symbol_agnostic_machines']} / {c['validated_machines']}`",
        f"- **Machines with Unreachable Final State**: `{fl['final_unreachable_machines']} / {c['validated_machines']}`",
        "",
        "## 3. Stop Reasons & Family Confounding",
        f"- **Overall Stop Reasons**: `{sr['overall']}`",
        "",
        "| Family | Machines | `final_state` | `missing_transition` | `step_limit` |",
        "|---|---:|---:|---:|---:|",
    ]

    for fam, m_cnt in sorted(fl["machine_counts_by_family"].items()):
        fam_sr = sr["by_family"].get(fam, {})
        lines.append(
            f"| `{fam}` | {m_cnt} | {fam_sr.get('final_state', 0)} | {fam_sr.get('missing_transition', 0)} | {fam_sr.get('step_limit', 0)} |"
        )

    lines.extend(
        [
            "",
            "## 4. Class Balance: All Runs vs. Subset Active After 10 Steps",
            f"- **Observed Early Halts ($T \\le 10$)**: `{pa['early_halts_le_10_steps']}` (`{pa['early_halts_fraction']:.1%}`) — *resolved directly by 10-step prefix observation*",
            f"- **Active After 10 Steps ($T > 10$ or `step_limit`)**: `{pa['active_after_10_steps']}` (`{pa['active_after_10_fraction']:.1%}`) — *actual ML prediction target population*",
            "",
            "| Subset / Family | Budget 50 (+ / -) | Budget 200 (+ / -) | Budget 1000 (+ / -) |",
            "|---|---|---|---|",
        ]
    )

    all_ov = cb["overall"]
    lines.append(
        f"| **All Runs (Overall)** | {all_ov['budget_50']['positive']} / {all_ov['budget_50']['negative']} | {all_ov['budget_200']['positive']} / {all_ov['budget_200']['negative']} | {all_ov['budget_1000']['positive']} / {all_ov['budget_1000']['negative']} |"
    )
    act_ov = pa["active_after_10_class_balance_overall"]
    lines.append(
        f"| **Active >10 Steps (Overall)** | {act_ov['budget_50']['positive']} / {act_ov['budget_50']['negative']} | {act_ov['budget_200']['positive']} / {act_ov['budget_200']['negative']} | {act_ov['budget_1000']['positive']} / {act_ov['budget_1000']['negative']} |"
    )
    for fam in sorted(fl["machine_counts_by_family"]):
        fb = pa["active_after_10_class_balance_by_family"][fam]
        lines.append(
            f"| Active >10: `{fam}` | {fb['budget_50']['positive']} / {fb['budget_50']['negative']} | {fb['budget_200']['positive']} / {fb['budget_200']['negative']} | {fb['budget_1000']['positive']} / {fb['budget_1000']['negative']} |"
        )

    lines.extend(
        [
            "",
            "## 5. Input-Dependent Label Variation Within Machines",
            f"- **Machines with Constant Labels Across All 5 Inputs**: `{wm['machines_constant_across_all_inputs']} / {c['validated_machines']}`",
            f"- **Machines with Input-Dependent Label Changes**: `{wm['machines_varying_across_inputs']} / {c['validated_machines']}` (`{wm['varying_fraction']:.1%}`)",
            f"- **Varying by Family**: `{wm['varying_by_family']}` (Constant by family: `{wm['constant_by_family']}`)",
            f"- **Machines Varying by Budget**: `{wm['machines_varying_by_budget']}`",
            f"- **Among Machines Active >10 Steps**: `{wm['active_after_10_machines_varying']} / {wm['active_after_10_machines_with_runs']}` vary (`{wm['active_after_10_varying_by_family']}`)",
            "",
            "## 6. Exact Boundary Step Coverage in Dataset",
            f"- Boundary step counts: `{bc}`",
            "",
            "## 7. Key Data Quality Risks Identified",
        ]
    )

    if report["risks_identified"]:
        for risk in report["risks_identified"]:
            lines.append(f"- **RISK**: {risk}")
    else:
        lines.append("- None identified; all diversity and balance checks passed.")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Turing Machine pilot dataset.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/pilot_v1"),
        help="Path to dataset directory containing machines.jsonl and runs.jsonl",
    )
    args = parser.parse_args()

    report = audit_dataset(args.data_dir)
    json_path = args.data_dir / "audit_report.json"
    md_path = args.data_dir / "audit_report.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_text = format_markdown_report(report)
    md_path.write_text(md_text, encoding="utf-8")

    print(md_text)
    print(f"Saved JSON report to: {json_path}")
    print(f"Saved Markdown report to: {md_path}")


if __name__ == "__main__":
    main()

