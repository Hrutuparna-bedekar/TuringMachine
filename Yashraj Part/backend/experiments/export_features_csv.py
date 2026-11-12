"""Export leak-free ML feature and bounded-halting label CSV tables from a dataset directory.

Generates two CSV files inside the target dataset directory (default `data/generated/pilot_v2`):
1. `features_and_labels.csv`: All 5,000 runs with grouping column (`machine_id`),
   split assignment (`split`: train/val/test), early-halt indicator (`observed_early_halt`),
   the 14 ordered static + 10-step prefix feature columns, and the 3 target labels
   (`halt_by_50`, `halt_by_200`, `halt_by_1000`).
2. `features_active_after_10.csv`: Only runs that remain active after 10 transitions
   (`observed_early_halt == 0`), which is the true learned-model training/evaluation subset.

Diagnostic/leakage fields (`executed_steps`, `halt_step`, `stop_reason`, `family`,
`lineage_id`, `seed`) are strictly excluded from the exported CSV tables.

Run from the 'Yashraj Part' directory:
    python -m backend.experiments.export_features_csv --data-dir data/generated/pilot_v2
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from backend.app.schemas import TuringMachine
from backend.experiments.audit_pilot import BUDGETS, load_jsonl
from backend.experiments.features import (
    ALL_FEATURE_COLUMNS,
    FORBIDDEN_LEAKAGE_KEYS,
    observe_prefix_and_extract,
)
from backend.experiments.split_dataset import create_grouped_splits

CSV_METADATA_COLUMNS: tuple[str, ...] = (
    "machine_id",
    "split",
    "observed_early_halt",
)
CSV_LABEL_COLUMNS: tuple[str, ...] = (
    "halt_by_50",
    "halt_by_200",
    "halt_by_1000",
)
CSV_HEADER: tuple[str, ...] = (
    CSV_METADATA_COLUMNS + ALL_FEATURE_COLUMNS + CSV_LABEL_COLUMNS
)


def export_dataset_to_csv(data_dir: Path) -> dict[str, Any]:
    """Extract 14-column features and write full + active-after-10 CSV files."""
    machines_raw = load_jsonl(data_dir / "machines.jsonl")
    runs_raw = load_jsonl(data_dir / "runs.jsonl")

    manifest_path = data_dir / "split_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = create_grouped_splits(data_dir)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    machine_to_split: dict[str, str] = manifest["machine_to_split"]
    machines_by_id: dict[str, TuringMachine] = {
        m["machine_id"]: TuringMachine.model_validate(m["machine"])
        for m in machines_raw
    }

    # Ensure no forbidden leakage column is in the feature columns
    assert not (set(ALL_FEATURE_COLUMNS) & FORBIDDEN_LEAKAGE_KEYS)

    all_rows: list[dict[str, Any]] = []
    active10_rows: list[dict[str, Any]] = []

    for r in runs_raw:
        mid = r["machine_id"]
        inp = r["input"]
        tm = machines_by_id[mid]
        split_name = machine_to_split[mid]

        obs = observe_prefix_and_extract(tm, inp)
        is_early = int(obs["observed_early_halt"])
        feats = obs["features"]

        row: dict[str, Any] = {
            "machine_id": mid,
            "split": split_name,
            "observed_early_halt": is_early,
        }
        for col in ALL_FEATURE_COLUMNS:
            row[col] = feats[col]
        for b in BUDGETS:
            row[f"halt_by_{b}"] = int(r[f"halt_by_{b}"])

        all_rows.append(row)
        if not obs["observed_early_halt"]:
            active10_rows.append(row)

    full_csv_path = data_dir / "features_and_labels.csv"
    active_csv_path = data_dir / "features_active_after_10.csv"

    for path, rows in ((full_csv_path, all_rows), (active_csv_path, active10_rows)):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(CSV_HEADER))
            writer.writeheader()
            writer.writerows(rows)

    return {
        "full_csv_path": str(full_csv_path),
        "active_csv_path": str(active_csv_path),
        "total_rows": len(all_rows),
        "active_after_10_rows": len(active10_rows),
        "early_halt_rows": len(all_rows) - len(active10_rows),
        "columns": list(CSV_HEADER),
        "feature_columns": list(ALL_FEATURE_COLUMNS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export ML features and labels to CSV.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/pilot_v2"),
        help="Dataset directory containing machines.jsonl and runs.jsonl",
    )
    args = parser.parse_args()

    summary = export_dataset_to_csv(args.data_dir)
    print(f"Exported all runs ({summary['total_rows']} rows) to: {summary['full_csv_path']}")
    print(
        f"Exported active-after-10 runs ({summary['active_after_10_rows']} rows) to: {summary['active_csv_path']}"
    )
    print(f"Observed early halts (T <= 10): {summary['early_halt_rows']}")
    print(f"Feature columns ({len(summary['feature_columns'])}): {summary['feature_columns']}")


if __name__ == "__main__":
    main()

