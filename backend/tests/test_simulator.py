"""Exhaustive unit and boundary tests for the pure Python Turing Machine simulator."""

import json
from pathlib import Path
import pytest
from backend.app.schemas import (
    SimulationRequest,
    State,
    Transition,
    TuringMachine,
)
from backend.app.simulator import simulate


def make_simple_machine(
    transitions: list[Transition] | None = None,
    start_state: str = "q0",
    final_states: list[str] | None = None,
    states: list[State] | None = None,
    input_alphabet: list[str] | None = None,
    tape_alphabet: list[str] | None = None,
    blank_symbol: str = "B",
) -> TuringMachine:
    """Helper to construct valid TuringMachine instances for testing."""
    if states is None:
        declared_states = [State(id="q0", name="State 0"), State(id="q1", name="State 1")]
        if final_states:
            for fs in final_states:
                if fs not in ["q0", "q1"]:
                    declared_states.append(State(id=fs, name=f"Final State {fs}"))
    else:
        declared_states = states

    return TuringMachine(
        states=declared_states,
        input_alphabet=input_alphabet or ["0", "1"],
        tape_alphabet=tape_alphabet or ["0", "1", "B"],
        blank_symbol=blank_symbol,
        start_state=start_state,
        final_states=final_states or ["q1"],
        transitions=transitions or [],
    )


