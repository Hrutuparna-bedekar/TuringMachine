"""ML labeling boundary fixtures and envelope validation tests.

Verifies the exact requirements and boundary fixture table specified in Section 3
of DATA_AND_ML_PLAN.md to guarantee 100% integration readiness for the ML team.
"""

import pytest
from backend.app.schemas import (
    MachineExportEnvelope,
    NodeLayout,
    State,
    Transition,
    TuringMachine,
)
from backend.app.simulator import simulate


def derive_ml_labels(machine: TuringMachine, input_text: str) -> dict[str, int]:
    """Demonstrates and tests the ML labeling logic specified in DATA_AND_ML_PLAN.md Section 3.

    Runs simulate with budget 1000.
    - If machine halts at step T <= 1000:
        halt_by_50 = 1 if T <= 50 else 0
        halt_by_200 = 1 if T <= 200 else 0
        halt_by_1000 = 1 if T <= 1000 else 0
    - If machine is still running at 1000:
        halt_by_50 = 0, halt_by_200 = 0, halt_by_1000 = 0
    """
    res = simulate(machine, input_text, step_limit=1000, trace_limit=10)
    if res.halted_within_limit:
        t = res.steps
        return {
            "halt_by_50": 1 if t <= 50 else 0,
            "halt_by_200": 1 if t <= 200 else 0,
            "halt_by_1000": 1 if t <= 1000 else 0,
            "steps": t,
            "stop_reason": res.stop_reason,
            "trace_length": len(res.trace),
        }
    else:
        return {
            "halt_by_50": 0,
            "halt_by_200": 0,
            "halt_by_1000": 0,
            "steps": res.steps,
            "stop_reason": res.stop_reason,
            "trace_length": len(res.trace),
        }


class TestMLLabelingFixtures:
    """Exact verification of the 5 boundary fixtures from DATA_AND_ML_PLAN.md."""

    def test_fixture_1_t_zero_starts_in_final_or_no_matching_rule(self):
        """Starts in final state or no rule: T=0 -> labels 1, 1, 1."""
        # Case A: starts in final state
        m_final = TuringMachine(
            states=[State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q_halt",
            final_states=["q_halt"],
            transitions=[],
        )
        labels_a = derive_ml_labels(m_final, "0")
        assert labels_a["halt_by_50"] == 1
        assert labels_a["halt_by_200"] == 1
        assert labels_a["halt_by_1000"] == 1
        assert labels_a["steps"] == 0
        assert labels_a["stop_reason"] == "final_state"

        # Case B: starts with no matching rule
        m_stuck = TuringMachine(
            states=[State(id="q0", name="Start")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[],
            transitions=[],
        )
        labels_b = derive_ml_labels(m_stuck, "0")
        assert labels_b["halt_by_50"] == 1
        assert labels_b["halt_by_200"] == 1
        assert labels_b["halt_by_1000"] == 1
        assert labels_b["steps"] == 0
        assert labels_b["stop_reason"] == "missing_transition"

    def test_fixture_2_halts_after_50th_transition(self):
        """Halts after 50th transition (T=50) -> labels 1, 1, 1."""
        # 2 states: scans 49 '1's then on blank enters q_halt (total steps = 50)
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_halt", write="B", move="R"),
            ],
        )
        labels = derive_ml_labels(m, "1" * 49)
        assert labels["steps"] == 50
        assert labels["halt_by_50"] == 1
        assert labels["halt_by_200"] == 1
        assert labels["halt_by_1000"] == 1

    def test_fixture_3_halts_after_51st_transition(self):
        """Halts after 51st transition (T=51) -> labels 0, 1, 1."""
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_halt", write="B", move="R"),
            ],
        )
        labels = derive_ml_labels(m, "1" * 50)  # 50 ones + 1 blank = 51 steps
        assert labels["steps"] == 51
        assert labels["halt_by_50"] == 0
        assert labels["halt_by_200"] == 1
        assert labels["halt_by_1000"] == 1

    def test_fixture_4_halts_after_1000th_transition(self):
        """Halts after 1000th transition (T=1000) -> labels 0, 0, 1."""
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_halt", write="B", move="R"),
            ],
        )
        labels = derive_ml_labels(m, "1" * 999)  # 999 ones + 1 blank = 1000 steps
        assert labels["steps"] == 1000
        assert labels["halt_by_50"] == 0
        assert labels["halt_by_200"] == 0
        assert labels["halt_by_1000"] == 1

    def test_fixture_5_still_running_after_1000_transitions(self):
        """Still has a matching rule after 1000 transitions -> labels 0, 0, 0, stop_reason=step_limit."""
        m = TuringMachine(
            states=[State(id="q0", name="Loop")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[],
            transitions=[
                # Infinite right scan across blanks
                Transition(from_state="q0", read="B", to_state="q0", write="B", move="R"),
            ],
        )
        labels = derive_ml_labels(m, "")
        assert labels["steps"] == 1000
        assert labels["stop_reason"] == "step_limit"
        assert labels["halt_by_50"] == 0
        assert labels["halt_by_200"] == 0
        assert labels["halt_by_1000"] == 0

    def test_prefix_feature_trace_limit_isolation(self):
        """For ML labels and prefix features, step_limit=1000, trace_limit=10 captures <= 10 events."""
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_halt", write="B", move="R"),
            ],
        )
        # Runs 500 steps
        res = simulate(m, "1" * 499, step_limit=1000, trace_limit=10)
        assert res.steps == 500
        assert len(res.trace) == 10
        assert res.trace[0].step == 1
        assert res.trace[-1].step == 10

    def test_exact_simulation_timing_trace_limit_zero(self):
        """trace_limit=0 captures zero events for high-throughput timing benchmarks."""
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q_halt", name="Halt")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_halt"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_halt", write="B", move="R"),
            ],
        )
        res = simulate(m, "1" * 100, step_limit=1000, trace_limit=0)
        assert res.steps == 101
        assert len(res.trace) == 0


class TestMachineExportEnvelope:
    """Verifies PROJECT_PLAN JSON import/export envelope contracts."""

    def test_valid_export_envelope_with_layout(self):
        m = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q1", name="S1")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q1"],
            transitions=[],
        )
        envelope = MachineExportEnvelope(
            schema_version=1,
            machine=m,
            layout={
                "q0": NodeLayout(x=100.0, y=150.0),
                "q1": NodeLayout(x=300.0, y=150.0),
            },
        )
        dumped = envelope.model_dump()
        assert dumped["schema_version"] == 1
        assert dumped["layout"]["q0"]["x"] == 100.0

    def test_invalid_schema_version_rejected(self):
        m = TuringMachine(
            states=[State(id="q0", name="S0")],
            input_alphabet=["0"],
            tape_alphabet=["0", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[],
            transitions=[],
        )
        with pytest.raises(Exception):
            MachineExportEnvelope(schema_version=2, machine=m)  # strictly version 1

    def test_dangling_layout_id_rejected(self):
        m = TuringMachine(
            states=[State(id="q0", name="S0")],
            input_alphabet=["0"],
            tape_alphabet=["0", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[],
            transitions=[],
        )
        with pytest.raises(ValueError, match="Dangling layout entry"):
            MachineExportEnvelope(
                schema_version=1,
                machine=m,
                layout={"q_nonexistent": NodeLayout(x=0.0, y=0.0)},
            )
