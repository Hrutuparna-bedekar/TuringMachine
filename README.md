# Turing Machine Simulator · Backend & Simulation Engine

A deterministic, high-performance, stateless Turing Machine simulation engine and REST API built in Python with FastAPI and Pydantic v2.

---

## 1. Overview

This package delivers the backend core for the Turing Machine platform. It provides:
1. **Pure Python Simulation Engine (`simulator.py`)**: A framework-independent, deterministic engine featuring an unbounded bidirectional sparse tape, exact step counting, and observational trace isolation.
2. **Pydantic v2 Data Contracts (`schemas.py`)**: Strict, validated schemas for states, alphabets, transitions, simulation requests, and execution traces.
3. **FastAPI Application (`main.py`)**: An asynchronous REST API with CORS support, 256 KiB request body protection, health checks, and simulation execution endpoints.
4. **Verified Examples (`examples/`)**: Complete, runnable JSON configurations for standard Turing Machine patterns.
5. **Comprehensive Test Suite (`backend/tests/`)**: 45 exhaustive unit, boundary, priority, tape normalization, and API integration tests.

---

## 2. Architecture & Module Responsibilities

```text
backend/app/
├── schemas.py    # Authoritative Pydantic models, semantic invariants, input guards
├── simulator.py  # Pure Python simulation logic (NO web framework dependencies)
└── main.py       # FastAPI application, ASGI request-size middleware, CORS, endpoints
```

- **`schemas.py`**: Validates machine structures (unique states, alphabet subsets, no outgoing transitions from final states, strict determinism, and single Unicode code points).
- **`simulator.py`**: Executes deterministic Turing Machine transitions. Operates on a sparse dictionary tape (`dict[int, str]`), indexes transitions for $O(1)$ lookup, and strictly enforces terminal evaluation ordering.
- **`main.py`**: Wraps the simulator into a REST API. Enforces a 256 KiB body limit at the ASGI level and translates validation errors into structured HTTP 422 responses.

---

## 3. Technology Stack & Python Version

- **Python**: 3.11+ (verified on Python 3.14)
- **FastAPI**: >= 0.115.0
- **Pydantic**: >= 2.9.0 (v2)
- **Uvicorn**: >= 0.30.0
- **Pytest**: >= 8.0.0
- **HTTPX**: >= 0.27.0

---

## 4. Local Installation Instructions

Install dependencies locally using pip:

```bash
# Runtime dependencies
pip install -r backend/requirements.txt

# Development and testing dependencies
pip install -r backend/requirements-dev.txt
```

---

## 5. Starting the Backend API

Run the Uvicorn server locally from the project root:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server will be accessible at:
- **Base URL**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Documentation**: `http://127.0.0.1:8000/docs`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

---

## 6. API Endpoints

### 6.1 `GET /api/health`
Health check and readiness endpoint.

- **Request**: No body required.
- **Response** (`200 OK`):
  ```json
  {
    "status": "ok"
  }
  ```

---

### 6.2 `POST /api/simulate`
Simulates a deterministic Turing Machine on an input string.

- **Request Headers**: `Content-Type: application/json`
- **Request Body Limits**: Maximum payload size is **256 KiB (262,144 bytes)**. Requests exceeding this limit return `HTTP 413 Content Too Large`.
- **Validation**: Strict integer check on `step_limit` (1..1000). All input characters must belong to `machine.input_alphabet`.

#### Example Request Payload
```json
{
  "machine": {
    "states": [
      {"id": "q_scan", "name": "Scan Input"},
      {"id": "q_halt", "name": "Accepting State"}
    ],
    "input_alphabet": ["0", "1"],
    "tape_alphabet": ["0", "1", "□"],
    "blank_symbol": "□",
    "start_state": "q_scan",
    "final_states": ["q_halt"],
    "transitions": [
      {"from_state": "q_scan", "read": "0", "to_state": "q_scan", "write": "0", "move": "R"},
      {"from_state": "q_scan", "read": "1", "to_state": "q_scan", "write": "1", "move": "R"},
      {"from_state": "q_scan", "read": "□", "to_state": "q_halt", "write": "□", "move": "R"}
    ]
  },
  "input": "101",
  "step_limit": 50
}
```

