# Turing Machine Simulator & Bounded Halting Predictor

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-101%20Passed-brightgreen)](backend/tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An academic-grade, interactive **Deterministic Turing Machine (DTM) Simulator** and **Machine Learning Bounded-Halting Predictor**. Built for Theory of Computation (TOC) pedagogy, algorithmic research, and formal automata visualization.

---

## Table of Contents
- [1. Executive Overview](#1-executive-overview)
- [2. System Architecture](#2-system-architecture)
- [3. Key Features](#3-key-features)
- [4. Theoretical Foundations](#4-theoretical-foundations)
- [5. Quick Start Guide](#5-quick-start-guide)
- [6. REST API Reference](#6-rest-api-reference)
- [7. Machine Learning Bounded Halting](#7-machine-learning-bounded-halting)
- [8. Test Suites & Verification](#8-test-suites--verification)
- [9. Repository Structure](#9-repository-structure)
- [10. License & Credits](#10-license--credits)

---

## 1. Executive Overview

This application bridges formal theoretical computer science with modern engineering:
1. **Interactive Workspace**: Construct, edit, and visualize deterministic Turing machines on an interactive graph canvas featuring circular state nodes conforming to formal automata drawing standards.
2. **Deterministic Simulation Engine**: Simulates transitions over a bidirectional infinite tape with signed indexing ($-\infty \dots +\infty$) and strict deterministic execution rules up to 50,000 steps.
3. **Step-by-Step Playback & Explainability**: Forward/backward trace stepping, scrub slider, 0.5x–10x playback speeds, and real-time execution banners detailing transition rules, head positions, symbol updates, and next actions.
4. **Machine Learning Bounded-Halting Predictor**: Explores empirical prediction of finite-step halting across 50, 200, and 1,000 execution budgets using 10-step prefix observation combined with topological graph features.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Web Browser (SPA)                          │
│  React 18 · TypeScript · Vite · @xyflow/react · Modern CSS Tokens      │
│  ┌──────────────────────┬──────────────────────┬────────────────────┐  │
│  │  Machine Workspace   │  Tape Simulation     │  ML Predictor      │  │
│  │  Circular Node Graph │  Step-by-Step Replay │  Multi-Budget View │  │
│  └──────────────────────┴──────────────────────┴────────────────────┘  │
└────────────────────────────────────▲───────────────────────────────────┘
                                     │ HTTP REST / JSON
┌────────────────────────────────────▼───────────────────────────────────┐
│                        FastAPI Backend Server                          │
│  Uvicorn ASGI · Pydantic v2 · 256 KiB Streaming Guard · Static Mount  │
│  ┌──────────────────────┬──────────────────────┬────────────────────┐  │
│  │   /api/simulate      │   /api/predict       │   /api/health      │  │
│  │   Deterministic TM   │   ML Model Inference │   Readiness Probe  │  │
│  └──────────┬───────────┴──────────┬───────────┴────────────────────┘  │
└─────────────┼──────────────────────┼───────────────────────────────────┘
              ▼                      ▼
┌───────────────────────────┐ ┌──────────────────────────────────────────┐
│  Sparse Simulator Engine  │ │  Trained ML Model Bundles (Joblib)       │
│  Infinite 2-Way Tape      │ │  • halt_by_50.joblib (Random Forest)     │
│  Signed Head Coordinates  │ │  • halt_by_200.joblib (Decision Tree)    │
│  O(1) Hash Map Cells      │ │  • halt_by_1000.joblib (Random Forest)   │
└───────────────────────────┘ └──────────────────────────────────────────┘
```

---

## 3. Key Features

### 🔵 Automata Canvas & Circular Nodes
- **Standard Automata Representation**: Replaced generic rectangular boxes with 76×76px circular nodes conforming to Theory of Computation standards.
- **Formal Indicators**:
  - `START →` directional entry arrow pointing into the initial state.
  - Concentric inner ring (double circle) for accepting/final states ($q \in F$).
  - Crimson border treatment for explicit rejecting states.
  - Active pulsing amber aura tracking the active state node during live execution.
- **Self-Loop & Edge Routing**: Symmetrical handles and smooth cubic bezier curves prevent overlapping.

### 📼 Deterministic Tape Simulation
- **Bidirectional Sparse Tape**: Implemented as a hash map $T: \mathbb{Z} \to \Gamma$, supporting unboundedly negative and positive cell indices without arbitrary array truncation.
- **Configurable Safety Step Limit**: Up to **50,000 steps** with instant preset pills (`50`, `200`, `1k`, `5k`, `10k`).
- **Unified Stepping Engine**: Run Simulation and Replay use the exact same step-by-step pipeline.

### 🎓 Educational Explainability
- **Execution Banner**: Displays the exact mathematical rule applied:
  $$\delta(q_{\text{before}}, \sigma_{\text{read}}) \to (q_{\text{after}}, \sigma_{\text{write}}, D)$$
  along with cell index, symbol written, and head direction.
- **Next Action Preview**: Previews the scanned symbol under the head and the next rule scheduled to fire.
- **Theoretical Halting Badges**:
  - `ACCEPTED` (Green): Machine halted in an accepting final state ($q \in F$).
  - `REJECTED` (Crimson): Machine halted because no transition rule was defined for $(q, \sigma)$ while $q \notin F$.
  - `SAFETY LIMIT REACHED` (Amber): Execution budget exhausted.

### 🤖 Bounded Halting Predictor
- Predicts whether a given machine and input string will halt within $B \in \{50, 200, 1000\}$ execution steps.
- **Dual-Mode Inference**: If the machine halts within a 10-step prefix, the system reports direct observation; otherwise, it queries trained Random Forest and Decision Tree models with topological graph features.
- Includes a direct **Compare with Exact Simulation** button to verify model accuracy against ground truth.

### 📚 Curated Automata Library & Portability
- 9 pre-configured classical machines:
  1. *Scan to Blank*
  2. *Binary Incrementer (+1)*
  3. *Unary Addition*
  4. *Replace Symbol*
  5. *Bit Inverter*
  6. *Infinite Ping-Pong Cycle*
  7. *Binary Palindrome Checker*
  8. *Parity Detector*
  9. *Right Boundary Seeker*
- **Import / Export**: Full JSON envelope serialization (`schema_version: 1`) preserving both formal machine definitions and canvas $(x, y)$ coordinates.

---

## 4. Theoretical Foundations

### Formal 7-Tuple Definition
A Deterministic Turing Machine (DTM) is formally defined as:
$$M = (Q, \Sigma, \Gamma, \delta, q_0, \sqcup, F)$$

| Component | Description | Implementation Detail |
| :--- | :--- | :--- |
| **$Q$** | Finite, non-empty set of states | `machine.states` (Unique string IDs) |
| **$\Sigma$** | Input alphabet (excluding $\sqcup$) | `machine.input_alphabet` |
| **$\Gamma$** | Tape alphabet ($\Sigma \subset \Gamma, \sqcup \in \Gamma$) | `machine.tape_alphabet` |
| **$\delta$** | Transition function $(Q \setminus F) \times \Gamma \to Q \times \Gamma \times \{L, R\}$ | `machine.transitions` (Deterministic) |
| **$q_0$** | Initial start state ($q_0 \in Q$) | `machine.start_state` |
| **$\sqcup$** | Designated blank symbol | `machine.blank_symbol` (Default `□`) |
| **$F$** | Set of accepting final states ($F \subseteq Q$) | `machine.final_states` |

### The Halting Problem vs. Bounded Halting
- **General Halting Problem (Turing, 1936)**: Determining whether an arbitrary Turing machine halts on an arbitrary input is **undecidable**. No algorithm can solve it for all inputs.
- **Bounded Halting Problem**: Asking *"Does $M$ halt on $w$ within at most $B$ transitions?"* is **strictly decidable** in $O(B)$ time. Our ML predictor investigates statistical pattern recognition to approximate this bounded property.

---

## 5. Quick Start Guide

### Prerequisites
- **Python 3.13** (Recommended)
- **Node.js 18+** with `npm`

---

### Option A: One-Click Launch (Windows)
Double-click:
```cmd
start_server.bat
```
This script detects the local virtual environment, opens your default browser at `http://127.0.0.1:8000`, and launches the FastAPI/Uvicorn server.

---

### Option B: Automated PowerShell Launcher
From the repository root:
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```
Automatically checks for dependencies, compiles the frontend bundle if missing, and launches the server at `http://127.0.0.1:8000`.

---

### Option C: Manual Setup & Execution

#### 1. Setup Backend
```powershell
# Create Python 3.13 virtual environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
python -m pip install --upgrade pip
pip install -r backend/requirements-dev.txt -r backend/requirements-ml.txt
```

#### 2. Build Frontend
```powershell
cd frontend
npm ci
npm run build
cd ..
```

#### 3. Launch Server
```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser.

---

## 6. REST API Reference

### Health Check
```http
GET /api/health
```
**Response (200 OK):**
```json
{
  "status": "ok"
}
```

---

### Simulate Machine
```http
POST /api/simulate
Content-Type: application/json
```
**Request Body:**
```json
{
  "machine": {
    "states": [{"id": "q0", "name": "Scan"}, {"id": "q1", "name": "Halt"}],
    "input_alphabet": ["1"],
    "tape_alphabet": ["1", "□"],
    "blank_symbol": "□",
    "start_state": "q0",
    "final_states": ["q1"],
    "transitions": [
      {"from_state": "q0", "read": "1", "to_state": "q0", "write": "1", "move": "R"},
      {"from_state": "q0", "read": "□", "to_state": "q1", "write": "□", "move": "R"}
    ]
  },
  "input": "111",
  "step_limit": 5000
}
```

**Response (200 OK):**
```json
{
  "halted_within_limit": true,
  "stop_reason": "final_state",
  "steps": 4,
  "initial": {
    "state": "q0",
    "head": 0,
    "cells": ["1", "1", "1"]
  },
  "trace": [
    {
      "step": 1,
      "transition_index": 0,
      "state_before": "q0",
      "state_after": "q0",
      "head_before": 0,
      "head_after": 1,
      "symbol_before": "1",
      "symbol_after": "1"
    }
  ]
}
```

---

### Predict Bounded Halting
```http
POST /api/predict
Content-Type: application/json
```
**Request Body:**
```json
{
  "machine": { ... },
  "input": "101"
}
```
**Response (200 OK):**
```json
{
  "50": {
    "source": "observed",
    "predicted_halted_within_limit": true,
    "observed_steps": 4,
    "stop_reason": "final_state"
  },
  "200": {
    "source": "observed",
    "predicted_halted_within_limit": true,
    "observed_steps": 4,
    "stop_reason": "final_state"
  },
  "1000": {
    "source": "observed",
    "predicted_halted_within_limit": true,
    "observed_steps": 4,
    "stop_reason": "final_state"
  }
}
```

---

## 7. Machine Learning Bounded Halting

The project implements a bounded halting estimation pipeline:
1. **Feature Extraction (`backend/app/features.py`)**:
   - Machine size metrics ($|Q|$, $|\Sigma|$, $|\Gamma|$, $|\delta|$).
   - In-degree, out-degree, and cycle ratios from the state transition digraph.
   - Prefix simulation features (distinct states visited, tape cell range, read/write ratios over the first 10 steps).
2. **Model Architectures**:
   - Trained across synthetic distributions of halting, cycling, and wandering Turing machines.
   - Preserves monotonicity constraints across increasing step budgets.
3. **Artifacts**: Serialized model bundles are stored under `models/final/` (`halt_by_50.joblib`, `halt_by_200.joblib`, `halt_by_1000.joblib`).

---

## 8. Test Suites & Verification

### Run Backend Unit & Boundary Tests
```powershell
.\.venv\Scripts\python.exe -m pytest
```
- **101 tests passed** across API validation, simulator boundaries (49..51, 199..201, 999..1001, 50000, 50001), infinite cycle handling, and ML monotonicity.

### Run Frontend Unit Tests
```powershell
cd frontend
npm test -- --run
```
- **12 tests passed** verifying tape cell reconstruction, signed head panning, and step state invariants.

### Production Type Check & Build
```powershell
cd frontend
npx tsc --noEmit
npm run build
```
- Zero TypeScript errors; produces optimized production bundle in `frontend/dist`.

---

## 9. Repository Structure

```
├── backend/
│   ├── app/
│   │   ├── features.py          # Topological & prefix feature extraction
│   │   ├── main.py              # FastAPI app, static SPA mount, size guard
│   │   ├── predictor.py         # Multi-budget ML model inference
│   │   ├── schemas.py           # Pydantic v2 TM & request/response schemas
│   │   └── simulator.py         # Deterministic sparse tape simulator
│   ├── experiments/             # Dataset generation & model training scripts
│   ├── requirements.txt         # Production runtime dependencies
│   ├── requirements-dev.txt     # Test & lint dependencies (pytest, httpx)
│   ├── requirements-ml.txt      # Machine learning dependencies (scikit-learn, pandas)
│   └── tests/                   # 101 automated pytest test cases
├── docs/                        # Formal architecture & project documentation
├── examples/                    # Canonical TM templates (JSON)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/       # Instant-load overview & system metrics
│   │   │   ├── examples/        # Curated automata library browser
│   │   │   ├── help/            # Formal 7-tuple theory reference modal
│   │   │   ├── modals/          # Schema v1 JSON import/export modal
│   │   │   ├── predictor/       # Bounded halting ML prediction view
│   │   │   ├── simulation/      # TapePlayer & ResultsPanel components
│   │   │   └── workspace/       # StateNode, TransitionEdge, MachineEditor
│   │   ├── api.ts               # Typed client fetch wrappers
│   │   ├── App.tsx              # Central state & unified playback coordinator
│   │   ├── styles.css           # Complete design system & responsive styling
│   │   └── types.ts             # TypeScript interfaces for TM models
│   ├── package.json             # NPM dependencies & scripts
│   └── vite.config.ts           # Vite build & Vitest test configuration
├── models/
│   ├── final/                   # Production-ready trained ML model bundles
│   ├── pilot/                   # Baseline pilot models
│   └── pilot_v2/                # Monotonic comparison models
├── report/                      # Accuracy metrics, confusion matrices & figures
├── pytest.ini                   # Pytest configuration
├── run.bat                      # Windows launcher script
├── run.ps1                      # PowerShell automated installer & runner
├── start_server.bat             # One-click standalone server launcher
└── README.md                    # Comprehensive project documentation
```

---

## 10. License & Credits

Distributed under the **MIT License**.

Built for academic demonstration in **Theory of Computation**. Designed with mathematical rigor, deterministic execution guarantees, and responsive automata visualization.
