"""Canonical Pydantic v2 data models and validation contracts.

This module defines the strict schemas for Turing Machine definitions, simulation
requests, responses, and execution trace structures.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _check_single_code_point(v: str, field_desc: str) -> str:
    """Validate that a string consists of exactly one valid Unicode scalar value."""
    if not isinstance(v, str):
        raise ValueError(f"{field_desc} must be a string, got {type(v).__name__}")
    if len(v) != 1:
        raise ValueError(f"{field_desc} must be exactly 1 Unicode code point, got length {len(v)}")
    cp = ord(v)
    if 0xD800 <= cp <= 0xDFFF:
        raise ValueError(f"{field_desc} cannot be a surrogate code point (U+{cp:04X})")
    return v


class State(BaseModel):
    """Represents a discrete state in the Turing Machine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(..., min_length=1, max_length=64, description="Unique state identifier")
    name: str = Field(..., min_length=1, max_length=64, description="Human-readable state name")


class Transition(BaseModel):
    """Represents a deterministic transition rule in the Turing Machine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    from_state: str = Field(..., min_length=1, max_length=64, description="Source state ID")
    read: str = Field(..., description="Tape symbol required to trigger this transition")
    to_state: str = Field(..., min_length=1, max_length=64, description="Target state ID")
    write: str = Field(..., description="Tape symbol written to current cell")
    move: Literal["L", "R"] = Field(..., description="Direction to move tape head: 'L' or 'R'")

    @field_validator("read")
    @classmethod
    def validate_read_symbol(cls, v: str) -> str:
        return _check_single_code_point(v, "Transition read symbol")

    @field_validator("write")
    @classmethod
    def validate_write_symbol(cls, v: str) -> str:
        return _check_single_code_point(v, "Transition write symbol")


class TuringMachine(BaseModel):
    """Complete, self-contained, validated specification of a Deterministic Turing Machine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    states: list[State] = Field(..., min_length=1, max_length=64, description="List of discrete states")
    input_alphabet: list[str] = Field(
        ..., min_length=1, max_length=32, description="Alphabet of symbols allowed in input string"
    )
    tape_alphabet: list[str] = Field(
        ..., min_length=1, max_length=32, description="Complete alphabet of symbols allowed on tape"
    )
    blank_symbol: str = Field(..., description="Designated blank symbol on the tape")
    start_state: str = Field(..., min_length=1, max_length=64, description="Initial state ID")
    final_states: list[str] = Field(default_factory=list, description="List of accepting/terminal state IDs")
    transitions: list[Transition] = Field(
        default_factory=list, max_length=1024, description="List of deterministic transition rules"
    )

    @field_validator("blank_symbol")
    @classmethod
    def validate_blank_symbol(cls, v: str) -> str:
        return _check_single_code_point(v, "Blank symbol")

    @field_validator("input_alphabet")
    @classmethod
    def validate_input_alphabet(cls, v: list[str]) -> list[str]:
        seen = set()
        for sym in v:
            _check_single_code_point(sym, "Input alphabet symbol")
            if sym in seen:
                raise ValueError(f"Duplicate symbol in input_alphabet: {sym!r}")
            seen.add(sym)
        return v

    @field_validator("tape_alphabet")
    @classmethod
    def validate_tape_alphabet(cls, v: list[str]) -> list[str]:
        seen = set()
        for sym in v:
            _check_single_code_point(sym, "Tape alphabet symbol")
            if sym in seen:
                raise ValueError(f"Duplicate symbol in tape_alphabet: {sym!r}")
            seen.add(sym)
        return v

    @model_validator(mode="after")
    def validate_machine_semantics(self) -> "TuringMachine":
        # 1. State ID uniqueness
        state_ids = set()
        for s in self.states:
            if s.id in state_ids:
                raise ValueError(f"Duplicate state ID found: {s.id!r}")
            state_ids.add(s.id)

        # 2. Start state validity
        if self.start_state not in state_ids:
            raise ValueError(f"start_state {self.start_state!r} does not exist in declared states")

        # 3. Final states uniqueness & validity
        final_state_set = set()
        for f in self.final_states:
            if f in final_state_set:
                raise ValueError(f"Duplicate final state ID found: {f!r}")
            if f not in state_ids:
                raise ValueError(f"final_state {f!r} does not exist in declared states")
            final_state_set.add(f)

        # 4. Alphabets & Blank symbol relationships
        input_set = set(self.input_alphabet)
        tape_set = set(self.tape_alphabet)

        if self.blank_symbol not in tape_set:
            raise ValueError(f"blank_symbol {self.blank_symbol!r} must be in tape_alphabet")

        if self.blank_symbol in input_set:
            raise ValueError(f"blank_symbol {self.blank_symbol!r} must NOT be in input_alphabet")

        if not input_set.issubset(tape_set):
            missing = input_set - tape_set
            raise ValueError(f"input_alphabet must be a subset of tape_alphabet; missing: {missing!r}")

        # 5. Transition integrity & determinism
        transition_keys = set()
        for idx, t in enumerate(self.transitions):
            if t.from_state not in state_ids:
                raise ValueError(f"Transition {idx} references unknown from_state: {t.from_state!r}")
            if t.to_state not in state_ids:
                raise ValueError(f"Transition {idx} references unknown to_state: {t.to_state!r}")
            if t.read not in tape_set:
                raise ValueError(f"Transition {idx} reads symbol {t.read!r} not in tape_alphabet")
            if t.write not in tape_set:
                raise ValueError(f"Transition {idx} writes symbol {t.write!r} not in tape_alphabet")

            # Final states cannot have outgoing transitions
            if t.from_state in final_state_set:
                raise ValueError(
                    f"Transition {idx} has from_state {t.from_state!r} which is a final state. "
                    "Final states must have no outgoing transitions."
                )

            # Determinism: at most one transition per (from_state, read)
            key = (t.from_state, t.read)
            if key in transition_keys:
                raise ValueError(
                    f"Non-deterministic machine: duplicate transition rule for state {t.from_state!r} "
                    f"and symbol {t.read!r} at transition index {idx}"
                )
            transition_keys.add(key)

        return self