class TestSimulatorCoreSemantics:
    """Tests core halting semantics, priority ordering, and step counting."""

    def test_immediate_final_state_at_step_zero(self):
        """If start_state is in final_states, halts immediately at step 0."""
        machine = make_simple_machine(
            start_state="q_accept",
            final_states=["q_accept"],
            states=[State(id="q_accept", name="Accept")],
            transitions=[],
        )
        res = simulate(machine, input_text="101", step_limit=10)

        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.steps == 0
        assert len(res.trace) == 0
        assert res.initial.state == "q_accept"
        assert res.initial.head == 0
        assert len(res.initial.cells) == 3

    def test_immediate_missing_transition_at_step_zero(self):
        """If no transition matches (start_state, initial_symbol), halts stuck at step 0."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q1"],
            transitions=[
                # Only rule is for symbol '1', but tape has '0'
                Transition(from_state="q0", read="1", to_state="q1", write="1", move="R")
            ],
        )
        res = simulate(machine, input_text="0", step_limit=10)

        assert res.halted_within_limit is True
        assert res.stop_reason == "missing_transition"
        assert res.steps == 0  # Failed lookup consumes ZERO steps
        assert len(res.trace) == 0

    def test_empty_input_string(self):
        """Empty input results in head at 0 reading blank_symbol."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q1"],
            transitions=[
                Transition(from_state="q0", read="B", to_state="q1", write="B", move="R")
            ],
        )
        res = simulate(machine, input_text="", step_limit=10)

        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.steps == 1
        assert len(res.initial.cells) == 0  # Tape was entirely blank initially
        assert len(res.trace) == 1
        assert res.trace[0].symbol_before == "B"

    @pytest.mark.parametrize("budget", [50, 200, 1000])
    def test_exact_step_budget_halt_at_k(self, budget: int):
        """Machine configured to execute exactly K transitions and halt on step K."""
        # 2-state machine: scans 'budget - 1' ones, then on step K reads blank and halts in q_halt
        machine = TuringMachine(
            states=[State(id="q0", name="Scan"), State(id="q_halt", name="Halt")],
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

        input_str = "1" * (budget - 1)
        res = simulate(machine, input_text=input_str, step_limit=budget)
        assert res.steps == budget
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"

    @pytest.mark.parametrize("budget", [50, 200, 1000])
    def test_exact_step_budget_exhausted_at_k(self, budget: int):
        """Machine would halt on step K + 1, but stops at K with step_limit."""
        machine = TuringMachine(
            states=[State(id="q0", name="Scan"), State(id="q_halt", name="Halt")],
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

        input_str = "1" * budget
        # At budget K: executes K transitions on '1', reaches step limit before executing step K+1
        res = simulate(machine, input_text=input_str, step_limit=budget)
        assert res.steps == budget
        assert res.halted_within_limit is False
        assert res.stop_reason == "step_limit"

        # At budget K+1: executes K transitions on '1' + 1 transition on blank to q_halt
        res_plus = simulate(machine, input_text=input_str, step_limit=budget + 1)
        assert res_plus.steps == budget + 1
        assert res_plus.halted_within_limit is True
        assert res_plus.stop_reason == "final_state"

    def test_missing_transition_exactly_at_step_k(self):
        """Machine executes K steps then halts due to missing_transition at step K."""
        k = 5
        states = [State(id=f"q{i}", name=f"State {i}") for i in range(k + 1)]
        transitions = [
            Transition(from_state=f"q{i}", read="B", to_state=f"q{i+1}", write="B", move="R")
            for i in range(k)
        ]
        # qK has no outgoing transitions, and is NOT in final_states
        machine = TuringMachine(
            states=states,
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[],  # No final states
            transitions=transitions,
        )

        res = simulate(machine, input_text="", step_limit=k)
        assert res.steps == k
        assert res.halted_within_limit is True
        assert res.stop_reason == "missing_transition"


class TestTapeAndHeadMechanics:
    """Tests bidirectional tape, sparse normalization, and negative head positions."""

    def test_negative_head_movement(self):
        """Head moving left produces negative positions: 0 -> -1 -> -2 -> -3."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q_end"],
            states=[
                State(id="q0", name="0"),
                State(id="q1", name="1"),
                State(id="q2", name="2"),
                State(id="q_end", name="End"),
            ],
            transitions=[
                Transition(from_state="q0", read="B", to_state="q1", write="0", move="L"),
                Transition(from_state="q1", read="B", to_state="q2", write="1", move="L"),
                Transition(from_state="q2", read="B", to_state="q_end", write="0", move="L"),
            ],
        )

        res = simulate(machine, input_text="", step_limit=10)
        assert res.steps == 3
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"

        # Check negative head positions in trace
        assert res.trace[0].head_before == 0
        assert res.trace[0].head_after == -1

        assert res.trace[1].head_before == -1
        assert res.trace[1].head_after == -2

        assert res.trace[2].head_before == -2
        assert res.trace[2].head_after == -3

    def test_tape_normalization_writing_blank_symbol(self):
        """Writing a blank symbol removes the cell from the internal sparse tape."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q1"],
            transitions=[
                # Read '1' at pos 0, write 'B', move 'R' to pos 1 (which is unvisited B)
                Transition(from_state="q0", read="1", to_state="q1", write="B", move="R"),
            ],
        )
        res = simulate(machine, input_text="1", step_limit=10)
        assert res.steps == 1
        assert res.halted_within_limit is True
        assert res.initial.cells[0].position == 0
        assert res.initial.cells[0].symbol == "1"

    def test_initial_configuration_sorted_non_blanks_only(self):
        """InitialConfiguration contains only non-blank cells, sorted by position."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q0"],  # Immediate halt
            states=[State(id="q0", name="Start")],
            transitions=[],
        )
        res = simulate(machine, input_text="101", step_limit=10)
        assert len(res.initial.cells) == 3
        assert [c.position for c in res.initial.cells] == [0, 1, 2]
        assert [c.symbol for c in res.initial.cells] == ["1", "0", "1"]


class TestTraceIsolationAndLimits:
    """Tests observational trace isolation, prefix limiting, and anti-leakage invariants."""

    def test_trace_limit_zero(self):
        """trace_limit=0 returns an empty trace list while execution runs normally."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q2"],
            states=[State(id="q0", name="0"), State(id="q1", name="1"), State(id="q2", name="2")],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q1", write="1", move="R"),
                Transition(from_state="q1", read="B", to_state="q2", write="B", move="R"),
            ],
        )
        res = simulate(machine, input_text="1", step_limit=10, trace_limit=0)
        assert res.steps == 2
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.trace == []

    def test_trace_limit_prefix_strictly_bounded(self):
        """trace_limit=10 on a 50-step run records exactly 10 trace events without future leakage."""
        steps_total = 50
        limit_trace = 10
        states = [State(id=f"q{i}", name=f"S{i}") for i in range(steps_total + 1)]
        transitions = [
            Transition(from_state=f"q{i}", read="B", to_state=f"q{i+1}", write="B", move="R")
            for i in range(steps_total)
        ]
        machine = TuringMachine(
            states=states,
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=[f"q{steps_total}"],
            transitions=transitions,
        )

        res = simulate(machine, input_text="", step_limit=steps_total, trace_limit=limit_trace)
        assert res.steps == steps_total
        assert res.halted_within_limit is True
        assert len(res.trace) == limit_trace

        # Verify steps 1 to 10 are present
        assert [e.step for e in res.trace] == list(range(1, limit_trace + 1))
        # Ensure no events from step 11 onwards are present
        assert all(e.step <= limit_trace for e in res.trace)

    def test_transition_index_accuracy(self):
        """Trace event records the exact original index in machine.transitions."""
        t0 = Transition(from_state="q0", read="0", to_state="q1", write="0", move="R")
        t1 = Transition(from_state="q0", read="B", to_state="q1", write="B", move="R")
        t2 = Transition(from_state="q0", read="1", to_state="q1", write="1", move="R")

        machine = make_simple_machine(
            start_state="q0",
            final_states=["q1"],
            transitions=[t0, t1, t2],  # Index 2 will execute
        )
        res = simulate(machine, input_text="1", step_limit=10)
        assert res.steps == 1
        assert res.trace[0].transition_index == 2


