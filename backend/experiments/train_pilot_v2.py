"""Train and evaluate bounded-halting classifiers on the leak-free pilot_v2 dataset.

Uses the authoritative feature extractor in `backend/app/features.py` (100% parity
with `backend/app/predictor.py`) and the zero-leakage grouped split manifest in
`data/generated/pilot_v2/split_manifest.json`.

Saves:
- `models/pilot_v2/halt_by_{50,200,1000}.joblib` + `manifest.json`
  (compatible with `backend.app.predictor.load_model_bundle`)
- `report/pilot_v2/metrics.json` and `report/pilot_v2/evaluation_report.md`
  (including side-by-side comparison against `models/final` on the same test set)

Run from the 'Yashraj Part' directory:
    python -m backend.experiments.train_pilot_v2
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from backend.app.features import (
    ALL_FEATURE_NAMES,
    FEATURE_VERSION,
    STATIC_FEATURE_NAMES,
    extract_features,
)
from backend.app.predictor import load_model_bundle, predict_bounded
from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate
from backend.experiments.audit_pilot import BUDGETS, MAX_STEPS, PREFIX_STEPS, load_jsonl

SEED = 202602


def build_candidate_pipelines(seed: int = SEED) -> dict[str, Any]:
    """Candidate architectures matching DATA_AND_ML_PLAN.md."""
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "dt_depth3": DecisionTreeClassifier(max_depth=3, random_state=seed),
        "dt_depth5": DecisionTreeClassifier(max_depth=5, random_state=seed),
        "dt_depth8": DecisionTreeClassifier(max_depth=8, random_state=seed),
        "rf_100_d8": RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=2,
            random_state=seed,
            n_jobs=-1,
        ),
        "mlp_32": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPClassifier(
                        hidden_layer_sizes=(32,),
                        max_iter=400,
                        early_stopping=True,
                        random_state=seed,
                    ),
                ),
            ]
        ),
    }


def _score_predictions(
    y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray | None
) -> dict[str, float]:
    metrics = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
    else:
        metrics["roc_auc"] = 0.5
    return metrics


def _predict_probs_and_labels(model: Any, X: pd.DataFrame, threshold: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)
        classes = list(model.classes_)
        if 1 in classes:
            p1 = probs[:, classes.index(1)]
        else:
            p1 = np.zeros(len(X), dtype=float)
        preds = (p1 >= threshold).astype(int)
        return p1, preds
    preds = model.predict(X).astype(int)
    return preds.astype(float), preds


def prepare_dataframe(data_dir: Path) -> pd.DataFrame:
    """Build DataFrame using `backend.app.features` and `split_manifest.json`."""
    machines_raw = load_jsonl(data_dir / "machines.jsonl")
    runs_raw = load_jsonl(data_dir / "runs.jsonl")
    manifest = json.loads((data_dir / "split_manifest.json").read_text(encoding="utf-8"))

    machines = {
        m["machine_id"]: TuringMachine.model_validate(m["machine"])
        for m in machines_raw
    }
    machine_to_split = manifest["machine_to_split"]

    rows: list[dict[str, Any]] = []
    for r in runs_raw:
        mid = r["machine_id"]
        inp = r["input"]
        tm = machines[mid]
        sim_prefix = simulate(tm, inp, step_limit=PREFIX_STEPS, trace_limit=PREFIX_STEPS)
        feats = extract_features(tm, inp, sim_prefix.trace, feature_names=ALL_FEATURE_NAMES)
        row: dict[str, Any] = {
            "machine_id": mid,
            "input": inp,
            "split": machine_to_split[mid],
            "active_at_prefix": not sim_prefix.halted_within_limit,
            **feats,
        }
        for b in BUDGETS:
            row[f"halt_by_{b}"] = int(r[f"halt_by_{b}"])
        rows.append(row)

    return pd.DataFrame(rows)


def train_and_evaluate(
    data_dir: Path,
    models_out_dir: Path,
    report_out_dir: Path,
    baseline_models_dir: Path | None = Path("models/final"),
) -> dict[str, Any]:
    df = prepare_dataframe(data_dir)
    active_df = df[df["active_at_prefix"]].copy()

    train_df = active_df[active_df["split"] == "train"]
    val_df = active_df[active_df["split"] == "val"]
    test_df = active_df[active_df["split"] == "test"]
    full_test_df = df[df["split"] == "test"]

    models_out_dir.mkdir(parents=True, exist_ok=True)
    report_out_dir.mkdir(parents=True, exist_ok=True)

    feature_configs = {
        "static": STATIC_FEATURE_NAMES,
        "static_plus_prefix": ALL_FEATURE_NAMES,
    }

    manifest: dict[str, Any] = {
        "run_id": "pilot_v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prefix_budget": PREFIX_STEPS,
        "feature_version": FEATURE_VERSION,
        "budgets": list(BUDGETS),
        "models": {},
        "comparison_log": [],
    }

    selected_models: dict[int, Any] = {}
    selected_feature_sets: dict[int, list[str]] = {}
    test_results_by_budget: dict[str, Any] = {}

    for budget in BUDGETS:
        target = f"halt_by_{budget}"
        y_train = train_df[target].to_numpy()
        y_val = val_df[target].to_numpy()
        y_test = test_df[target].to_numpy()

        best_val_bal = -1.0
        best_entry: dict[str, Any] = {}
        best_model = None
        best_cols: list[str] = []

        for f_name, f_cols in feature_configs.items():
            X_train = train_df[f_cols]
            X_val = val_df[f_cols]
            X_test = test_df[f_cols]

            for c_name, model in build_candidate_pipelines(SEED).items():
                model.fit(X_train, y_train)
                p_val, pred_val = _predict_probs_and_labels(model, X_val)
                val_metrics = _score_predictions(y_val, pred_val, p_val)

                p_test, pred_test = _predict_probs_and_labels(model, X_test)
                test_metrics = _score_predictions(y_test, pred_test, p_test)

                log_row = {
                    "budget": budget,
                    "candidate": c_name,
                    "feature_set": f_name,
                    "val": val_metrics,
                    "test_active": test_metrics,
                }
                manifest["comparison_log"].append(log_row)

                if val_metrics["balanced_accuracy"] > best_val_bal:
                    best_val_bal = val_metrics["balanced_accuracy"]
                    best_model = model
                    best_cols = list(f_cols)
                    best_entry = {
                        "model_id": f"{c_name}_{f_name}_{budget}",
                        "candidate": c_name,
                        "feature_set": f_name,
                        "val": val_metrics,
                        "test_active": test_metrics,
                    }

        model_filename = f"halt_by_{budget}.joblib"
        joblib.dump(best_model, models_out_dir / model_filename)
        selected_models[budget] = best_model
        selected_feature_sets[budget] = best_cols

        manifest["models"][str(budget)] = {
            "model_id": best_entry["model_id"],
            "filename": model_filename,
            "threshold": 0.5,
            "feature_set": best_entry["feature_set"],
            "feature_names": best_cols,
            "val_balanced_accuracy": best_entry["val"]["balanced_accuracy"],
            "val_macro_f1": best_entry["val"]["macro_f1"],
        }

        # Full-pipeline evaluation on test split (observed early halts + active ML predictions)
        X_full_act = test_df[best_cols]
        _, act_preds = _predict_probs_and_labels(best_model, X_full_act)
        act_pred_map = dict(zip(test_df.index, act_preds))

        y_full_true = full_test_df[target].to_numpy()
        y_full_pred = np.array(
            [
                1 if not row["active_at_prefix"] else act_pred_map[idx]
                for idx, row in full_test_df.iterrows()
            ],
            dtype=int,
        )
        full_metrics = _score_predictions(y_full_true, y_full_pred, None)

        test_results_by_budget[str(budget)] = {
            "selected_model_id": best_entry["model_id"],
            "active_test_count": int(len(test_df)),
            "full_test_count": int(len(full_test_df)),
            "active_test_metrics": best_entry["test_active"],
            "full_pipeline_test_metrics": full_metrics,
        }

    # Optional side-by-side comparison with existing models/final on the exact same pilot_v2 test split
    baseline_comparison: dict[str, Any] = {}
    if baseline_models_dir is not None and (baseline_models_dir / "manifest.json").exists():
        base_bundle = load_model_bundle(baseline_models_dir)
        machines_map = {
            m["machine_id"]: TuringMachine.model_validate(m["machine"])
            for m in load_jsonl(data_dir / "machines.jsonl")
        }
        for budget in BUDGETS:
            y_act_t, y_act_p = [], []
            y_all_t, y_all_p = [], []
            for _, row in full_test_df.iterrows():
                tm = machines_map[row["machine_id"]]
                res = predict_bounded(tm, row["input"], budget, base_bundle)
                yt = int(row[f"halt_by_{budget}"])
                yp = int(res["predicted_halted_within_limit"])
                y_all_t.append(yt)
                y_all_p.append(yp)
                if res["source"] == "model":
                    y_act_t.append(yt)
                    y_act_p.append(yp)
            baseline_comparison[str(budget)] = {
                "active_test_metrics": _score_predictions(np.array(y_act_t), np.array(y_act_p), None),
                "full_pipeline_test_metrics": _score_predictions(np.array(y_all_t), np.array(y_all_p), None),
            }

    (models_out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    report_payload = {
        "data_dir": str(data_dir),
        "models_dir": str(models_out_dir),
        "splits": {
            "train_active": int(len(train_df)),
            "val_active": int(len(val_df)),
            "test_active": int(len(test_df)),
            "test_full": int(len(full_test_df)),
        },
        "pilot_v2_test_results": test_results_by_budget,
        "models_final_on_pilot_v2_test": baseline_comparison,
        "comparison_log": manifest["comparison_log"],
    }
    (report_out_dir / "metrics.json").write_text(
        json.dumps(report_payload, indent=2) + "\n", encoding="utf-8"
    )

    md_lines = [
        "# `pilot_v2` Model Training & Evaluation Report",
        "",
        f"- **Dataset**: `{data_dir}` (`train` active={len(train_df)}, `val` active={len(val_df)}, `test` active={len(test_df)}, `test` full={len(full_test_df)})",
        f"- **Zero-Leakage Grouping**: Connected components of `(lineage_id, behavioral_signature)`",
        "",
        "## 1. Selected `pilot_v2` Models vs. `models/final` on `pilot_v2` Test Set",
        "",
        "| Budget | Selected `pilot_v2` Model | `pilot_v2` Active Bal Acc | `pilot_v2` Active F1 | `pilot_v2` Full Bal Acc | `models/final` Active Bal Acc |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for b in BUDGETS:
        r = test_results_by_budget[str(b)]
        base_ba = (
            baseline_comparison[str(b)]["active_test_metrics"]["balanced_accuracy"]
            if str(b) in baseline_comparison
            else 0.0
        )
        md_lines.append(
            f"| **{b}** | `{r['selected_model_id']}` | **{r['active_test_metrics']['balanced_accuracy']:.4f}** | "
            f"**{r['active_test_metrics']['macro_f1']:.4f}** | **{r['full_pipeline_test_metrics']['balanced_accuracy']:.4f}** | {base_ba:.4f} |"
        )

    md_lines.extend(
        [
            "",
            "## 2. Static vs. Static+Prefix Comparison (Active Test Set)",
            "",
            "| Budget | Candidate | Feature Set | Val Bal Acc | Test Bal Acc | Test Macro F1 | Test ROC-AUC |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in manifest["comparison_log"]:
        md_lines.append(
            f"| {row['budget']} | `{row['candidate']}` | `{row['feature_set']}` | "
            f"{row['val']['balanced_accuracy']:.4f} | {row['test_active']['balanced_accuracy']:.4f} | "
            f"{row['test_active']['macro_f1']:.4f} | {row['test_active']['roc_auc']:.4f} |"
        )

    md_text = "\n".join(md_lines) + "\n"
    (report_out_dir / "evaluation_report.md").write_text(md_text, encoding="utf-8")
    print(md_text)
    return report_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate pilot_v2 models.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated/pilot_v2"))
    parser.add_argument("--models-dir", type=Path, default=Path("models/pilot_v2"))
    parser.add_argument("--report-dir", type=Path, default=Path("report/pilot_v2"))
    args = parser.parse_args()

    train_and_evaluate(
        data_dir=args.data_dir,
        models_out_dir=args.models_dir,
        report_out_dir=args.report_dir,
    )


if __name__ == "__main__":
    main()

