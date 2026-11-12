"""Callable ML inference module for bounded halting prediction.

Independent of HTTP framework. Integrates prefix execution observation (10 steps)
with ML classification for still-active machines at budgets 50, 200, and 1000.
"""

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from backend.app.features import ALL_FEATURE_NAMES, extract_features
from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate

SUPPORTED_BUDGETS = {50, 200, 1000}
PREFIX_BUDGET = 10


def load_model_bundle(models_dir: str | Path) -> dict[str, Any]:
    """Load exported model pipelines and manifest for all supported budgets.

    Expects models_dir to contain:
      - manifest.json
      - halt_by_50.joblib
      - halt_by_200.joblib
      - halt_by_1000.joblib
    """
    path = Path(models_dir)
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    models: dict[int, Any] = {}
    thresholds: dict[int, float] = {}
    model_ids: dict[int, str] = {}
    feature_sets: dict[int, list[str]] = {}

    for budget in SUPPORTED_BUDGETS:
        key = str(budget)
        if key not in manifest.get("models", {}):
            raise KeyError(f"Budget {budget} missing from manifest models configuration")

        entry = manifest["models"][key]
        model_file = entry["filename"]
        file_path = path / model_file
        if not file_path.exists():
            raise FileNotFoundError(f"Model artifact not found at {file_path}")

        models[budget] = joblib.load(file_path)
        thresholds[budget] = float(entry.get("threshold", 0.5))
        model_ids[budget] = entry.get("model_id", f"model_{budget}")
        feature_sets[budget] = entry.get("feature_names", ALL_FEATURE_NAMES)

    return {
        "manifest": manifest,
        "models": models,
        "thresholds": thresholds,
        "model_ids": model_ids,
        "feature_sets": feature_sets,
    }


def predict_bounded(
    machine: TuringMachine,
    input_text: str,
    step_limit: int,
    models: dict[str, Any],
) -> dict[str, Any]:
    """Execute prefix simulation and classify halting within a bounded step limit.

    Parameters
    ----------
    machine : TuringMachine
        Validated Turing Machine definition.
    input_text : str
        Input string on tape starting at cell 0.
    step_limit : int
        Bounded prediction budget. Must be 50, 200, or 1000.
    models : dict[str, Any]
        Preloaded bundle containing model pipelines, thresholds, and metadata.

    Returns
    -------
    dict[str, Any]
        Observation or model prediction result according to PROJECT_PLAN contract.
    """
    if step_limit not in SUPPORTED_BUDGETS:
        raise ValueError(
            f"Unsupported step_limit {step_limit}. Supported budgets are {sorted(SUPPORTED_BUDGETS)}"
        )

    # 1. Run simulator up to prefix limit (10 steps)
    sim_res = simulate(machine, input_text, step_limit=PREFIX_BUDGET, trace_limit=PREFIX_BUDGET)

    # 2. Early-halt observed within 10 steps
    if sim_res.halted_within_limit:
        return {
            "source": "observed",
            "predicted_halted_within_limit": True,
            "observed_steps": sim_res.steps,
            "stop_reason": sim_res.stop_reason,
        }

    # 3. Active after step 10 -> Extract features and invoke ML pipeline
    pipeline = models["models"][step_limit]
    threshold = models["thresholds"][step_limit]
    model_id = models["model_ids"][step_limit]
    feature_names = models["feature_sets"].get(step_limit, ALL_FEATURE_NAMES)

    # Extract ordered features matching training columns
    feat_dict = extract_features(machine, input_text, sim_res.trace, feature_names=feature_names)
    X = pd.DataFrame([feat_dict], columns=feature_names)

    # Obtain probability score for halt class (label 1)
    if hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(X)
        classes_list = list(pipeline.classes_)
        if 1 in classes_list:
            class_1_idx = classes_list.index(1)
            halt_score = float(probs[0][class_1_idx])
        else:
            halt_score = 0.0
    else:
        # Fallback for models without predict_proba
        raw_pred = pipeline.predict(X)[0]
        halt_score = 1.0 if raw_pred == 1 else 0.0

    predicted_halt = bool(halt_score >= threshold)

    return {
        "source": "model",
        "predicted_halted_within_limit": predicted_halt,
        "observed_steps": PREFIX_BUDGET,
        "model_id": model_id,
        "halt_score": round(halt_score, 4),
    }


def predict_all_budgets(
    machine: TuringMachine,
    input_text: str,
    models: dict[str, Any],
    *,
    enforce_monotonic: bool = True,
) -> dict[int, dict[str, Any]]:
    """Predict bounded halting across all supported budgets (50, 200, 1000).

    Runs the 10-step prefix simulation once, then scores each budget. When
    `enforce_monotonic=True`, enforces non-decreasing scores and binary labels
    across budgets: P(T <= 50) <= P(T <= 200) <= P(T <= 1000).
    """
    ordered_budgets = sorted(SUPPORTED_BUDGETS)
    results: dict[int, dict[str, Any]] = {
        b: predict_bounded(machine, input_text, b, models) for b in ordered_budgets
    }

    if not enforce_monotonic:
        return results

    if all(r["source"] == "model" for r in results.values()):
        running_score = 0.0
        running_pred = False
        for b in ordered_budgets:
            r = results[b]
            score = max(running_score, float(r["halt_score"]))
            running_score = score
            pred = running_pred or bool(score >= models["thresholds"][b]) or bool(
                r["predicted_halted_within_limit"]
            )
            running_pred = pred
            r["halt_score"] = round(score, 4)
            r["predicted_halted_within_limit"] = pred

    return results

