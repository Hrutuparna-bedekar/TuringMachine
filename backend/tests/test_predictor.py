"""Tests for feature extraction and offline bounded prediction module."""

import pytest
from sklearn.base import BaseEstimator, ClassifierMixin
import numpy as np

from backend.app.features import (
    ALL_FEATURE_NAMES,
    PREFIX_FEATURE_NAMES,
    STATIC_FEATURE_NAMES,
    extract_all_features,
    extract_features,
    extract_prefix_features,
    extract_static_features,
    is_final_state_reachable,
)
from backend.app.predictor import predict_bounded
from backend.app.schemas import State, TraceEvent, Transition, TuringMachine
from backend.app.simulator import simulate


class DummyClassifier(BaseEstimator, ClassifierMixin):
    """Deterministic dummy classifier for unit testing predict_bounded."""

    def __init__(self, prob_class_1: float = 0.85):
        self.prob_class_1 = prob_class_1
        self.classes_ = np.array([0, 1])

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        n = len(X)
        return np.array([[1.0 - self.prob_class_1, self.prob_class_1] for _ in range(n)])

    def predict(self, X):
        return np.array([1 if self.prob_class_1 >= 0.5 else 0 for _ in range(len(X))])


class TestFeatureExtraction:
    """Verifies feature computation against mathematical definitions."""

    def test_static_features_and_reachability(self):
        # Machine with 3 states, 1 final state reachable from start
        machine = TuringMachine(
            states=[
                State(id="q0", name="Start"),
                State(id="q1", name="Mid"),
                State(id="q_halt", name="Halt"),
            ],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                # q0 -> q1 (move R)
                Transition(from_state="q0", read="0", to_state="q1", write="1", move="R"),
                # q1 -> q1 self-loop (move L)
                Transition(from_state="q1", read="0", to_state="q1", write="0", move="L"),
                # q1 -> q_halt (move R)
                Transition(from_state="q1", read="_", to_state="q_halt", write="_", move="R"),
            ],
        )

        assert is_final_state_reachable(machine) is True

        feats = extract_static_features(machine, "001")
        assert feats["state_count"] == 3.0
        assert feats["tape_alphabet_size"] == 3.0
        # denom = (3 - 1) * 3 = 6. 3 rules / 6 = 0.5
        assert feats["rule_density"] == 0.5
        assert feats["final_reachable"] == 1.0
        # 1 self loop out of 3 rules = 1/3
        assert pytest.approx(feats["self_loop_fraction"]) == 1.0 / 3.0
        # 1 left move out of 3 rules = 1/3
        assert pytest.approx(feats["left_move_fraction"]) == 1.0 / 3.0
        # 2 right moves out of 3 rules = 2/3
        assert pytest.approx(feats["right_move_fraction"]) == 2.0 / 3.0
        assert feats["input_length"] == 3.0
        assert feats["input_symbol_diversity"] == 2.0  # '0' and '1'

    def test_reachability_unreachable_final(self):
        machine = TuringMachine(
            states=[
                State(id="q0", name="Start"),
                State(id="q_halt", name="Halt"),
            ],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                # loop on q0 only
                Transition(from_state="q0", read="0", to_state="q0", write="0", move="R"),
            ],
        )
        assert is_final_state_reachable(machine) is False
        feats = extract_static_features(machine, "0")
        assert feats["final_reachable"] == 0.0

    def test_prefix_features_trace_calculations(self):
        machine = TuringMachine(
            states=[
                State(id="q0", name="S0"),
                State(id="q1", name="S1"),
                State(id="q2", name="S2"),
            ],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=[],
            transitions=[],
        )

        # Trace of 4 events
        # Step 1: q0 -> q1, head 0->1, sym '0'->'1' (rule 0)
        # Step 2: q1 -> q1, head 1->2, sym '_'->'_' (rule 1)
        # Step 3: q1 -> q2, head 2->1, sym '_'->'0' (rule 2)
        # Step 4: q2 -> q1, head 1->2, sym '1'->'1' (rule 1 repeated!)
        trace = [
            TraceEvent(
                step=1, transition_index=0, state_before="q0", state_after="q1",
                head_before=0, head_after=1, symbol_before="0", symbol_after="1"
            ),
            TraceEvent(
                step=2, transition_index=1, state_before="q1", state_after="q1",
                head_before=1, head_after=2, symbol_before="_", symbol_after="_"
            ),
            TraceEvent(
                step=3, transition_index=2, state_before="q1", state_after="q2",
                head_before=2, head_after=1, symbol_before="_", symbol_after="0"
            ),
            TraceEvent(
                step=4, transition_index=1, state_before="q2", state_after="q1",
                head_before=1, head_after=2, symbol_before="1", symbol_after="1"
            ),
        ]

        prefix = extract_prefix_features(machine, "0", trace)
        # States visited: {q0, q1, q2} -> 3
        assert prefix["prefix_states_visited"] == 3.0
        # Final head after trace: 2. Initial: 0. Displacement: 2 - 0 = 2
        assert prefix["prefix_head_displacement"] == 2.0
        # Visited positions: {0, 1, 2}. max=2, min=0 -> span = 2 - 0 + 1 = 3
        assert prefix["prefix_tape_span"] == 3.0
        # Symbol changes: event 1 ('0'->'1') and event 3 ('_'->'0') -> 2 changes
        assert prefix["prefix_symbol_changes"] == 2.0
        # Rule repeats: 4 total events, rules used = {0, 1, 2} (3 unique). repeats = 4 - 3 = 1
        assert prefix["prefix_rule_repeats"] == 1.0

    def test_feature_ordering_and_completeness(self):
        machine = TuringMachine(
            states=[State(id="q0", name="Start")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=[],
            transitions=[],
        )
        feats = extract_features(machine, "0", [])
        assert list(feats.keys()) == ALL_FEATURE_NAMES
        assert len(feats) == 14


class TestPredictBounded:
    """Verifies predict_bounded contract, observed vs model routing, and error conditions."""

    @pytest.fixture
    def mock_model_bundle(self):
        clf_50 = DummyClassifier(prob_class_1=0.75)
        clf_200 = DummyClassifier(prob_class_1=0.40)
        clf_1000 = DummyClassifier(prob_class_1=0.90)

        return {
            "models": {50: clf_50, 200: clf_200, 1000: clf_1000},
            "thresholds": {50: 0.5, 200: 0.5, 1000: 0.5},
            "model_ids": {50: "dt_50", 200: "rf_200", 1000: "mlp_1000"},
            "feature_sets": {
                50: ALL_FEATURE_NAMES,
                200: ALL_FEATURE_NAMES,
                1000: ALL_FEATURE_NAMES,
            },
        }

    def test_unsupported_budget_raises_value_error(self, mock_model_bundle):
        m = TuringMachine(
            states=[State(id="q0", name="Start")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=[],
            transitions=[],
        )
        with pytest.raises(ValueError, match="Unsupported step_limit"):
            predict_bounded(m, "0", 100, mock_model_bundle)

    def test_observed_halt_at_step_zero_final_state(self, mock_model_bundle):
        m = TuringMachine(
            states=[State(id="q0", name="Start")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=["q0"],
            transitions=[],
        )
        res = predict_bounded(m, "0", 50, mock_model_bundle)
        assert res["source"] == "observed"
        assert res["predicted_halted_within_limit"] is True
        assert res["observed_steps"] == 0
        assert res["stop_reason"] == "final_state"
        assert "model_id" not in res
        assert "halt_score" not in res

    def test_observed_halt_at_step_5(self, mock_model_bundle):
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q0", write="0", move="R"),
                Transition(from_state="q0", read="_", to_state="q_halt", write="_", move="R"),
            ],
        )
        # "0000" means 4 steps on '0', 5th step on '_' halts
        res = predict_bounded(m, "0000", 200, mock_model_bundle)
        assert res["source"] == "observed"
        assert res["predicted_halted_within_limit"] is True
        assert res["observed_steps"] == 5
        assert res["stop_reason"] == "final_state"

    def test_observed_halt_at_exact_step_10(self, mock_model_bundle):
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q0", write="0", move="R"),
                Transition(from_state="q0", read="_", to_state="q_halt", write="_", move="R"),
            ],
        )
        # "0" * 9: 9 steps on '0' + 1 step on '_' = 10 steps total
        res = predict_bounded(m, "0" * 9, 1000, mock_model_bundle)
        assert res["source"] == "observed"
        assert res["predicted_halted_within_limit"] is True
        assert res["observed_steps"] == 10
        assert res["stop_reason"] == "final_state"

    def test_model_prediction_when_active_past_step_10(self, mock_model_bundle):
        # Infinite right scanner on blank
        m = TuringMachine(
            states=[State(id="q0", name="Loop")],
            input_alphabet=["0"],
            tape_alphabet=["0", "_"],
            blank_symbol="_",
            start_state="q0",
            final_states=[],
            transitions=[
                Transition(from_state="q0", read="_", to_state="q0", write="_", move="R"),
            ],
        )
        # Budget 50: mock prob is 0.75 >= 0.5 -> predicted_halted_within_limit = True
        res_50 = predict_bounded(m, "", 50, mock_model_bundle)
        assert res_50["source"] == "model"
        assert res_50["observed_steps"] == 10
        assert res_50["model_id"] == "dt_50"
        assert res_50["halt_score"] == 0.75
        assert res_50["predicted_halted_within_limit"] is True

        # Budget 200: mock prob is 0.40 < 0.5 -> predicted_halted_within_limit = False
        res_200 = predict_bounded(m, "", 200, mock_model_bundle)
        assert res_200["source"] == "model"
        assert res_200["observed_steps"] == 10
        assert res_200["model_id"] == "rf_200"
        assert res_200["halt_score"] == 0.40
        assert res_200["predicted_halted_within_limit"] is False

