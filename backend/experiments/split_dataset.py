"""Grouped machine and template-lineage dataset splitter with zero-leakage verification.

Assigns machines to train (70%), val (15%), and test (15%) splits grouped by
connected components of (lineage_id, behavioral_signature) so that no machine,
template lineage, or behavioral clone ever crosses split boundaries.
Verifies class balance across all budgets (50, 200, 1000) both overall and on the
subset of runs still active after 10 transitions.

Run from the 'Yashraj Part' directory:
    python -m backend.experiments.split_dataset --data-dir data/generated/pilot_v2
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from collections.abc import Hashable
from pathlib import Path
from typing import Any

from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate
from backend.experiments.audit_pilot import (
    BUDGETS,
    MAX_STEPS,
    PREFIX_STEPS,
    behavioral_signature,
    canonical_machine_fingerprint,
    load_jsonl,
)

SPLIT_SEED = 202602
SPLIT_NAMES = ("train", "val", "test")
TARGET_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
MIN_MINORITY_FRACTION = 0.12


def _build_zero_leakage_clusters(
    machines_by_id: dict[str, dict[str, Any]],
    beh_sigs: dict[str, Hashable],
) -> list[list[str]]:
    """Group machines by Union-Find over shared lineage_id and shared behavioral_signature."""
    parent = {mid: mid for mid in machines_by_id}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    by_lineage: dict[str, list[str]] = defaultdict(list)
    by_beh: dict[Hashable, list[str]] = defaultdict(list)

    for mid, m_row in machines_by_id.items():
        by_lineage[str(m_row["lineage_id"])].append(mid)
        by_beh[beh_sigs[mid]].append(mid)

    for group in by_lineage.values():
        first = group[0]
        for other in group[1:]:
            union(first, other)

    for group in by_beh.values():
        first = group[0]
        for other in group[1:]:
            union(first, other)

    clusters_map: dict[str, list[str]] = defaultdict(list)
    for mid in sorted(machines_by_id):
        clusters_map[find(mid)].append(mid)

    return [ clusters_map[k] for k in sorted(clusters_map) ]


def create_grouped_splits(
    data_dir: Path,
    seed: int = SPLIT_SEED,
    ratios: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Create and verify zero-leakage grouped splits for a dataset directory."""
    if ratios is None:
        ratios = TARGET_RATIOS

    raw_machines = load_jsonl(data_dir / "machines.jsonl")
    raw_runs = load_jsonl(data_dir / "runs.jsonl")

    machines_by_id: dict[str, dict[str, Any]] = {}
    validated_tms: dict[str, TuringMachine] = {}
    beh_sigs: dict[str, tuple[tuple[str, int], ...]] = {}
    fingerprints: dict[str, str] = {}

    for m_row in raw_machines:
        mid = m_row["machine_id"]
        machines_by_id[mid] = m_row
        tm = TuringMachine.model_validate(m_row["machine"])
        validated_tms[mid] = tm
        beh_sigs[mid] = behavioral_signature(tm)
        fingerprints[mid] = canonical_machine_fingerprint(m_row["machine"])

    runs_by_machine: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in raw_runs:
        mid = r["machine_id"]
        tm = validated_tms[mid]
        sim_prefix = simulate(tm, r["input"], step_limit=PREFIX_STEPS, trace_limit=0)
        active_after_10 = not sim_prefix.halted_within_limit
        runs_by_machine[mid].append({**r, "active_after_10": active_after_10})

    clusters = _build_zero_leakage_clusters(machines_by_id, beh_sigs)

    # Group clusters by dominant family so every family is stratified across train/val/test
    clusters_by_family: dict[str, list[list[str]]] = defaultdict(list)
    for cl in clusters:
        dom_family = Counter(machines_by_id[m]["family"] for m in cl).most_common(1)[0][0]
        clusters_by_family[dom_family].append(cl)

    rng = random.Random(seed)
    machine_to_split: dict[str, str] = {}

    for fam, fam_clusters in sorted(clusters_by_family.items()):
        # Sort clusters deterministically by average halt_by_200 rate + cluster ID, then bucket-shuffle
        def cluster_profile(cl: list[str]) -> tuple[float, str]:
            c_runs = [r for m in cl for r in runs_by_machine[m]]
            rate200 = sum(r["halt_by_200"] for r in c_runs) / max(len(c_runs), 1)
            return (round(rate200, 1), cl[0])

        fam_clusters_sorted = sorted(fam_clusters, key=cluster_profile)
        # Shuffle within strata of 7 clusters to preserve stratification across train/val/test
        stratified: list[list[str]] = []
        chunk_size = 7
        for i in range(0, len(fam_clusters_sorted), chunk_size):
            chunk = fam_clusters_sorted[i : i + chunk_size]
            rng.shuffle(chunk)
            stratified.extend(chunk)

        total_fam_machines = sum(len(c) for c in stratified)
        target_val = max(1, round(total_fam_machines * ratios["val"]))
        target_test = max(1, round(total_fam_machines * ratios["test"]))

        counts = {"train": 0, "val": 0, "test": 0}
        # Assign round-robin within each 7-cluster block: [train, val, test, train, train, train, train]
        pattern = ("val", "test", "train", "train", "train", "train", "train")
        for idx, cl in enumerate(stratified):
            preferred = pattern[idx % len(pattern)]
            if preferred == "val" and counts["val"] >= target_val:
                split_choice = "train"
            elif preferred == "test" and counts["test"] >= target_test:
                split_choice = "train"
            else:
                split_choice = preferred

            for m in cl:
                machine_to_split[m] = split_choice
            counts[split_choice] += len(cl)

    # Verify zero leakage across splits
    split_machines: dict[str, set[str]] = {s: set() for s in SPLIT_NAMES}
    split_lineages: dict[str, set[str]] = {s: set() for s in SPLIT_NAMES}
    split_fingerprints: dict[str, set[str]] = {s: set() for s in SPLIT_NAMES}
    split_beh_sigs: dict[str, set[tuple[tuple[str, int], ...]]] = {
        s: set() for s in SPLIT_NAMES
    }

    for mid, sp in machine_to_split.items():
        split_machines[sp].add(mid)
        split_lineages[sp].add(str(machines_by_id[mid]["lineage_id"]))
        split_fingerprints[sp].add(fingerprints[mid])
        split_beh_sigs[sp].add(beh_sigs[mid])

    machine_overlap = 0
    lineage_overlap = 0
    fingerprint_overlap = 0
    beh_sig_overlap = 0
    for i, s1 in enumerate(SPLIT_NAMES):
        for s2 in SPLIT_NAMES[i + 1 :]:
            machine_overlap += len(split_machines[s1] & split_machines[s2])
            lineage_overlap += len(split_lineages[s1] & split_lineages[s2])
            fingerprint_overlap += len(split_fingerprints[s1] & split_fingerprints[s2])
            beh_sig_overlap += len(split_beh_sigs[s1] & split_beh_sigs[s2])

    # Compute split statistics (overall, active_after_10, by family)
    split_stats: dict[str, Any] = {}
    coverage_issues: list[str] = []

    for sp in SPLIT_NAMES:
        mids = sorted(split_machines[sp])
        sp_runs = [r for m in mids for r in runs_by_machine[m]]
        sp_active10 = [r for r in sp_runs if r["active_after_10"]]
        sp_early = [r for r in sp_runs if not r["active_after_10"]]

        fam_machine_counts = Counter(machines_by_id[m]["family"] for m in mids)
        stop_counts = Counter(r["stop_reason"] for r in sp_runs)

        budgets_all = {}
        budgets_active10 = {}
        for b in BUDGETS:
            pos_all = sum(r[f"halt_by_{b}"] for r in sp_runs)
            neg_all = len(sp_runs) - pos_all
            rate_all = round(pos_all / max(len(sp_runs), 1), 4)
            budgets_all[f"budget_{b}"] = {
                "positive": pos_all,
                "negative": neg_all,
                "positive_rate": rate_all,
            }
            if min(rate_all, 1.0 - rate_all) < MIN_MINORITY_FRACTION:
                coverage_issues.append(
                    f"Split '{sp}' all-runs budget_{b} has low minority fraction: {rate_all:.3f}"
                )

            pos_act = sum(r[f"halt_by_{b}"] for r in sp_active10)
            neg_act = len(sp_active10) - pos_act
            rate_act = round(pos_act / max(len(sp_active10), 1), 4)
            budgets_active10[f"budget_{b}"] = {
                "positive": pos_act,
                "negative": neg_act,
                "positive_rate": rate_act,
            }
            if min(rate_act, 1.0 - rate_act) < MIN_MINORITY_FRACTION:
                coverage_issues.append(
                    f"Split '{sp}' active_after_10 budget_{b} has low minority fraction: {rate_act:.3f}"
                )

        split_stats[sp] = {
            "machine_count": len(mids),
            "lineage_count": len(split_lineages[sp]),
            "run_count": len(sp_runs),
            "early_halt_le_10_count": len(sp_early),
            "active_after_10_count": len(sp_active10),
            "families": dict(fam_machine_counts),
            "stop_reasons": dict(stop_counts),
            "class_balance_all_runs": budgets_all,
            "class_balance_active_after_10": budgets_active10,
            "machine_ids": mids,
        }

    zero_leakage = (
        machine_overlap == 0
        and lineage_overlap == 0
        and fingerprint_overlap == 0
        and beh_sig_overlap == 0
    )

    manifest = {
        "data_dir": str(data_dir),
        "split_seed": seed,
        "target_ratios": ratios,
        "total_clusters": len(clusters),
        "leakage_checks": {
            "zero_leakage_verified": zero_leakage,
            "machine_id_overlap": machine_overlap,
            "lineage_id_overlap": lineage_overlap,
            "fingerprint_overlap": fingerprint_overlap,
            "behavioral_signature_overlap": beh_sig_overlap,
        },
        "class_coverage_passed": len(coverage_issues) == 0,
        "coverage_issues": coverage_issues,
        "splits": split_stats,
        "machine_to_split": {mid: machine_to_split[mid] for mid in sorted(machine_to_split)},
    }
    return manifest


