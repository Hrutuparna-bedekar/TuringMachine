"""Tests for dataset generator, label integrity, determinism, and invariants."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from backend.app.features import ALL_FEATURE_NAMES
from backend.experiments.generate import run_generation


class TestDatasetIntegrity:
    """Verifies dataset generator output, schema conformity, and label mathematics."""

    @pytest.fixture(scope="module")
    def smoke_dataset_dir(self):
        """Generate a minimal smoke dataset of 20 machines for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_cfg = Path(tmp_dir) / "config.json"
            cfg = {
                "budgets": [50, 200, 1000],
                "prefix_budget": 10,
                "input_alphabet": ["0", "1"],
                "tape_alphabet": ["0", "1", "B"],
                "blank_symbol": "B",
                "inputs_per_machine": 3,
                "pilot_machines": 20,
                "final_machines": 20,
                "seed": 123,
                "family_weights": {
                    "random_tables": 0.25,
                    "scans_rewrites": 0.25,
                    "input_dependent": 0.20,
                    "delayed_halts": 0.15,
                    "long_running": 0.15,
                },
            }
            with open(tmp_cfg, "w", encoding="utf-8") as f:
                json.dump(cfg, f)

            # Run smoke generation
            out_dir = run_generation(str(tmp_cfg), "test_smoke", is_pilot=True)
            yield out_dir

    def test_files_created_and_valid(self, smoke_dataset_dir):
        out_dir = Path(smoke_dataset_dir)
        assert (out_dir / "machines.jsonl").exists()
        assert (out_dir / "runs.parquet").exists()
        assert (out_dir / "features.parquet").exists()
        assert (out_dir / "summary.json").exists()

    def test_monotonic_label_boundary_invariant(self, smoke_dataset_dir):
        """Invariant: halt_by_50 <= halt_by_200 <= halt_by_1000 for every run."""
        runs_df = pd.read_parquet(Path(smoke_dataset_dir) / "runs.parquet")

        assert len(runs_df) > 0
        diff_50_200 = runs_df["halt_by_200"] - runs_df["halt_by_50"]
        diff_200_1000 = runs_df["halt_by_1000"] - runs_df["halt_by_200"]

        assert (diff_50_200 >= 0).all(), "Found violation where halt_by_50 > halt_by_200"
        assert (diff_200_1000 >= 0).all(), "Found violation where halt_by_200 > halt_by_1000"

    def test_active_at_prefix_consistency(self, smoke_dataset_dir):
        """Invariant: active_at_prefix == (halt_step is None or halt_step > 10)."""
        runs_df = pd.read_parquet(Path(smoke_dataset_dir) / "runs.parquet")

        for _, row in runs_df.iterrows():
            halt_step = row["halt_step"]
            expected_active = bool(pd.isna(halt_step) or halt_step > 10)
            assert bool(row["active_at_prefix"]) == expected_active

    def test_feature_table_structure_and_no_nan(self, smoke_dataset_dir):
        """Invariant: features.parquet has run_id + exact ALL_FEATURE_NAMES and no nulls."""
        feats_df = pd.read_parquet(Path(smoke_dataset_dir) / "features.parquet")
        runs_df = pd.read_parquet(Path(smoke_dataset_dir) / "runs.parquet")

        assert len(feats_df) == len(runs_df)
        assert list(feats_df.columns) == ["run_id"] + ALL_FEATURE_NAMES
        assert feats_df.isna().sum().sum() == 0, "Features contain NaN values!"