class SimulationRequest(BaseModel):
    """Wire contract for POST /api/simulate requests."""

    model_config = ConfigDict(extra="forbid", strict=True)

    machine: TuringMachine
    input: str = Field(..., max_length=512, description="Input string written starting at cell 0")
    step_limit: int = Field(..., description="Maximum transitions allowed to execute (1..1000)")

    @field_validator("step_limit")
    @classmethod
    def validate_step_limit(cls, v: int) -> int:
        # Strictly forbid booleans (bool is a subclass of int in Python)
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("step_limit must be an integer, booleans/floats are rejected")
        if v < 0 or v > 1000:
            raise ValueError(f"step_limit must be between 0 and 1000 inclusive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_input_against_alphabet(self) -> "SimulationRequest":
        input_set = set(self.machine.input_alphabet)
        for idx, char in enumerate(self.input):
            cp = ord(char)
            if 0xD800 <= cp <= 0xDFFF:
                raise ValueError(f"Input character at index {idx} is an invalid surrogate code point (U+{cp:04X})")
            if char not in input_set:
                raise ValueError(
                    f"Input character {char!r} at index {idx} does not belong to the machine input_alphabet"
                )
        return self


class TapeCell(BaseModel):
    """Represents a single non-blank cell on the Turing Machine tape."""

    model_config = ConfigDict(extra="forbid", strict=True)

    position: int = Field(..., description="Signed integer tape position")
    symbol: str = Field(..., description="Symbol stored at this position")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        return _check_single_code_point(v, "TapeCell symbol")


class InitialConfiguration(BaseModel):
    """Snapshot of initial machine configuration before any transitions occur."""

    model_config = ConfigDict(extra="forbid", strict=True)

    state: str = Field(..., description="Initial state ID")
    head: int = Field(default=0, description="Initial head position (always 0)")
    cells: list[TapeCell] = Field(
        default_factory=list, description="Non-blank cells on tape initially, sorted by position"
    )


class TraceEvent(BaseModel):
    """Observational record of a single executed transition."""

    model_config = ConfigDict(extra="forbid", strict=True)

    step: int = Field(..., ge=1, description="1-indexed transition counter")
    transition_index: int = Field(
        ..., ge=0, description="0-indexed position of rule in machine.transitions"
    )
    state_before: str = Field(..., description="State prior to transition")
    state_after: str = Field(..., description="State after transition")
    head_before: int = Field(..., description="Head position prior to transition")
    head_after: int = Field(..., description="Head position after movement")
    symbol_before: str = Field(..., description="Symbol read from tape")
    symbol_after: str = Field(..., description="Symbol written to tape")


class SimulationResponse(BaseModel):
    """Wire contract for simulation outcomes."""

    model_config = ConfigDict(extra="forbid", strict=True)

    halted_within_limit: bool = Field(..., description="True if machine entered terminal state within step_limit")
    stop_reason: Literal["final_state", "missing_transition", "step_limit"] = Field(
        ..., description="Specific operational reason why simulation stopped"
    )
    steps: int = Field(..., ge=0, description="Total number of transitions executed")
    initial: InitialConfiguration = Field(..., description="Initial configuration snapshot")
    trace: list[TraceEvent] = Field(..., description="Chronological record of executed transitions")


class NodeLayout(BaseModel):
    """Visual coordinates for a state node in the graph editor canvas."""

    model_config = ConfigDict(extra="forbid", strict=True)

    x: float = Field(..., description="Finite X coordinate on canvas")
    y: float = Field(..., description="Finite Y coordinate on canvas")

    @field_validator("x", "y")
    @classmethod
    def validate_finite_coordinate(cls, v: float) -> float:
        import math
        if not math.isfinite(v):
            raise ValueError(f"Coordinate must be finite, got {v}")
        return v


class MachineExportEnvelope(BaseModel):
    """Versioned JSON export and import envelope for machine persistence.

    Conforms strictly to PROJECT_PLAN schema_version: 1 and optional layout keyed by state ID.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = Field(
        default=1, description="Strictly integer version 1"
    )
    machine: TuringMachine = Field(..., description="Canonical machine configuration")
    layout: dict[str, NodeLayout] | None = Field(
        default=None, description="Optional node positions keyed by state ID"
    )

    @model_validator(mode="after")
    def validate_layout_references(self) -> "MachineExportEnvelope":
        if self.layout is not None:
            state_ids = {s.id for s in self.machine.states}
            for state_id in self.layout:
                if state_id not in state_ids:
                    raise ValueError(
                        f"Dangling layout entry: state ID {state_id!r} does not exist in machine states"
                    )
        return self