def format_split_markdown(manifest: dict[str, Any]) -> str:
    lc = manifest["leakage_checks"]
    lines = [
        f"# Split Manifest & Leakage Verification — `{manifest['data_dir']}`",
        "",
        "## 1. Leakage & Grouping Verification",
        f"- **Zero Leakage Verified**: `{lc['zero_leakage_verified']}`",
        f"- **Atomic (Lineage + Behavioral) Clusters**: `{manifest['total_clusters']}`",
        f"- **Overlaps Across Splits (`train` / `val` / `test`)**:",
        f"  - `machine_id` overlap: `{lc['machine_id_overlap']}`",
        f"  - `lineage_id` overlap: `{lc['lineage_id_overlap']}`",
        f"  - Canonical JSON fingerprint overlap: `{lc['fingerprint_overlap']}`",
        f"  - Canonical 12-probe behavioral signature overlap: `{lc['behavioral_signature_overlap']}`",
        f"- **Class Coverage Check Passed**: `{manifest['class_coverage_passed']}`",
        "",
        "## 2. Split Sizes & Activity Breakdown",
        "| Split | Machines | Lineages | Total Runs | Observed Early Halts ($T \\le 10$) | Active After 10 Steps ($T > 10$) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sp in SPLIT_NAMES:
        st = manifest["splits"][sp]
        lines.append(
            f"| `{sp}` | {st['machine_count']} | {st['lineage_count']} | {st['run_count']} | {st['early_halt_le_10_count']} | {st['active_after_10_count']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Class Balance Across Budgets (All Runs vs. Active After 10 Steps)",
            "| Split & Subset | Budget 50 (+ / - / %+) | Budget 200 (+ / - / %+) | Budget 1000 (+ / - / %+) |",
            "|---|---|---|---|",
        ]
    )
    for sp in SPLIT_NAMES:
        st = manifest["splits"][sp]
        cb_all = st["class_balance_all_runs"]
        cb_act = st["class_balance_active_after_10"]
        lines.append(
            f"| `{sp}` (All) | {cb_all['budget_50']['positive']} / {cb_all['budget_50']['negative']} ({cb_all['budget_50']['positive_rate']:.1%}) "
            f"| {cb_all['budget_200']['positive']} / {cb_all['budget_200']['negative']} ({cb_all['budget_200']['positive_rate']:.1%}) "
            f"| {cb_all['budget_1000']['positive']} / {cb_all['budget_1000']['negative']} ({cb_all['budget_1000']['positive_rate']:.1%}) |"
        )
        lines.append(
            f"| `{sp}` (Active >10) | {cb_act['budget_50']['positive']} / {cb_act['budget_50']['negative']} ({cb_act['budget_50']['positive_rate']:.1%}) "
            f"| {cb_act['budget_200']['positive']} / {cb_act['budget_200']['negative']} ({cb_act['budget_200']['positive_rate']:.1%}) "
            f"| {cb_act['budget_1000']['positive']} / {cb_act['budget_1000']['negative']} ({cb_act['budget_1000']['positive_rate']:.1%}) |"
        )

    lines.extend(
        [
            "",
            "## 4. Family Distribution Across Splits (Machines)",
            "| Split | " + " | ".join(sorted(manifest["splits"]["train"]["families"])) + " |",
            "|---|" + "|".join("---:" for _ in manifest["splits"]["train"]["families"]) + "|",
        ]
    )
    fams = sorted(manifest["splits"]["train"]["families"])
    for sp in SPLIT_NAMES:
        st_fams = manifest["splits"][sp]["families"]
        lines.append(
            f"| `{sp}` | " + " | ".join(str(st_fams.get(f, 0)) for f in fams) + " |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create zero-leakage grouped splits.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/pilot_v2"),
        help="Dataset directory containing machines.jsonl and runs.jsonl",
    )
    parser.add_argument("--seed", type=int, default=SPLIT_SEED)
    args = parser.parse_args()

    manifest = create_grouped_splits(args.data_dir, seed=args.seed)
    json_path = args.data_dir / "split_manifest.json"
    md_path = args.data_dir / "split_manifest.md"

    json_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md_text = format_split_markdown(manifest)
    md_path.write_text(md_text, encoding="utf-8")

    print(md_text)
    print(f"Saved split manifest JSON to: {json_path}")
    print(f"Saved split manifest Markdown to: {md_path}")


if __name__ == "__main__":
    main()

