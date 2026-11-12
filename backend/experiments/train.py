"""Grouped dataset splitting, candidate model training, and validation selection.

Enforces strictly disjoint lineage and machine groups between train, val, and test splits.
Trains Majority, Decision Tree, Random Forest, and MLPClassifier across static and
static-plus-prefix feature sets on cases still active at prefix (steps > 10).
Selects best pipeline per budget (50, 200, 1000) using validation balanced accuracy,
and exports artifacts to models/<run-id>/ alongside manifest.json.
"""

import argparse
import json
import random
from datetime import datetime, timezone
from importlib.metadata import version
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

from backend.app.features import ALL_FEATURE_NAMES, FEATURE_VERSION, STATIC_FEATURE_NAMES
from backend.experiments.generate import machine_fingerprint
from backend.experiments.split_dataset import _build_zero_leakage_clusters

SUPPORTED_BUDGETS = [50, 200, 1000]


def create_grouped_splits(runs_df: pd.DataFrame, machines: dict[str, dict], seed: int = 42) -> dict[str, list[str]]:
    """Keep lineages and matching machine definitions together across splits."""
    fingerprints = {mid: machine_fingerprint(row["machine"]) for mid, row in machines.items()}
    clusters = _build_zero_leakage_clusters(machines, fingerprints)
    cluster_by_machine = {mid: cluster[0] for cluster in clusters for mid in cluster}
    reserved = {
        cluster_by_machine[mid] for mid, row in machines.items() if row["family"] == "delayed_halts"
    }
    data = runs_df.assign(
        group=runs_df["machine_id"].map(cluster_by_machine),
        fingerprint=runs_df["machine_id"].map(fingerprints),
    )
    if data["group"].isna().any():
        raise ValueError("Dataset contains an unknown machine ID.")
    holdout = data[data["family"] == "delayed_halts"].drop_duplicates(["fingerprint", "input"])
    standard = data[~data["group"].isin(reserved)].drop_duplicates(["fingerprint", "input"])
    targets = [f"halt_by_{budget}" for budget in SUPPORTED_BUDGETS]
    groups = sorted(standard["group"].unique())
    rng = random.Random(seed)
    active = standard[standard["active_at_prefix"]]
    counts = active.groupby("group")[targets].sum().reindex(groups, fill_value=0).to_numpy()
    sizes = active.groupby("group").size().reindex(groups, fill_value=0).to_numpy()
    row_counts = standard.groupby("group").size().reindex(groups).to_numpy()
    negative_counts = sizes[:, None] - counts
    total_positive = counts.sum(axis=0)
    total_negative = negative_counts.sum(axis=0)
    if (total_positive == 0).any() or (total_negative == 0).any():
        raise ValueError("Still-active cases must have both classes at every budget.")
    ratios = (0.70, 0.15, 0.15)
    cut1, cut2 = int(len(groups) * ratios[0]), int(len(groups) * sum(ratios[:2]))
    order = list(range(len(groups)))
    best = None
    best_error = float("inf")
    for _ in range(1024):
        rng.shuffle(order)
        parts = (order[:cut1], order[cut1:cut2], order[cut2:])
        positives = np.array([counts[part].sum(axis=0) for part in parts])
        negatives = np.array([negative_counts[part].sum(axis=0) for part in parts])
        if (positives == 0).any() or (negatives == 0).any():
            continue
        targets = np.array(ratios)[:, None]
        row_shares = np.array([row_counts[part].sum() / len(standard) for part in parts])
        error = (
            np.abs(row_shares - ratios).sum()
            + np.abs(positives / total_positive - targets).mean(axis=1).sum()
            + np.abs(negatives / total_negative - targets).mean(axis=1).sum()
        )
        if error < best_error:
            best, best_error = parts, error
    if best is None:
        raise ValueError("Cannot create disjoint splits with both classes at every budget.")

    assignments = {
        name: standard.loc[standard["group"].isin([groups[index] for index in part]), "run_id"].tolist()
        for name, part in zip(("train", "val", "test"), best)
    }
    return {**assignments, "reserved_family": holdout["run_id"].tolist()}


def build_candidate_pipelines(seed: int = 42) -> dict[str, Any]:
    """Define candidate model architectures according to PROJECT_PLAN specifications."""
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "dt_depth3": DecisionTreeClassifier(max_depth=3, random_state=seed),
        "dt_depth5": DecisionTreeClassifier(max_depth=5, random_state=seed),
        "dt_depth8": DecisionTreeClassifier(max_depth=8, random_state=seed),
        "rf_100_d8": RandomForestClassifier(
            n_estimators=100, max_depth=8, min_samples_leaf=2, random_state=seed
        ),
        "mlp_32": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPClassifier(
                        hidden_layer_sizes=(32,),
                        max_iter=300,
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
    with (data_dir / "machines.jsonl").open(encoding="utf-8") as source:
        machines = {row["machine_id"]: row for row in map(json.loads, source)}

    # Merge on run_id
    merged_df = pd.merge(runs_df, feats_df, on="run_id")

    # Filter to cases still active at prefix (>10 steps)
    active_df = merged_df[merged_df["active_at_prefix"]].copy()
    print(f"[{run_id}] Total dataset rows: {len(merged_df)}, Active at prefix (>10 steps): {len(active_df)}")

    # Create and save grouped split manifest
    split_assignments = create_grouped_splits(runs_df, machines)
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
        "feature_version": FEATURE_VERSION,
        "dependency_versions": {name: version(name) for name in ("scikit-learn", "pandas", "joblib", "numpy", "scipy")},
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

                if (bal_acc, macro_f1) > (best_score, best_f1):
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