#### Example Response (`200 OK`)
```json
{
  "halted_within_limit": true,
  "stop_reason": "final_state",
  "steps": 4,
  "initial": {
    "state": "q_scan",
    "head": 0,
    "cells": [
      {"position": 0, "symbol": "1"},
      {"position": 1, "symbol": "0"},
      {"position": 2, "symbol": "1"}
    ]
  },
  "trace": [
    {
      "step": 1,
      "transition_index": 1,
      "state_before": "q_scan",
      "state_after": "q_scan",
      "head_before": 0,
      "head_after": 1,
      "symbol_before": "1",
      "symbol_after": "1"
    },
    {
      "step": 2,
      "transition_index": 0,
      "state_before": "q_scan",
      "state_after": "q_scan",
      "head_before": 1,
      "head_after": 2,
      "symbol_before": "0",
      "symbol_after": "0"
    },
    {
      "step": 3,
      "transition_index": 1,
      "state_before": "q_scan",
      "state_after": "q_scan",
      "head_before": 2,
      "head_after": 3,
      "symbol_before": "1",
      "symbol_after": "1"
    },
    {
      "step": 4,
      "transition_index": 2,
      "state_before": "q_scan",
      "state_after": "q_halt",
      "head_before": 3,
      "head_after": 4,
      "symbol_before": "□",
      "symbol_after": "□"
    }
  ]
}
```

---

## 7. Simulation Semantics & Invariants

### 7.1 Tape Representation
- Tape is represented as a sparse dictionary (`dict[int, str]`).
- Unvisited cells return `blank_symbol`.
- Writing `blank_symbol` deletes the key, keeping storage normalized.
- Negative head positions (moving left from 0) are natively supported.

### 7.2 Terminal Condition Priority
At step 0 and after every executed transition, the simulator evaluates conditions in this **exact priority order**:

1. **Priority 1: `final_state`**
   If `current_state in machine.final_states`, simulation stops immediately.
   `halted_within_limit = True`, `stop_reason = "final_state"`.
2. **Priority 2: `missing_transition`**
   If no transition matches `(current_state, read_symbol)`, the machine is stuck.
   `halted_within_limit = True`, `stop_reason = "missing_transition"`.
   *Failed lookups consume 0 steps.*
3. **Priority 3: `step_limit`**
   If a matching transition exists but `steps == step_limit`, budget is exhausted.
   `halted_within_limit = False`, `stop_reason = "step_limit"`.
4. **Priority 4: Execute Transition**
   Executes transition, updates head, writes tape, and increments `steps += 1`.

### 7.3 Step-Limit Behaviour
- An execution budget $K$ permits at most $K$ executed transitions.
- Reaching a final state or encountering an undefined transition on the $K$-th transition counts as `halted_within_limit = True`.

### 7.4 Trace-Limit & Data Isolation
- `trace_limit=None`: Complete trace of all executed transitions.
- `trace_limit=0`: No trace recorded (maximum execution speed).
- `trace_limit=N`: Records at most the first $N$ events (`min(N, steps)`).
- **Anti-Leakage Guarantee**: Trace limiting only restricts observation; it never affects execution semantics or step counts. No future transitions beyond step $N$ ever leak into the response.

---

## 8. Direct Python Usage (Independent Module Integration)

The simulator can be imported directly without starting any HTTP server or web dependencies. This is the recommended interface for offline ML batch processing:

```python
from backend.app.schemas import TuringMachine, State, Transition
from backend.app.simulator import simulate

# 1. Define machine
machine = TuringMachine(
    states=[State(id="q0", name="Start"), State(id="q_halt", name="Halt")],
    input_alphabet=["0", "1"],
    tape_alphabet=["0", "1", "B"],
    blank_symbol="B",
    start_state="q0",
    final_states=["q_halt"],
    transitions=[
        Transition(from_state="q0", read="1", to_state="q_halt", write="0", move="R"),
    ],
)

# 2. Run deterministic simulation
result = simulate(
    machine=machine,
    input_text="1",
    step_limit=100,
    trace_limit=10,  # Optional: record at most first 10 events
)

print("Halted:", result.halted_within_limit)
print("Stop Reason:", result.stop_reason)
print("Steps Executed:", result.steps)
```

---

## 9. Running the Test Suite Locally

Run pytest from the repository root:

```bash
pytest backend/tests -v
```

All 45 tests validate:
- Step 0 immediate halts (final state and missing transition).
- Exact budget boundaries ($K = 50, 200, 1000$).
- Negative head positions and tape normalization.
- Trace limiting and anti-leakage invariants.
- Determinism and machine immutability.
- 256 KiB request body limit (declared and streamed).
- CORS headers and HTTP 422 validation.
- All three example configurations in `examples/`.

---

## 10. Local Project Directory Tree

```text
Toc/
├── backend/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── __init__.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   ├── simulator.py
│   │   └── main.py
│   └── tests/
│       ├── __init__.py
│       ├── test_simulator.py
│       └── test_api.py
├── examples/
│   ├── scan-to-blank.json
│   ├── replace-symbol.json
│   └── loop.json
├── pytest.ini
└── README.md
```
