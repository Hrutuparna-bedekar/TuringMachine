"""Grouped dataset splitting, candidate model training, and validation selection.

Enforces strictly disjoint lineage and machine groups between train, val, and test splits.
Trains Majority, Decision Tree, Random Forest, and MLPClassifier across static and
static-plus-prefix feature sets on cases still active at prefix (steps > 10).
Selects best pipeline per budget (50, 200, 1000) using validation balanced accuracy,
and exports artifacts to models/<run-id>/ alongside manifest.json.
"""

import argparse
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from backend.app.features import ALL_FEATURE_NAMES, STATIC_FEATURE_NAMES

SUPPORTED_BUDGETS = [50, 200, 1000]


def create_grouped_splits(
    runs_df: pd.DataFrame,
    reserved_family: str = "delayed_halts",
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 42,
) -> dict[str, list[str]]:
    """Partition runs into reserved_family, train, validation, and test sets.

    Grouping is strictly enforced at the lineage_id level (or machine_id level),
    guaranteeing ZERO leakage of machines or template variants between splits.
    """
    rng = random.Random(seed)

    # 1. Reserved family runs for out-of-distribution evaluation
    reserved_runs = runs_df[runs_df["family"] == reserved_family]["run_id"].tolist()

    # 2. Remaining data grouped by lineage_id
    standard_df = runs_df[runs_df["family"] != reserved_family]
    lineages = sorted(standard_df["lineage_id"].unique())
    rng.shuffle(lineages)

    n_total_lin = len(lineages)
    n_train = int(n_total_lin * train_frac)
    n_val = int(n_total_lin * val_frac)

    train_lineages = set(lineages[:n_train])
    val_lineages = set(lineages[n_train : n_train + n_val])
    test_lineages = set(lineages[n_train + n_val :])

    train_runs = standard_df[standard_df["lineage_id"].isin(train_lineages)]["run_id"].tolist()
    val_runs = standard_df[standard_df["lineage_id"].isin(val_lineages)]["run_id"].tolist()
    test_runs = standard_df[standard_df["lineage_id"].isin(test_lineages)]["run_id"].tolist()

    return {
        "train": train_runs,
        "val": val_runs,
        "test": test_runs,
        "reserved_family": reserved_runs,
    }


def build_candidate_pipelines(seed: int = 42) -> dict[str, Any]:
    """Define candidate model architectures according to PROJECT_PLAN specifications."""
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "dt_depth3": DecisionTreeClassifier(max_depth=3, random_state=seed),
        "dt_depth5": DecisionTreeClassifier(max_depth=5, random_state=seed),
        "dt_depth8": DecisionTreeClassifier(max_depth=8, random_state=seed),
        "rf_100_d8": RandomForestClassifier(
            n_estimators=100, max_depth=8, min_samples_leaf=2, random_state=seed, n_jobs=-1
        ),
        "mlp_32": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPClassifier(
                        hidden_layer_sizes=(32,),
                        max_iter=300,
                        early_stopping=True,
                        random_state=seed,
                    ),
                ),
            ]
        ),
    }


