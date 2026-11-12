"""Evaluation and reporting for bounded halting prediction models.

Evaluates frozen models on held-out test splits, unseen family holdouts, complexity bins,
and computes runtime latency benchmarks against exact simulation. Generates publication-ready
markdown reports, metrics JSON, and visualization plots.
"""

import argparse
import json
import platform
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from backend.app.predictor import load_model_bundle, predict_bounded
from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate
from backend.experiments.generate import machine_fingerprint

SUPPORTED_BUDGETS = [50, 200, 1000]


def predict_labels(pipeline: Any, X: pd.DataFrame, threshold: float) -> np.ndarray:
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(X)
        classes = list(pipeline.classes_)
        if 1 in classes:
            class_1_idx = classes.index(1)
            y_pred = (probs[:, class_1_idx] >= threshold).astype(int)
        else:
            y_pred = np.zeros(len(X), dtype=int)
        return y_pred
    return pipeline.predict(X)


def evaluate_model_pipeline(
    pipeline: Any,
    X: pd.DataFrame,
    y: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute evaluation metrics for one model and test split."""
    if len(X) == 0:
        return {}

    y_pred = predict_labels(pipeline, X, threshold)

    bal_acc = float(balanced_accuracy_score(y, y_pred))
    macro_f1 = float(f1_score(y, y_pred, average="macro", zero_division=0))
    prec = float(precision_score(y, y_pred, zero_division=0))
    rec = float(recall_score(y, y_pred, zero_division=0))
    cm = confusion_matrix(y, y_pred, labels=[0, 1]).tolist()

    return {
        "sample_count": len(X),
        "balanced_accuracy": round(bal_acc, 4),
        "macro_f1": round(macro_f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "confusion_matrix": cm,
        "class_balance": [int(np.sum(y == 0)), int(np.sum(y == 1))],
    }


def run_evaluation(run_id: str, data_dir: Path, models_dir: Path, report_dir: Path):
    report_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = report_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data and models
    runs_df = pd.read_parquet(data_dir / "runs.parquet")
    feats_df = pd.read_parquet(data_dir / "features.parquet")
    merged_df = pd.merge(runs_df, feats_df, on="run_id")

    with open(models_dir / "split_manifest.json", "r", encoding="utf-8") as f:
        splits = json.load(f)

    bundle = load_model_bundle(models_dir)
    manifest = bundle["manifest"]

    test_runs_set = set(splits["test"])
    reserved_runs_set = set(splits["reserved_family"])

    test_df = merged_df[merged_df["run_id"].isin(test_runs_set)].copy()
    reserved_df = merged_df[merged_df["run_id"].isin(reserved_runs_set)].copy()

    # Active subset on test
    active_test_df = test_df[test_df["active_at_prefix"]].copy()
    active_reserved_df = reserved_df[reserved_df["active_at_prefix"]].copy()

    print(f"[{run_id}] Test split total: {len(test_df)}, Active at prefix: {len(active_test_df)}")
    print(f"[{run_id}] Reserved family total: {len(reserved_df)}, Active at prefix: {len(active_reserved_df)}")

    metrics_report: dict[str, Any] = {
        "run_id": run_id,
        "budgets_evaluated": SUPPORTED_BUDGETS,
        "by_budget": {},
        "full_pipeline_vs_active_only": {},
        "complexity_breakdown": {},
        "reserved_family_generalization": {},
        "latency_benchmark": {},
        "validation_model_comparison": manifest["comparison_log"],
        "error_examples": {},
    }

    # -------------------------------------------------------------
    # Question 1: Budget Effect on Active Cases
    # -------------------------------------------------------------
    for budget in SUPPORTED_BUDGETS:
        model = bundle["models"][budget]
        threshold = bundle["thresholds"][budget]
        feat_names = bundle["feature_sets"][budget]

        X_test = active_test_df[feat_names]
        y_test = active_test_df[f"halt_by_{budget}"].to_numpy()

        res = evaluate_model_pipeline(model, X_test, y_test, threshold)
        res["model_id"] = bundle["model_ids"][budget]
        res["feature_set"] = manifest["models"][str(budget)]["feature_set"]
        metrics_report["by_budget"][str(budget)] = res
        incorrect = active_test_df.loc[predict_labels(model, X_test, threshold) != y_test].copy()
        incorrect["distance_to_budget"] = (incorrect["halt_step"] - budget).abs()
        examples = []
        for row in incorrect.sort_values("distance_to_budget", na_position="last").head(3).itertuples():
            examples.append({
                "run_id": row.run_id,
                "machine_id": row.machine_id,
                "input_length": len(row.input),
                "predicted_halt": not bool(getattr(row, f"halt_by_{budget}")),
                "observed_halt_step": int(row.halt_step) if pd.notna(row.halt_step) else None,
            })
        metrics_report["error_examples"][str(budget)] = examples

    # -------------------------------------------------------------
    # Question 2: Full Pipeline (Observed + Model) vs Active Only
    # -------------------------------------------------------------
    for budget in SUPPORTED_BUDGETS:
        # Full pipeline evaluation on ALL test cases (early observed + model predicted)
        y_true_all = test_df[f"halt_by_{budget}"].to_numpy()
        y_pred_full: list[int] = []

        model = bundle["models"][budget]
        threshold = bundle["thresholds"][budget]
        feat_names = bundle["feature_sets"][budget]

        for _, row in test_df.iterrows():
            if not row["active_at_prefix"]:
                # Early halt observed at <= 10 steps -> always positive
                y_pred_full.append(1)
            else:
                X_row = pd.DataFrame([row[feat_names]], columns=feat_names)
                if hasattr(model, "predict_proba"):
                    probs = model.predict_proba(X_row)
                    classes = list(model.classes_)
                    p = probs[0][classes.index(1)] if 1 in classes else 0.0
                    y_pred_full.append(1 if p >= threshold else 0)
                else:
                    y_pred_full.append(int(model.predict(X_row)[0]))

        y_pred_full_arr = np.array(y_pred_full)
        full_bal_acc = float(balanced_accuracy_score(y_true_all, y_pred_full_arr))
        full_f1 = float(f1_score(y_true_all, y_pred_full_arr, average="macro", zero_division=0))

        metrics_report["full_pipeline_vs_active_only"][str(budget)] = {
            "active_only_balanced_accuracy": metrics_report["by_budget"][str(budget)]["balanced_accuracy"],
            "full_pipeline_balanced_accuracy": round(full_bal_acc, 4),
            "full_pipeline_macro_f1": round(full_f1, 4),
            "total_test_samples": len(test_df),
        }

    # -------------------------------------------------------------
    # Question 3: Complexity Breakdown (State Count Bins)
    # -------------------------------------------------------------
    # Bins: 2 states, 3 states, 4+ states
    active_test_df["state_bin"] = pd.cut(
        active_test_df["state_count"],
        bins=[0, 2, 3, 100],
        labels=["1–2_states", "3_states", "4+_states"],
    )

    for sbin in ["1–2_states", "3_states", "4+_states"]:
        sub_df = active_test_df[active_test_df["state_bin"] == sbin]
        metrics_report["complexity_breakdown"][sbin] = {}
        for budget in SUPPORTED_BUDGETS:
            if len(sub_df) > 0 and len(np.unique(sub_df[f"halt_by_{budget}"])) > 1:
                feat_names = bundle["feature_sets"][budget]
                sub_res = evaluate_model_pipeline(
                    bundle["models"][budget],
                    sub_df[feat_names],
                    sub_df[f"halt_by_{budget}"].to_numpy(),
                    bundle["thresholds"][budget],
                )
            else:
                sub_res = {"sample_count": len(sub_df), "note": "Insufficient class diversity in bin"}
            if not sub_df.empty:
                sub_res["median_rule_density"] = float(sub_df["rule_density"].median())
                sub_res["median_input_length"] = float(sub_df["input_length"].median())
            metrics_report["complexity_breakdown"][sbin][str(budget)] = sub_res

    # -------------------------------------------------------------
    # Question 4: Generalization on Unseen Family (Reserved: delayed_halts)
    # -------------------------------------------------------------
    for budget in SUPPORTED_BUDGETS:
        if active_reserved_df[f"halt_by_{budget}"].nunique() == 2:
            feat_names = bundle["feature_sets"][budget]
            res_gen = evaluate_model_pipeline(
                bundle["models"][budget],
                active_reserved_df[feat_names],
                active_reserved_df[f"halt_by_{budget}"].to_numpy(),
                bundle["thresholds"][budget],
            )
        else:
            res_gen = {"sample_count": len(active_reserved_df), "note": "Insufficient class diversity"}
        metrics_report["reserved_family_generalization"][str(budget)] = res_gen

    # -------------------------------------------------------------
    # Question 5: Latency Benchmarking (Warmed-up Prediction vs Exact Sim)
    # -------------------------------------------------------------
    print(f"[{run_id}] Measuring latency benchmarks on sample of test machines...")
    # Read canonical machine definitions
    machines_map: dict[str, TuringMachine] = {}
    with open(data_dir / "machines.jsonl", "r", encoding="utf-8") as mf:
        for line in mf:
            rec = json.loads(line)
            machines_map[rec["machine_id"]] = TuringMachine.model_validate(rec["machine"])
    metrics_report["unique_machine_definitions"] = {
        name: len({machine_fingerprint(machines_map[mid].model_dump()) for mid in frame["machine_id"].unique()})
        for name, frame in (("test", test_df), ("reserved_family", reserved_df))
    }

    def benchmark(samples: pd.DataFrame, budget: int) -> dict[str, Any]:
        exact_times, prediction_times = [], []
        for row in samples.itertuples():
            machine = machines_map[row.machine_id]
            start = time.perf_counter()
            simulate(machine, row.input, step_limit=budget, trace_limit=0)
            exact_times.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            predict_bounded(machine, row.input, budget, bundle)
            prediction_times.append((time.perf_counter() - start) * 1000)
        return {
            "sample_count": len(samples),
            "exact_simulation_ms": {
                "median": round(float(np.median(exact_times)), 3),
                "p95": round(float(np.percentile(exact_times, 95)), 3),
            },
            "prediction_pipeline_ms": {
                "median": round(float(np.median(prediction_times)), 3),
                "p95": round(float(np.percentile(prediction_times, 95)), 3),
            },
            "speedup_ratio": round(float(np.median(exact_times)) / float(np.median(prediction_times)), 2),
        }

    metrics_report["benchmark_environment"] = platform.platform()
    metrics_report["latency_by_budget"] = {}
    for budget in SUPPORTED_BUDGETS:
        groups = {
            "active_at_prefix": active_test_df,
            "early_halt": test_df[~test_df["active_at_prefix"]],
        }
        timings = {}
        for name, group in groups.items():
            if group.empty:
                continue
            samples = group.sample(n=min(len(group), 100), random_state=42)
            warm = samples.iloc[0]
            machine = machines_map[warm["machine_id"]]
            simulate(machine, warm["input"], step_limit=budget, trace_limit=0)
            predict_bounded(machine, warm["input"], budget, bundle)
            timings[name] = benchmark(samples, budget)
        metrics_report["latency_by_budget"][str(budget)] = timings
    metrics_report["latency_benchmark"] = metrics_report["latency_by_budget"]["1000"]["active_at_prefix"]

    # Save metrics JSON
    with open(report_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_report, f, indent=2)

    # -------------------------------------------------------------
    # Plotting Figures
    # -------------------------------------------------------------
    # Figure 1: Balanced Accuracy and Macro F1 across budgets
    plt.figure(figsize=(8, 5))
    budgets = [str(b) for b in SUPPORTED_BUDGETS]
    accs = [metrics_report["by_budget"][b]["balanced_accuracy"] for b in budgets]
    f1s = [metrics_report["by_budget"][b]["macro_f1"] for b in budgets]

    x = np.arange(len(budgets))
    width = 0.35
    plt.bar(x - width / 2, accs, width, label="Balanced Accuracy", color="#3b82f6")
    plt.bar(x + width / 2, f1s, width, label="Macro F1", color="#10b981")
    plt.xticks(x, [f"Budget {b}" for b in budgets])
    plt.ylim(0.0, 1.05)
    plt.ylabel("Score")
    plt.title("Model Performance by Bounded Step Limit (Active Cases)")
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(fig_dir / "score_by_budget.png", dpi=200)
    plt.close()

    # Figure 2: Confusion Matrices
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for idx, b in enumerate(SUPPORTED_BUDGETS):
        cm = np.array(metrics_report["by_budget"][str(b)]["confusion_matrix"])
        ax = axes[idx]
        im = ax.imshow(cm, cmap="Blues", interpolation="nearest")
        ax.set_title(f"Budget {b}")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Non-halt", "Halt"])
        ax.set_yticklabels(["Non-halt", "Halt"])
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=12)
    plt.tight_layout()
    plt.savefig(fig_dir / "confusion_matrices.png", dpi=200)
    plt.close()

    # Figure 3: Latency Comparison
    plt.figure(figsize=(7, 4.5))
    categories = ["Exact Sim (Trace=0)", "Prefix (10) + ML Predict"]
    medians = [
        metrics_report["latency_benchmark"]["exact_simulation_ms"]["median"],
        metrics_report["latency_benchmark"]["prediction_pipeline_ms"]["median"],
    ]
    p95s = [
        metrics_report["latency_benchmark"]["exact_simulation_ms"]["p95"],
        metrics_report["latency_benchmark"]["prediction_pipeline_ms"]["p95"],
    ]
    x = np.arange(len(categories))
    plt.bar(x - width / 2, medians, width, label="Median Latency (ms)", color="#6366f1")
    plt.bar(x + width / 2, p95s, width, label="95th Percentile (ms)", color="#f59e0b")
    plt.xticks(x, categories)
    plt.ylabel("Time (ms)")
    plt.title("Execution Latency Benchmark Comparison")
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(fig_dir / "latency_comparison.png", dpi=200)
    plt.close()

    # -------------------------------------------------------------
    # Markdown Report Generation
    # -------------------------------------------------------------
    lines = [
        "# Bounded halting evaluation",
        "",
        f"Run: `{run_id}`. Generated rows: {len(runs_df):,}. "
        f"Grouped test rows: {len(test_df):,}, with {len(active_test_df):,} active at step 10.",
        "",
        "The engine reports early observed halts exactly. Models estimate whether an active run "
        "will halt within a finite budget. Performance reflects the synthetic dataset and selected holdouts.",
        "",
        "## Held-out performance",
        "",
        "| Budget | Selected model | Features | Active-only balanced accuracy | Active-only macro F1 | Full-pipeline balanced accuracy | Unseen-family balanced accuracy |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for budget in SUPPORTED_BUDGETS:
        key = str(budget)
        result = metrics_report["by_budget"][key]
        full = metrics_report["full_pipeline_vs_active_only"][key]
        holdout = metrics_report["reserved_family_generalization"][key]
        unseen = holdout.get("balanced_accuracy")
        lines.append(
            f"| {budget} | `{result['model_id']}` | {result['feature_set']} "
            f"| {result['balanced_accuracy']:.2%} | {result['macro_f1']:.2%} "
            f"| {full['full_pipeline_balanced_accuracy']:.2%} "
            f"| {format(unseen, '.2%') if unseen is not None else 'Insufficient class diversity'} |"
        )
    lines.extend([
        "",
        "The unseen family is `delayed_halts`. It contains "
        f"{metrics_report['unique_machine_definitions']['reserved_family']} distinct machine definitions "
        "with multiple inputs each. The main split keeps identical definitions and template lineages "
        "together and removes repeated machine/input pairs.",
        "",
        "## Best validation result by feature set",
        "",
        "| Budget | Static | Static plus prefix |",
        "| ---: | ---: | ---: |",
    ])
    for budget in SUPPORTED_BUDGETS:
        rows = [row for row in manifest["comparison_log"] if row["budget"] == budget]
        scores = [
            max(row["val_balanced_accuracy"] for row in rows if row["feature_set"] == name)
            for name in ("static", "static_plus_prefix")
        ]
        lines.append(f"| {budget} | {scores[0]:.2%} | {scores[1]:.2%} |")
    lines.extend([
        "",
        "The full candidate comparison, class counts, confusion matrices, complexity breakdown, "
        "and misclassified examples are in [metrics.json](metrics.json).",
        "",
        "## Latency",
        "",
        f"Measured on {metrics_report['benchmark_environment']} with trace-free exact simulation.",
        "",
        "| Budget | Cases | Exact median (ms) | Predictor median (ms) |",
        "| ---: | --- | ---: | ---: |",
    ])
    for budget, groups in metrics_report["latency_by_budget"].items():
        for name, values in groups.items():
            lines.append(
                f"| {budget} | {name} | {values['exact_simulation_ms']['median']} "
                f"| {values['prediction_pipeline_ms']['median']} |"
            )
    lines.extend([
        "",
        "A run that is active at the budget may halt later. The general halting problem remains undecidable.",
        "",
    ])
    report_md = "\n".join(lines)

    with open(report_dir / "report.md", "w", encoding="utf-8") as rf:
        rf.write(report_md)

    print(f"[{run_id}] Evaluation complete! Report and figures saved to {report_dir}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate frozen halting prediction models.")
    parser.add_argument("--run-id", default="final", help="Identifier for experiment run.")
    args = parser.parse_args()

    data_dir = Path("data") / "generated" / args.run_id
    models_dir = Path("models") / args.run_id
    report_dir = Path("report") / args.run_id
    run_evaluation(args.run_id, data_dir, models_dir, report_dir)


if __name__ == "__main__":
    main()
