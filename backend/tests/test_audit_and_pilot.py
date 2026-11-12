"""Tests for data-quality audit, pilot_v2 generation, zero-leakage splits, and feature extraction."""

from __future__ import annotations

from pathlib import Path
import pytest

from backend.app.predictor import load_model_bundle, predict_all_budgets, predict_bounded
from backend.app.schemas import State, Transition, TuringMachine
from backend.app.simulator import simulate
from backend.experiments.audit_pilot import (
    audit_dataset,
    verify_canonical_boundary_fixtures,
)
from backend.experiments.export_features_csv import (
    CSV_HEADER,
    export_dataset_to_csv,
)
from backend.experiments.features import (
    ALL_FEATURE_COLUMNS,
    FORBIDDEN_LEAKAGE_KEYS,
    PREFIX_FEATURE_COLUMNS,
    STATIC_FEATURE_COLUMNS,
    extract_feature_vector,
    extract_features,
    extract_prefix_features_from_trace,
    observe_prefix_and_extract,
)
from backend.experiments.split_dataset import SPLIT_NAMES, create_grouped_splits

PILOT_V1_DIR = Path("data/generated/pilot_v1")
PILOT_V2_DIR = Path("data/generated/pilot_v2")


class TestCanonicalBoundaryFixturesAndAuditV1:
    """Tests the standalone data-quality audit on canonical fixtures and pilot_v1."""

    def test_canonical_boundary_probes_pass(self):
        res = verify_canonical_boundary_fixtures()
        assert res["all_passed"] is True
        by_name = {p["probe"]: p for p in res["probes"]}
        assert by_name["T=0_final_state"]["labels"] == [1, 1, 1]
        assert by_name["T=0_missing_transition"]["labels"] == [1, 1, 1]
        assert by_name["T=50_exact_budget"]["labels"] == [1, 1, 1]
        assert by_name["T=51_just_over_50"]["labels"] == [0, 1, 1]
        assert by_name["T=200_exact_budget"]["labels"] == [0, 1, 1]
        assert by_name["T=201_just_over_200"]["labels"] == [0, 0, 1]
        assert by_name["T=1000_exact_halt"]["labels"] == [0, 0, 1]
        assert by_name["T=1000_exact_halt"]["halted_within_limit"] is True
        assert by_name["T=1000_step_limit"]["labels"] == [0, 0, 0]
        assert by_name["T=1000_step_limit"]["halted_within_limit"] is False

    def test_audit_pilot_v1_reproduces_observations_and_flags_risks(self):
        assert PILOT_V1_DIR.exists(), "pilot_v1 directory must be preserved"
        report = audit_dataset(PILOT_V1_DIR)

        assert report["integrity_passed"] is True
        assert report["counts"]["validated_machines"] == 500
        assert report["counts"]["raw_runs"] == 2500
        assert report["validation_checks"]["resimulation_mismatches"] == 0
        assert report["validation_checks"]["monotonicity_violations"] == 0

        # Confirm audit detects the known confounding and wire-limit issues in pilot_v1
        assert report["validation_checks"]["oversized_api_inputs_gt_512"] == 175
        assert report["stop_reasons"]["by_family"]["cyclic_loop"] == {"step_limit": 500}
        assert report["families_and_lineages"]["symbol_agnostic_machines"] == 275
        assert len(report["risks_identified"]) >= 4


@pytest.fixture(scope="module")
def v2_audit_report():
    assert (PILOT_V2_DIR / "machines.jsonl").exists()
    assert (PILOT_V2_DIR / "runs.jsonl").exists()
    return audit_dataset(PILOT_V2_DIR)


@pytest.fixture(scope="module")
def v2_split_manifest():
    return create_grouped_splits(PILOT_V2_DIR)


