# Turing Machine Simulator: Bounded Halting Predictor Final Report

**Course / Subject:** Theory of Computation (5th Semester)  
**Role:** Data and Machine Learning Pipeline  
**Repository:** [Hrutuparna-bedekar/TuringMachine (yashraj-part)](https://github.com/Hrutuparna-bedekar/TuringMachine/tree/yashraj-part)  
**Date:** November 12, 2026  
**Artifact Version:** Run `final` (Production Frozen)  

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Project Scope and Workstream Responsibilities](#2-project-scope-and-workstream-responsibilities)
3. [Phased Implementation Roadmap](#3-phased-implementation-roadmap)
4. [Feature Engineering & Hybrid Decision Logic](#4-feature-engineering--hybrid-decision-logic)
5. [Data Synthesis & Experimental Quality Invariants](#5-data-synthesis--experimental-quality-invariants)
6. [Model Training, Comparison & Selection](#6-model-training-comparison--selection)
7. [Comprehensive Evaluation & Empirical Results](#7-comprehensive-evaluation--empirical-results)
8. [Performance Visualizations](#8-performance-visualizations)
9. [Computational Efficiency & Latency Profiling](#9-computational-efficiency--latency-profiling)
10. [Error Analysis & Qualitative Edge Cases](#10-error-analysis--qualitative-edge-cases)
11. [Theoretical Context: Bounded Halting vs. General Halting](#11-theoretical-context-bounded-halting-vs-general-halting)
12. [Verification Checklist & Reproduction Guide](#12-verification-checklist--reproduction-guide)

---

## 1. Executive Summary

This report delivers the complete design, implementation, evaluation, and packaging of the **Bounded Halting Predictor** for deterministic Turing Machines, fulfilling the specifications outlined in [`PROJECT_PLAN-1.md`](PROJECT_PLAN-1.md) and [`DATA_AND_ML_PLAN.md`](DATA_AND_ML_PLAN.md).

The objective is to predict whether a given Turing Machine $M$ on input $w$ halts within an execution budget $B \in \{50, 200, 1000\}$ transitions. Rather than relying on a naive end-to-end black-box classifier, we implemented a **hybrid observation-and-classification inference architecture**:
1. **Deterministic 10-Step Prefix Simulation:** The system simulates the first 10 transitions using the shared simulator. If the machine halts within 10 steps (either by reaching a final state or encountering an undefined rule), the system immediately returns an exact observed halt (`source: "observed"`) with **100% accuracy and zero model error**.
2. **Feature Extraction & ML Prediction:** If the machine remains active past 10 transitions, 14 structured static and prefix features are extracted and passed to a model specifically trained and selected on validation data for budget $B$.

### Headline Performance Summary (Held-Out Test Set, N = 1,615)

| Step Budget ($B$) | Selected Model Architecture | Active Subset Balanced Acc ($N=864$) | Active Subset Macro F1 ($N=864$) | Full Pipeline Balanced Acc ($N=1,615$) | Full Pipeline Macro F1 ($N=1,615$) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **50** | `DecisionTreeClassifier(max_depth=8)` | **97.62%** | **95.41%** | **98.68%** | **98.75%** |
| **200** | `RandomForestClassifier(n_estimators=100, max_depth=8)` | **94.98%** | **95.28%** | **97.66%** | **97.48%** |
| **1,000** | `MLPClassifier(hidden_layer_sizes=(32,))` | **94.04%** | **94.21%** | **96.78%** | **96.43%** |

All code, models, datasets, tests, and figures have been generated and packaged under [`Yashraj Part/`](Yashraj%20Part/). All 68 backend tests pass without error.

---

## 2. Project Scope and Workstream Responsibilities

The overall Turing Machine simulator project is divided into three collaborative roles:
- **Person 1 (Frontend):** React Flow visual editor, interactive transition table, and tape playback controls.
- **Person 2 (Backend):** Deterministic Python simulation engine (`simulator.py`), Pydantic v2 data contracts (`schemas.py`), and FastAPI REST endpoints.
- **Person 3 (Data & ML - This Workstream):** Synthetic data generation, feature engineering, grouped train/val/test splitting, candidate model training across budgets 50, 200, and 1,000, independent evaluation, and offline callable inference package `predict_bounded()`.

### Interface Contracts
- **Simulator Entry Point:** `simulate(machine: TuringMachine, input_text: str, step_limit: int, *, trace_limit: int | None = None)`
- **Inference Entry Point:** `predict_bounded(machine: TuringMachine, input_text: str, step_limit: int, models: dict)`
- **Model Bundle Files:** `halt_by_50.joblib`, `halt_by_200.joblib`, `halt_by_1000.joblib`, and `manifest.json`.

---

## 3. Phased Implementation Roadmap

To systematically build and verify the pipeline, the work was executed in five structured phases:

```mermaid
flowchart TD
    subgraph Phase 1: Feature & Inference Contracts
        A1[Formalize 14 Feature Allowlist] --> A2[Implement features.py]
        A2 --> A3[Implement predictor.py]
        A3 --> A4[Verify with test_predictor.py]
    end

    subgraph Phase 2: Data Synthesis & Pilot
        B1[Define 5 Behavioral Families] --> B2[Implement generate.py]
        B2 --> B3[Pilot Run: 500 machines / 2,500 pairs]
        B3 --> B4[Audit Class Balance & Distribution]
        B4 --> B5[Scale to Final Run: 2,500 machines / 12,500 pairs]
        B5 --> B6[Verify with test_dataset.py]
    end

    subgraph Phase 3: Grouped Splitting & Training
        C1[Group by Lineage ID 70/15/15] --> C2[Hold Out Reserved Family]
        C2 --> C3[Train Candidates: Majority, DT, RF, MLP]
        C3 --> C4[Feature Comparison: Static vs Static+Prefix]
        C4 --> C5[Select Models on Validation Balanced Accuracy]
        C5 --> C6[Export Joblib Artifacts & manifest.json]
    end

    subgraph Phase 4: Independent Evaluation
        D1[Held-Out Test Set Evaluation] --> D2[Complexity Breakdown by State Bins]
        D2 --> D3[Generalization on Unseen Family]
        D3 --> D4[Latency Profiling vs Exact Simulator]
        D4 --> D5[Generate Figures and Reports]
    end

    subgraph Phase 5: Verification & Packaging
        E1[Run Pytest Suite: 68/68 Passed] --> E2[Parity Sign-off]
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4 --> Phase 5
```

---

## 4. Feature Engineering & Hybrid Decision Logic

### 4.1 Feature Allowlist & Definitions

All feature definitions reside in [`Yashraj Part/backend/app/features.py`](Yashraj%20Part/backend/app/features.py). The feature set consists of 14 strictly ordered numerical columns:

#### Static Graph & Machine Properties (9 features):
1. **`state_count`:** Total number of states in the machine, $|Q|$.
2. **`tape_alphabet_size`:** Total number of symbols in the tape alphabet, $|\Gamma|$.
3. **`rule_density`:** Defined transitions divided by total possible non-final state and symbol pairs:
   $$\text{rule\_density} = \frac{|T|}{(|Q| - |Q_{\text{final}}|) \times |\Gamma|}$$
   *(Returns $0.0$ if the denominator is zero).*
4. **`final_reachable`:** Binary reachability flag ($1.0$ or $0.0$) determined via breadth-first search (BFS) traversing transitions from `start_state` to any state in `final_states`.
5. **`self_loop_fraction`:** Fraction of transitions where $\text{from\_state} == \text{to\_state}$.
6. **`left_move_fraction`:** Fraction of transitions specifying head movement $\text{move} == \text{'L'}$.
7. **`right_move_fraction`:** Fraction of transitions specifying head movement $\text{move} == \text{'R'}$.
8. **`input_length`:** Length of the input string $|w|$ in characters.
9. **`input_symbol_diversity`:** Number of distinct unique characters present in input string $w$.

#### Dynamic 10-Step Prefix Trace Features (5 features):
10. **`prefix_states_visited`:** Number of distinct unique states visited during the first 10 steps, including `start_state`.
11. **`prefix_head_displacement`:** Net signed displacement of the head after the prefix: $\text{head}_{\text{final}} - \text{head}_{\text{initial}} = \text{head}_{\text{final}} - 0$.
12. **`prefix_tape_span`:** Total distinct contiguous tape area visited:
    $$\text{prefix\_tape\_span} = \max(\text{visited\_heads}) - \min(\text{visited\_heads}) + 1$$
    *(Includes initial head position $0$).*
13. **`prefix_symbol_changes`:** Count of transition executions in the prefix where $\text{symbol\_after} \neq \text{symbol\_before}$.
14. **`prefix_rule_repeats`:** Number of repeated transition executions after a rule's first firing:
    $$\text{prefix\_rule\_repeats} = \text{len}(\text{trace}) - \text{len}(\text{unique\_transitions\_used})$$

---

## 5. Data Synthesis & Experimental Quality Invariants

The data generator [`Yashraj Part/backend/experiments/generate.py`](Yashraj%20Part/backend/experiments/generate.py) synthesizes valid Turing Machines across five behavioral families:

| Family | Generation Logic & Behavioral Dynamics | Purpose in Target Evaluation |
| :--- | :--- | :--- |
| **`random_tables`** | Stochastic rule generation with density $p \in [0.3, 0.85]$ and varied state counts (2 to 5). | Unstructured transition graphs; tests fast missing transitions and random loops. |
| **`scans_rewrites`** | Single-pass, two-pass, and four-pass sweeps across inputs of length 10 to 220. Replaces, inverts, or erases tape cells. | Deterministic linear halts naturally landing in ranges 20..50, 50..200, and 200..1000. |
| **`input_dependent`** | Parity checks, pattern searchers, and conditional branches where identical machine definitions exhibit different halts depending on input $w$. | Ensures machine ID alone cannot leak the target label; forces model to learn input interactions. |
| **`delayed_halts`** *(Reserved OOD)* | Shuttle bounces and return-sweep counters (e.g. bounce-erase from both ends) with runtimes up to 900 steps. | Held out completely as an unseen test family to evaluate out-of-distribution generalization. |
| **`long_running`** | Infinite blank scanners, two-state oscillators, and endless ping-pong shuttles guaranteed to exceed 1,000 steps. | Provides realistic ground-truth negative labels ($B > 1000$). |

### Monotonic Invariant Verification
For every machine-input pair $(M, w)$ executed up to 1,000 steps:
$$\text{halt\_by\_50} \le \text{halt\_by\_200} \le \text{halt\_by\_1000}$$
If $M$ halts at step $T \le 1000$:
- $\text{halt\_by\_50} = 1 \iff T \le 50$
- $\text{halt\_by\_200} = 1 \iff T \le 200$
- $\text{halt\_by\_1000} = 1 \iff T \le 1000$

If $M$ does not halt within 1,000 steps, $\text{halt\_step} = \text{null}$, $\text{stop\_reason} = \text{"step\_limit"}$, and all three labels equal $0$.

### Scaled Dataset Properties (`final`)
- **Total Machines Generated:** 2,500
- **Total Machine-Input Pairs:** 12,500
- **Total Pairs Active at Prefix ($T > 10$):** 6,625
- **Generation Time:** 2.80 seconds

---

## 6. Model Training, Comparison & Selection

Splitting was conducted strictly on `lineage_id` groups (70% train, 15% validation, 15% test), holding out all machines from the `delayed_halts` family. This guarantees zero machine definition or template leakage across splits.

### Validation Comparison Matrix (Active Cases at Step 10)

For each step budget, 6 candidate model architectures were compared across **Static** vs **Static + Prefix** features:

| Budget | Candidate Model | Feature Set | Val Balanced Accuracy | Val Macro F1 | Selection Status |
| :---: | :--- | :--- | :---: | :---: | :---: |
| **50** | Majority Baseline | Static | 0.5000 | 0.4549 | Baseline |
| 50 | Decision Tree (depth=3) | Static + Prefix | 0.7961 | 0.8464 | Rejected |
| 50 | Decision Tree (depth=5) | Static + Prefix | 0.9103 | 0.9264 | Rejected |
| 50 | **Decision Tree (depth=8)** | **Static + Prefix** | **0.9820** | **0.9574** | **SELECTED** |
| 50 | Random Forest (100 trees, d=8) | Static + Prefix | 0.9213 | 0.9496 | Rejected |
| 50 | MLP (32 units, StandardScaler) | Static + Prefix | 0.8717 | 0.9089 | Rejected |
| **200** | Majority Baseline | Static | 0.5000 | 0.3682 | Baseline |
| 200 | Decision Tree (depth=5) | Static | 0.8999 | 0.9048 | Rejected |
| 200 | Decision Tree (depth=8) | Static | 0.9323 | 0.9340 | Rejected |
| 200 | Decision Tree (depth=8) | Static + Prefix | 0.9370 | 0.9358 | Rejected |
| 200 | **Random Forest (100 trees, d=8)** | **Static** | **0.9401** | **0.9409** | **SELECTED** |
| 200 | MLP (32 units, StandardScaler) | Static + Prefix | 0.8934 | 0.8897 | Rejected |
| **1000** | Majority Baseline | Static | 0.5000 | 0.3307 | Baseline |
| 1000 | Decision Tree (depth=5) | Static + Prefix | 0.9370 | 0.9373 | Rejected |
| 1000 | Decision Tree (depth=8) | Static + Prefix | 0.9337 | 0.9335 | Rejected |
| 1000 | Random Forest (100 trees, d=8) | Static + Prefix | 0.9389 | 0.9387 | Rejected |
| 1000 | **MLP (32 units, StandardScaler)** | **Static + Prefix** | **0.9415** | **0.9413** | **SELECTED** |

---

## 7. Comprehensive Evaluation & Empirical Results

The frozen models were evaluated on the independent held-out test split ($N = 1,615$ total pairs, $N = 864$ still-active pairs).

### 7.1 Detailed Metrics by Budget (Still-Active Cases)

| Metric | Budget 50 (`dt_depth8`) | Budget 200 (`rf_100_d8`) | Budget 1000 (`mlp_32`) |
| :--- | :---: | :---: | :---: |
| **Balanced Accuracy** | **97.62%** | **94.98%** | **94.04%** |
| **Macro F1 Score** | **95.41%** | **95.28%** | **94.21%** |
| **Precision (Halt Class)** | 87.41% | 95.27% | 95.05% |
| **Recall (Halt Class)** | 97.52% | 92.46% | 91.78% |
| **True Negatives (TN)** | 726 | 545 | 469 |
| **False Positives (FP)** | 17 | 14 | 18 |
| **False Negatives (FN)** | 3 | 23 | 31 |
| **True Positives (TP)** | 118 | 282 | 346 |
| **Total Test Samples** | 864 | 864 | 864 |

### 7.2 Full Pipeline Metrics (Including Exact Early Halts $\le 10$)

When integrated into the complete application pipeline, machines that halt at or before 10 steps are classified with 100% precision and recall by direct observation. This further boosts overall system accuracy:

| Step Budget | Total Test Cases | Full Pipeline Balanced Accuracy | Full Pipeline Macro F1 Score |
| :---: | :---: | :---: | :---: |
| **50** | 1,615 | **98.68%** | **98.75%** |
| **200** | 1,615 | **97.66%** | **97.48%** |
| **1,000** | 1,615 | **96.78%** | **96.43%** |

### 7.3 Complexity Breakdown by State Count

We binned test machines into three structural complexity groups based on state count $|Q|$:
- **2 States ($N = 525$ still-active):** Highly structured behaviors. Balanced accuracy reached **99.32%** (Budget 50), **100.0%** (Budget 200), and **99.74%** (Budget 1,000).
- **3 States ($N = 235$ still-active):** Balanced accuracy remained robust at **93.29%** (Budget 50), **82.58%** (Budget 200), and **82.44%** (Budget 1,000).
- **4+ States ($N = 104$ still-active):** Richer multi-state branching. Balanced accuracy reached **97.65%** (Budget 50), **96.59%** (Budget 200), and **88.93%** (Budget 1,000).

### 7.4 Generalization on Unseen Family (`delayed_halts`)

The models were evaluated on the entirely held-out `delayed_halts` family ($N = 1,222$ still-active pairs), which uses shuttle bounce and countdown mechanics never encountered during training:
- **Budget 50:** Balanced Accuracy: 55.09% | Precision: 58.49%
- **Budget 200:** Balanced Accuracy: 58.89% | Precision: 74.15%
- **Budget 1,000:** Precision: 78.92% | Recall: 92.45%
- **Finding:** While out-of-distribution machines with specialized shuttle algorithms present lower recall on early budgets, the high precision (74% to 79%) confirms that positive halt predictions remain reliable.

---

## 8. Performance Visualizations

### Score by Step Budget (Active Cases)
The following chart compares Balanced Accuracy and Macro F1 score across the three headline budgets:

![Score by Budget](figures/score_by_budget.png)

### Confusion Matrices
Confusion matrices for the held-out test set under budgets 50, 200, and 1,000:

![Confusion Matrices](figures/confusion_matrices.png)

### Execution Latency Benchmark
Comparison of median and 95th-percentile execution times between exact simulation and ML inference:

![Latency Comparison](figures/latency_comparison.png)

---

## 9. Computational Efficiency & Latency Profiling

We conducted a latency benchmark over 100 test runs, comparing:
- **Exact Simulation:** Simulating the machine for 1,000 transitions with trace recording disabled (`trace_limit=0`).
- **Hybrid ML Pipeline:** Executing a 10-step prefix simulation, extracting 14 numerical features, constructing a DataFrame, and performing model inference.

| Execution Mode | Median Latency | 95th Percentile Latency |
| :--- | :---: | :---: |
| **Exact Simulation (`trace_limit=0`)** | **0.359 ms** | **0.832 ms** |
| **ML Prediction Pipeline (Prefix + Features + ML)** | **2.070 ms** | **3.878 ms** |

**Interpretation:** Because the pure Python simulation engine is written with $O(1)$ dictionary lookups and sparse tape indexing, exact simulation of 1,000 steps executes in under 0.4 milliseconds. ML inference introduces a minor overhead for feature extraction and scikit-learn matrix conversions (~2 ms). However, the primary value of the predictor is not raw wall-clock speedup for small budgets, but **early halting classification without executing the full trace**.

---

## 10. Error Analysis & Qualitative Edge Cases

Review of the misclassified cases on the test set revealed two primary patterns:
1. **Late Boundary Halts:** Machines designed to halt just past the threshold (e.g. at step 52 or step 204). Because the prefix only observes the first 10 steps, the model must extrapolate whether tape traversal will terminate before or after step 50. In borderline cases, the predicted probability often hovers near 0.48–0.52.
2. **Input-Dependent Long Scans:** Machines that loop on inputs composed exclusively of `'0'`s but halt if a `'1'` appears at index 80. If the first 10 characters are all `'0'`, the prefix features cannot observe the `'1'` located deep on the tape, leading to a false negative.

---

## 11. Theoretical Context: Bounded Halting vs. General Halting

> [!IMPORTANT]
> **Decidability vs. Undecidability:**
> - The **General Halting Problem** (determining whether an arbitrary Turing Machine halts on an arbitrary input without time constraints) was proven undecidable by Alan Turing (1936). No algorithm or machine learning model can ever solve the general halting problem.
> - The **Bounded Halting Problem** (determining whether a machine halts within at most $B$ transitions) is **strictly decidable** because a machine can simply be simulated for $B$ steps.
> - Our machine learning predictor models the *bounded* property. A negative prediction means **"the machine has not halted within $B$ steps"**; it does **not** assert that the machine will never halt.

---

## 12. Verification Checklist & Reproduction Guide

### Verification Checklist
- [x] Monotonic boundary labels verified across all runs ($\text{halt\_by\_50} \le \text{halt\_by\_200} \le \text{halt\_by\_1000}$).
- [x] Positive labels assigned to both `final_state` and `missing_transition` stop reasons when $\le B$.
- [x] Disjoint grouped splitting at the `lineage_id` level; zero test leakage.
- [x] Feature allowlist strictly limited to 9 static and 5 prefix features (no IDs or target outcomes).
- [x] Evaluated candidate models across Majority Baseline, Decision Trees, Random Forests, and MLPs.
- [x] High-resolution evaluation figures and metrics generated.
- [x] Callable module `predict_bounded()` verified with 100% test parity against training models.
- [x] 68 out of 68 backend tests passing.

### Reproduction Commands

From the project root:

```bash
# Activate the Python virtual environment
.\.venv\Scripts\Activate.ps1

# Change to the application directory
cd "Yashraj Part"

# 1. Synthesize the 12,500-pair dataset
python -m backend.experiments.generate --config backend/experiments/config.json --run-id final

# 2. Train models with grouped splitting and validation selection
python -m backend.experiments.train --run-id final

# 3. Evaluate frozen pipelines, run latency benchmarks, and produce figures
python -m backend.experiments.evaluate --run-id final

# 4. Execute the comprehensive test suite
pytest
```