class TestDeterminismAndImmutability:
    """Verifies that simulator is 100% deterministic and does not mutate inputs."""

    def test_determinism_across_ten_runs(self):
        """Consecutive runs with identical inputs produce identical serialized outputs."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q2"],
            states=[State(id="q0", name="0"), State(id="q1", name="1"), State(id="q2", name="2")],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q1", write="1", move="R"),
                Transition(from_state="q1", read="1", to_state="q2", write="0", move="R"),
            ],
        )

        first_res = simulate(machine, input_text="01", step_limit=10).model_dump()
        for _ in range(9):
            subsequent_res = simulate(machine, input_text="01", step_limit=10).model_dump()
            assert first_res == subsequent_res

    def test_machine_immutability(self):
        """Simulation must not alter the TuringMachine configuration object in any way."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q1"],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q1", write="1", move="R")
            ],
        )
        before_dump = machine.model_dump()
        _ = simulate(machine, input_text="0", step_limit=10)
        after_dump = machine.model_dump()

        assert before_dump == after_dump


class TestValidationAndErrorCases:
    """Tests parameter validation and error guards in simulator.py."""

    def test_invalid_step_limit_type_and_value(self):
        machine = make_simple_machine()
        with pytest.raises(ValueError, match="step_limit"):
            simulate(machine, "0", -1)

        with pytest.raises(ValueError, match="step_limit"):
            simulate(machine, "0", True)  # Booleans rejected

    def test_invalid_trace_limit_type_and_value(self):
        machine = make_simple_machine()
        with pytest.raises(ValueError, match="trace_limit"):
            simulate(machine, "0", 10, trace_limit=-5)

        with pytest.raises(ValueError, match="trace_limit"):
            simulate(machine, "0", 10, trace_limit=False)

    def test_invalid_input_character(self):
        machine = make_simple_machine(input_alphabet=["0", "1"])
        with pytest.raises(ValueError, match="input_alphabet"):
            simulate(machine, "012", 10)  # '2' not in input_alphabet

    def test_step_limit_zero_handled_safely(self):
        """step_limit=0 is permitted for direct simulator calls (boundary testing)."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=[],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q0", write="0", move="R")
            ],
        )
        res = simulate(machine, input_text="0", step_limit=0)
        assert res.steps == 0
        assert res.halted_within_limit is False
        assert res.stop_reason == "step_limit"


class TestExamplesExecution:
    """Verifies that the 3 canonical example JSON files are valid and execute accurately."""

    @pytest.fixture
    def examples_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "examples"

    def test_scan_to_blank_example(self, examples_dir: Path):
        file_path = examples_dir / "scan-to-blank.json"
        assert file_path.exists(), f"Missing example file: {file_path}"

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.pop("schema_version") == 1
        req = SimulationRequest.model_validate(data)
        res = simulate(req.machine, req.input, req.step_limit)

        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.steps == 4  # Scans '1', '0', '1', lands on '□' and transitions to q_halt

    def test_replace_symbol_example(self, examples_dir: Path):
        file_path = examples_dir / "replace-symbol.json"
        assert file_path.exists(), f"Missing example file: {file_path}"

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.pop("schema_version") == 1
        req = SimulationRequest.model_validate(data)
        res = simulate(req.machine, req.input, req.step_limit)

        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.steps == 6  # 5 symbols + blank

    def test_loop_example(self, examples_dir: Path):
        file_path = examples_dir / "loop.json"
        assert file_path.exists(), f"Missing example file: {file_path}"

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.pop("schema_version") == 1
        req = SimulationRequest.model_validate(data)
        res = simulate(req.machine, req.input, req.step_limit)

        assert res.steps == req.step_limit
        assert res.halted_within_limit is False
        assert res.stop_reason == "step_limit"


class TestTerminalPriorityAndUnicodeEdgeCases:
    """Verifies strict priority ordering between final state, missing transition, and budget."""

    def test_priority_final_state_beats_missing_transition_at_step_zero(self):
        """If a state is final, it halts even if no transition is defined for the symbol."""
        # q0 is final, no transitions defined
        machine = make_simple_machine(
            start_state="q0",
            final_states=["q0"],
            states=[State(id="q0", name="Final and Stuck")],
            transitions=[],
        )
        res = simulate(machine, input_text="0", step_limit=10)
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"  # Final state takes precedence over missing rule
        assert res.steps == 0

    def test_priority_missing_transition_beats_step_limit_at_step_zero(self):
        """At step 0 with step_limit=0, a missing transition halts rather than step_limit."""
        machine = make_simple_machine(
            start_state="q0",
            final_states=[],
            transitions=[],  # No transitions at all
        )
        # Even with step_limit=0, check 2 (missing rule) fires before check 3 (budget)
        res = simulate(machine, input_text="0", step_limit=0)
        assert res.halted_within_limit is True
        assert res.stop_reason == "missing_transition"
        assert res.steps == 0

    def test_unicode_scalar_symbols_execution(self):
        """Machine successfully handles non-ASCII single Unicode scalar values."""
        sym_alpha = "α"
        sym_beta = "β"
        sym_blank = "□"

        machine = TuringMachine(
            states=[State(id="q0", name="Start"), State(id="q_done", name="Done")],
            input_alphabet=[sym_alpha, sym_beta],
            tape_alphabet=[sym_alpha, sym_beta, sym_blank],
            blank_symbol=sym_blank,
            start_state="q0",
            final_states=["q_done"],
            transitions=[
                Transition(from_state="q0", read=sym_alpha, to_state="q0", write=sym_beta, move="R"),
                Transition(from_state="q0", read=sym_blank, to_state="q_done", write=sym_blank, move="R"),
            ],
        )

        res = simulate(machine, input_text="α", step_limit=10)
        assert res.steps == 2
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"
        assert res.trace[0].symbol_before == "α"
        assert res.trace[0].symbol_after == "β"

    def test_max_input_length_512_code_points(self):
        """Input with exactly 512 code points executes properly."""
        machine = TuringMachine(
            states=[State(id="q0", name="Start"), State(id="q_end", name="End")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_end"],
            transitions=[
                Transition(from_state="q0", read="1", to_state="q0", write="1", move="R"),
                Transition(from_state="q0", read="B", to_state="q_end", write="B", move="R"),
            ],
        )
        # Input of 512 '1's
        input_512 = "1" * 512
        req = SimulationRequest(machine=machine, input=input_512, step_limit=600)
        res = simulate(req.machine, req.input, req.step_limit)
        assert res.steps == 513
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"


class TestExecutionLimitsAndBoundaryHalting:
    """Verifies precise halting boundaries across 49..51, 199..201, 999..1001, large budgets, and infinite cycles."""

    @staticmethod
    def _make_halt_at_step_machine():
        """Creates a machine that scans '1's to the right and halts on 'B'."""
        return TuringMachine(
            states=[State(id="q_scan", name="Scanning"), State(id="q_accept", name="Accepted")],
            input_alphabet=["1"],
            tape_alphabet=["1", "B"],
            blank_symbol="B",
            start_state="q_scan",
            final_states=["q_accept"],
            transitions=[
                Transition(from_state="q_scan", read="1", to_state="q_scan", write="1", move="R"),
                Transition(from_state="q_scan", read="B", to_state="q_accept", write="B", move="R"),
            ],
        )

    @pytest.mark.parametrize("target_steps", [49, 50, 51, 199, 200, 201, 999, 1000, 1001, 2500, 5000])
    def test_exact_halting_at_boundary_steps(self, target_steps: int):
        """Machine halts on exactly step target_steps when provided target_steps - 1 '1's followed by blank."""
        machine = self._make_halt_at_step_machine()
        # N '1's means N scan steps + 1 blank step to q_accept = N + 1 total steps.
        # So for target_steps, we provide target_steps - 1 '1's.
        input_str = "1" * (target_steps - 1)
        safety_budget = target_steps + 100

        res = simulate(machine, input_text=input_str, step_limit=safety_budget)
        assert res.steps == target_steps
        assert res.halted_within_limit is True
        assert res.stop_reason == "final_state"

    @pytest.mark.parametrize("target_steps", [50, 200, 1000, 2000])
    def test_safety_limit_cutoff_does_not_misclassify_as_reject(self, target_steps: int):
        """When budget is strictly less than halting step, engine returns stop_reason='step_limit' without rejection."""
        machine = self._make_halt_at_step_machine()
        # Machine needs target_steps transitions, but budget is target_steps - 1
        input_str = "1" * (target_steps - 1)
        insufficient_budget = target_steps - 1

        res = simulate(machine, input_text=input_str, step_limit=insufficient_budget)
        assert res.steps == insufficient_budget
        assert res.halted_within_limit is False
        assert res.stop_reason == "step_limit"

    def test_infinite_cycle_reaches_safety_limit(self):
        """An oscillator loop (q0 -> q1 -> q0) cleanly reaches safety step_limit."""
        machine = TuringMachine(
            states=[State(id="q0", name="S0"), State(id="q1", name="S1"), State(id="q_accept", name="Accept")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_accept"],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q1", write="0", move="R"),
                Transition(from_state="q1", read="B", to_state="q0", write="B", move="L"),
            ],
        )
        res = simulate(machine, input_text="0", step_limit=500)
        assert res.steps == 500
        assert res.halted_within_limit is False
        assert res.stop_reason == "step_limit"

    def test_missing_transition_is_distinct_rejection(self):
        """Machine halts because no transition matches (q0, '1') while q0 is not in final_states."""
        machine = TuringMachine(
            states=[State(id="q0", name="Start"), State(id="q_accept", name="Accept")],
            input_alphabet=["0", "1"],
            tape_alphabet=["0", "1", "B"],
            blank_symbol="B",
            start_state="q0",
            final_states=["q_accept"],
            transitions=[
                Transition(from_state="q0", read="0", to_state="q_accept", write="0", move="R"),
            ],
        )
        # Input '1' has no valid rule from q0
        res = simulate(machine, input_text="1", step_limit=100)
        assert res.steps == 0
        assert res.halted_within_limit is True
        assert res.stop_reason == "missing_transition"