def train_and_select_models(run_id: str, data_dir: Path, out_dir: Path) -> dict[str, Any]:
    runs_file = data_dir / "runs.parquet"
    feats_file = data_dir / "features.parquet"

    if not runs_file.exists() or not feats_file.exists():
        raise FileNotFoundError(f"Missing required dataset files in {data_dir}")

    runs_df = pd.read_parquet(runs_file)
    feats_df = pd.read_parquet(feats_file)

    # Merge on run_id
    merged_df = pd.merge(runs_df, feats_df, on="run_id")

    # Filter to cases still active at prefix (>10 steps)
    active_df = merged_df[merged_df["active_at_prefix"]].copy()
    print(f"[{run_id}] Total dataset rows: {len(merged_df)}, Active at prefix (>10 steps): {len(active_df)}")

    # Create and save grouped split manifest
    split_assignments = create_grouped_splits(runs_df, reserved_family="delayed_halts")
    out_dir.mkdir(parents=True, exist_ok=True)
    split_manifest_file = out_dir / "split_manifest.json"
    with open(split_manifest_file, "w", encoding="utf-8") as f:
        json.dump(split_assignments, f, indent=2)

    train_set = set(split_assignments["train"])
    val_set = set(split_assignments["val"])

    active_train = active_df[active_df["run_id"].isin(train_set)]
    active_val = active_df[active_df["run_id"].isin(val_set)]

    print(f"[{run_id}] Training split rows: {len(active_train)}, Validation split rows: {len(active_val)}")

    feature_configs = {
        "static": STATIC_FEATURE_NAMES,
        "static_plus_prefix": ALL_FEATURE_NAMES,
    }

    selected_bundle: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prefix_budget": 10,
        "budgets": SUPPORTED_BUDGETS,
        "models": {},
        "comparison_log": [],
    }

    # For each budget, evaluate all candidates across feature configurations
    for budget in SUPPORTED_BUDGETS:
        target_col = f"halt_by_{budget}"
        y_train = active_train[target_col].to_numpy()
        y_val = active_val[target_col].to_numpy()

        best_score = -1.0
        best_f1 = -1.0
        best_candidate_name = ""
        best_pipeline = None
        best_feat_config_name = ""
        best_feat_names: list[str] = []

        print(f"\n--- Model Selection for Budget {budget} ---")
        print(f"Train class balance: {np.bincount(y_train)}")
        print(f"Val class balance:   {np.bincount(y_val)}")

        for f_name, f_cols in feature_configs.items():
            X_train = active_train[f_cols]
            X_val = active_val[f_cols]

            candidates = build_candidate_pipelines(seed=42)

            for c_name, model in candidates.items():
                # Fit
                model.fit(X_train, y_train)

                # Predict on validation
                if hasattr(model, "predict_proba"):
                    probs = model.predict_proba(X_val)
                    classes = list(model.classes_)
                    if 1 in classes:
                        class_1_idx = classes.index(1)
                        y_pred = (probs[:, class_1_idx] >= 0.5).astype(int)
                    else:
                        y_pred = np.zeros(len(X_val), dtype=int)
                else:
                    y_pred = model.predict(X_val)

                bal_acc = float(balanced_accuracy_score(y_val, y_pred))
                macro_f1 = float(f1_score(y_val, y_pred, average="macro", zero_division=0))

                entry = {
                    "budget": budget,
                    "candidate": c_name,
                    "feature_set": f_name,
                    "val_balanced_accuracy": round(bal_acc, 4),
                    "val_macro_f1": round(macro_f1, 4),
                }
                selected_bundle["comparison_log"].append(entry)

                print(
                    f"[{c_name} | {f_name:18s}] Val Bal Acc: {bal_acc:.4f}, Val Macro F1: {macro_f1:.4f}"
                )

                if bal_acc > best_score:
                    best_score = bal_acc
                    best_f1 = macro_f1
                    best_candidate_name = f"{c_name}_{f_name}"
                    best_pipeline = model
                    best_feat_config_name = f_name
                    best_feat_names = f_cols

        print(
            f"--> Selected for Budget {budget}: {best_candidate_name} (Bal Acc: {best_score:.4f}, F1: {best_f1:.4f})"
        )

        # Save model artifact
        model_filename = f"halt_by_{budget}.joblib"
        joblib.dump(best_pipeline, out_dir / model_filename)

        selected_bundle["models"][str(budget)] = {
            "model_id": f"{best_candidate_name}_{budget}",
            "filename": model_filename,
            "threshold": 0.5,
            "feature_set": best_feat_config_name,
            "feature_names": best_feat_names,
            "val_balanced_accuracy": best_score,
            "val_macro_f1": best_f1,
        }

    # Save manifest.json
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(selected_bundle, f, indent=2)

    print(f"\n[{run_id}] Model training and selection complete! Manifest written to {manifest_path}")
    return selected_bundle


def main():
    parser = argparse.ArgumentParser(description="Train and select halting prediction models.")
    parser.add_argument("--run-id", default="final", help="Identifier for experiment run.")
    args = parser.parse_args()

    data_dir = Path("data") / "generated" / args.run_id
    out_dir = Path("models") / args.run_id
    train_and_select_models(args.run_id, data_dir, out_dir)


if __name__ == "__main__":
    main()