class TestPilotV2QualityAndSplits:
    """Verifies that pilot_v2 resolves pilot_v1's confounding and passes split checks."""

    def test_pilot_v2_integrity_and_wire_compliance(self, v2_audit_report):
        assert v2_audit_report["integrity_passed"] is True
        assert v2_audit_report["counts"]["validated_machines"] == 1000
        assert v2_audit_report["counts"]["raw_runs"] == 5000
        assert v2_audit_report["counts"]["unique_machine_input_pairs"] == 5000
        assert v2_audit_report["validation_checks"]["oversized_api_inputs_gt_512"] == 0
        assert v2_audit_report["validation_checks"]["resimulation_mismatches"] == 0
        assert v2_audit_report["validation_checks"]["monotonicity_violations"] == 0

    def test_pilot_v2_eliminates_family_determinism_and_symbol_agnosticism(
        self, v2_audit_report
    ):
        fl = v2_audit_report["families_and_lineages"]
        # ~20-25% of machines have final_reachable=0 (halting via missing_transition or hitting step_limit)
        assert 150 <= fl["final_unreachable_machines"] <= 300
        assert fl["symbol_agnostic_machines"] <= 15

        # Every family must have both halting runs and step_limit runs
        sr_by_fam = v2_audit_report["stop_reasons"]["by_family"]
        for fam, counts in sr_by_fam.items():
            halted = counts.get("final_state", 0) + counts.get("missing_transition", 0)
            limit = counts.get("step_limit", 0)
            assert halted > 0, f"Family {fam} has no halting runs"
            assert limit > 0, f"Family {fam} has no step_limit runs"

    def test_pilot_v2_within_machine_variation_and_boundary_coverage(
        self, v2_audit_report
    ):
        wm = v2_audit_report["within_machine_label_variation"]
        # At least 80% of machines must exhibit input-dependent label changes (up from 45.2% in v1)
        assert wm["varying_fraction"] >= 0.80
        assert wm["active_after_10_machines_varying"] >= 700

        bc = v2_audit_report["boundary_coverage_in_dataset"]
        for key in ("halt_T=50", "halt_T=51", "halt_T=200", "halt_T=201", "halt_T=1000", "step_limit_1000"):
            assert bc[key] > 0, f"Expected boundary coverage for {key} in pilot_v2"

    def test_pilot_v2_zero_leakage_grouped_splits(self, v2_split_manifest):
        lc = v2_split_manifest["leakage_checks"]
        assert lc["zero_leakage_verified"] is True
        assert lc["machine_id_overlap"] == 0
        assert lc["lineage_id_overlap"] == 0
        assert lc["fingerprint_overlap"] == 0
        assert lc["behavioral_signature_overlap"] == 0
        assert v2_split_manifest["class_coverage_passed"] is True

        total_machines = sum(
            v2_split_manifest["splits"][sp]["machine_count"] for sp in SPLIT_NAMES
        )
        total_runs = sum(
            v2_split_manifest["splits"][sp]["run_count"] for sp in SPLIT_NAMES
        )
        assert total_machines == 1000
        assert total_runs == 5000

        for sp in SPLIT_NAMES:
            st = v2_split_manifest["splits"][sp]
            assert st["active_after_10_count"] >= 400
            for b in (50, 200, 1000):
                b_act = st["class_balance_active_after_10"][f"budget_{b}"]
                assert b_act["positive"] >= 60
                assert b_act["negative"] >= 60

    def test_pilot_v2_csv_export_leak_free_and_complete(self):
        summary = export_dataset_to_csv(PILOT_V2_DIR)
        assert summary["total_rows"] == 5000
        assert summary["active_after_10_rows"] + summary["early_halt_rows"] == 5000
        assert (PILOT_V2_DIR / "features_and_labels.csv").exists()
        assert (PILOT_V2_DIR / "features_active_after_10.csv").exists()
        # Only machine_id is included for grouping; no stop_reason, halt_step, executed_steps, family, or lineage_id
        forbidden_in_csv = (set(CSV_HEADER) - {"machine_id", "halt_by_50", "halt_by_200", "halt_by_1000"}) & FORBIDDEN_LEAKAGE_KEYS
        assert not forbidden_in_csv


class TestFeatureExtractorAndAntiLeakage:
    """Tests exact feature protocol columns, parity, and anti-leakage invariants."""

    def test_feature_columns_and_order_match_spec(self):
        assert len(STATIC_FEATURE_COLUMNS) == 9
        assert len(PREFIX_FEATURE_COLUMNS) == 5
        assert len(ALL_FEATURE_COLUMNS) == 14
        assert not (set(ALL_FEATURE_COLUMNS) & FORBIDDEN_LEAKAGE_KEYS)

    def test_feature_parity_between_step10_and_step1000_trace10(self):
        machine = TuringMachine(
            states=[
                State(id="q0", name="q0"),
                State(id="q1", name="q1"),
                State(id="qhalt", name="qhalt"),
            ],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "□"],
            blank_symbol="□",
            start_state="q0",
            final_states=["qhalt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q1", write="0", move="R"),
                Transition(from_state="q1", read="0", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="□", to_state="qhalt", write="□", move="R"),
                Transition(from_state="q1", read="□", to_state="qhalt", write="□", move="R"),
            ],
        )
        inp = "10" * 20  # 40 chars, runs > 10 steps

        # Online extraction (simulates only 10 steps)
        online_vec = extract_feature_vector(machine, inp)

        # Offline extraction from a 1000-step run with trace_limit=10
        full_sim = simulate(machine, inp, step_limit=1000, trace_limit=10)
        assert full_sim.steps == 41
        assert len(full_sim.trace) == 10
        offline_vec = extract_feature_vector(
            machine, inp, precomputed_trace=full_sim.trace
        )

        assert online_vec == offline_vec
        feats = extract_features(machine, inp)
        assert feats["state_count"] == 3.0
        assert feats["tape_alphabet_size"] == 3.0
        assert feats["final_reachable"] == 1.0
        assert feats["input_length"] == 40.0
        assert feats["input_symbol_diversity"] == 1.0
        assert feats["prefix_states_visited"] == 2.0
        assert feats["prefix_head_displacement"] == 10.0
        assert feats["prefix_tape_span"] == 11.0
        assert feats["prefix_symbol_changes"] == 10.0
        assert feats["prefix_rule_repeats"] == 8.0

    def test_anti_leakage_rejects_trace_beyond_10_steps(self):
        machine = TuringMachine(
            states=[State(id="q0", name="q0"), State(id="qhalt", name="qhalt")],
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
        unbounded_sim = simulate(machine, "1" * 15, step_limit=100, trace_limit=15)
        with pytest.raises(ValueError, match="Anti-leakage violation"):
            extract_prefix_features_from_trace("q0", unbounded_sim.trace)

    def test_observe_prefix_separates_early_halts_from_active_runs(self):
        machine = TuringMachine(
            states=[State(id="q0", name="q0"), State(id="qhalt", name="qhalt")],
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
        early = observe_prefix_and_extract(machine, "1" * 5)  # Halts at step 6 <= 10
        assert early["observed_early_halt"] is True
        assert early["prefix_steps_executed"] == 6
        assert early["exact_early_labels"] == {
            "halt_by_50": 1,
            "halt_by_200": 1,
            "halt_by_1000": 1,
        }

        active = observe_prefix_and_extract(machine, "1" * 10)  # Halts at step 11 > 10
        assert active["observed_early_halt"] is False
        assert active["prefix_steps_executed"] == 10
        assert active["exact_early_labels"] is None


class TestPilotV2ModelBundleAndMonotonicPredictor:
    """Tests trained pilot_v2 model bundle loading and monotonic multi-budget inference."""

    def test_pilot_v2_bundle_loads_and_enforces_monotonic_predictions(self):
        models_dir = Path("models/pilot_v2")
        assert (models_dir / "manifest.json").exists()
        bundle = load_model_bundle(models_dir)

        machine = TuringMachine(
            states=[State(id="q0", name="q0"), State(id="qhalt", name="qhalt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "□"],
            blank_symbol="□",
            start_state="q0",
            final_states=["qhalt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="0", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="□", to_state="qhalt", write="□", move="R"),
            ],
        )

        # Observed early halt (<= 10 steps)
        early_preds = predict_all_budgets(machine, "101", bundle)
        for b in (50, 200, 1000):
            assert early_preds[b]["source"] == "observed"
            assert early_preds[b]["predicted_halted_within_limit"] is True

        # Active after 10 steps -> model predictions with monotonic ordering
        active_preds = predict_all_budgets(machine, "1" * 60, bundle)
        for b in (50, 200, 1000):
            assert active_preds[b]["source"] == "model"
            assert predict_bounded(machine, "1" * 60, b, bundle)["source"] == "model"

        scores = [active_preds[b]["halt_score"] for b in (50, 200, 1000)]
        labels = [int(active_preds[b]["predicted_halted_within_limit"]) for b in (50, 200, 1000)]
        assert scores == sorted(scores)
        assert labels == sorted(labels)
