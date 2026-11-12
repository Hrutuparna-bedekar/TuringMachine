# Turing Machine Simulator and Bounded Halting Predictor

## 1. Scope, roles, and handoffs

Build a localhost app where a user can draw a Turing machine, run it on an input within a step budget, and replay the tape. Start with exact simulation. Add bounded-halting prediction after the ML pipeline is trained and verified.

**Implementation brief.** Inspect existing code before implementing each workstream. Use the machine schema, simulator signature, stop ordering, and response examples below as shared contracts. Build and test one simulation engine. Keep the standalone app runnable before model integration and whenever the model is unavailable.

| Person | Role | Owns | Handoff |
| --- | --- | --- | --- |
| Person 1 | **Frontend** | React Flow editor, rule table, validation messages, JSON import/export, tape playback, and frontend tests. After model integration, add the prediction panel. | A working browser workflow that calls the backend API. Use the ML fixtures to check prediction display. |
| Person 2 | **Backend** | Machine schemas, Python simulation engine, simulation API, backend tests, and local app startup. After the ML handoff, expose the inference module through the prediction endpoint. | Tested simulator, schema, and boundary fixtures for Person 3. API contract and examples for Person 1. |
| Person 3 | **Data and ML** | Automatic data generation using the shared simulator, features, grouped splits, model training and evaluation, callable inference, and experimental report. | Versioned models, inference module, dependency versions, manifest, and reference results for app integration. |

1. **Standalone app.** Persons 1 and 2 agree on the schema and build and verify the frontend and backend. Person 3 can prepare generator settings and fixtures against that schema.
2. **ML pipeline.** Person 2 hands off the tested engine, schema, and fixtures. Person 3 imports that engine to generate training labels and produces the evaluated inference package.
3. **Local integration.** Person 2 adds the prediction endpoint, Person 1 adds the prediction panel, and Person 3 supplies fixtures and verifies that app scores match offline inference.

### Technology

| Area | Technology | Purpose |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite | Editor, tape viewer, controls, and result panels |
| Graph editor | React Flow (`@xyflow/react`) | Draggable nodes, transition handles, zoom, and labeled edges |
| Backend | Python, FastAPI, Pydantic, Uvicorn | Machine validation, exact simulation, and trace generation |
| Data and ML | scikit-learn, pandas, PyArrow, joblib, Matplotlib | Generate datasets, train classifiers, export pipelines, and plot results |
| Storage | Versioned JSON | Browser import/export for machine definitions and diagram positions |
| Testing | pytest and Vitest | Simulator semantics, API contracts, and editor behavior |
| Local demo | FastAPI serves the built React app on `127.0.0.1` | Serve the frontend and API from the same local origin. Use browser JSON import/export for persistence. |

## 2. Repository structure and requirements

```text
Toc/
├── README.md                     # Setup, commands, demo link, and example workflow
├── PROJECT_PLAN.md
├── .gitignore                    # Local environments and builds
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── index.html                # Vite entry document
│   ├── vite.config.ts            # Development proxy and Vitest configuration
│   ├── tsconfig.json
│   ├── src/
│   │   ├── main.tsx              # Mount the React app and load styles
│   │   ├── App.tsx               # Page layout and active machine/run state
│   │   ├── styles.css            # Editor, tape, and responsive layout
│   │   ├── machine.ts            # Machine types, editor validation, JSON import/export
│   │   ├── api.ts                # Simulation requests
│   │   ├── MachineEditor.tsx     # React Flow canvas and transition editing
│   │   ├── TransitionTable.tsx   # Keyboard-accessible rule editing
│   │   ├── TapePlayer.tsx        # Trace replay, tape window, head, and step controls
│   │   └── ResultsPanel.tsx      # Exact outcome and stop reason
│   └── tests/                    # Machine validation, replay, and UI interaction tests
├── backend/
│   ├── requirements.txt         # Simulator and web runtime dependencies
│   ├── requirements-dev.txt     # Testing dependencies
│   ├── requirements-ml.txt      # Separate ML dependencies
│   ├── app/
│   │   ├── main.py               # Routes and local build serving
│   │   ├── schemas.py            # Machine, request, trace, and result schemas
│   │   ├── simulator.py          # Shared tape, transition lookup, and stop rules
│   │   ├── features.py           # Ordered, versioned ML feature extraction
│   │   └── predictor.py          # Callable ML inference, independent of HTTP
│   ├── experiments/
│   │   ├── config.json           # Generator, split, and experiment settings
│   │   ├── generate.py           # Generate and label machine-input pairs
│   │   ├── train.py              # Grouped splits and model training
│   │   └── evaluate.py           # Frozen evaluation, timings, and figures
│   └── tests/
│       ├── test_simulator.py
│       ├── test_api.py
│       ├── test_dataset.py
│       └── test_predictor.py
├── examples/
│   ├── scan-to-blank.json
│   ├── replace-symbol.json
│   └── loop.json
├── data/generated/               # Generated datasets and split manifests
├── models/                       # Selected pipelines and manifest per run
└── report/                       # Evaluation tables, figures, and write-up
```

During development, run Vite and FastAPI separately on localhost and proxy `/api` from Vite. For the demo, serve the built React files from FastAPI. Keep dependency versions under version control and document installation, testing, and local startup commands in the README.

**Dependency requirements.** Runtime Python dependencies are `fastapi`, `pydantic`, and `uvicorn`. Test dependencies are `pytest` and `httpx` for API tests. Frontend runtime dependencies are `react`, `react-dom`, and `@xyflow/react`. Use Vite, TypeScript, and Vitest for the build and tests, with React Testing Library and a DOM test environment for UI tests. Commit the frontend lockfile and pin compatible Python dependencies. Define `npm run dev`, `npm run build` (including type checking), and `npm test` (non-watch mode) in `frontend/package.json`.

## 3. Person 1 · Frontend

| User action | Expected behavior |
| --- | --- |
| Create a machine | Start with an editable start node, alphabet controls, and an empty rule table. |
| Add, rename, drag, or delete states | Show start and final states distinctly. Use stable IDs so renaming preserves rules. Confirm deletion when it removes connected rules. |
| Draw an arrow or add a table row | Open a rule form with source, target, read, write, and Left/Right controls. Show self-loops and multiple rules between the same states. |
| Edit the graph or table | Update the same machine definition and reflect the change in both views. Use the table as a keyboard-accessible path for editing transitions. |
| Set the alphabet, input, and budget | Show actionable validation errors and block requests for invalid definitions. Support empty input and show the initial blank under the head. |
| Run or step through a machine | Highlight the current state, tape head, and last rule. Show numbered cells around the head. Provide play, pause, forward, backward, and reset. |
| Inspect the exact result | Show the stop reason and step count. Invalidate an old trace and discard a late response when the machine, input, or budget changes. |
| Load, import, or export | Offer scan-to-blank, symbol-replacement, and looping examples. Import/export versioned JSON and restore node positions. Keep the current editor contents if import validation fails. |

Use a JSON export envelope with `schema_version`, `machine`, and optional `layout` keyed by state ID. Keep layout out of simulator requests and ML features.

- Keep one machine definition as the source of truth. Derive canvas nodes and edges from it and keep layout separately. Group rules sharing the same source and target on one readable edge. Give every rule a table row so self-loops and parallel rules can be edited individually. Ask the user to reassign the start state before deleting it. When marking a state final, show any outgoing rules that need to be removed before applying the change.
- Playback is client-side over the returned trace. Cursor `0` shows the initial state; cursor `n` shows the configuration after `n` transitions. Reversing an event restores the previous tape symbol, head, and state. Pause at the last event and show the stop reason there. Reset returns to cursor `0`. A zero-event result still displays the initial tape and result.
- Show labeled inputs, visible keyboard focus, readable validation messages, and accessible names for playback buttons. The transition table must support creating, editing, and deleting rules without dragging. On a narrow screen, stack the canvas, table, and playback panels and allow the tape window to scroll.

## 4. Person 2 · Backend

### Machine and simulation requirements

- **Machine model.** Deterministic, one tape, infinite in both directions. The input is written from cell `0` onward. All other cells are blank and the head starts at `0`, including on empty input.
- **Alphabets.** The input alphabet is a subset of the tape alphabet. The blank belongs to the tape alphabet and is reserved from input. For the first version, each symbol is one Unicode code point. Both frontend and backend should split and validate input by code point.
- **Rules.** A rule maps `(current state, read symbol)` to `(next state, write symbol, move)`. Only `L` and `R` are valid. Writing the read symbol preserves the cell. At most one rule can match a given state and symbol.
- **Execution.** Use a dictionary keyed by signed positions for nonblank tape cells and a transition lookup keyed by state and read symbol. Writing a blank removes the cell from the dictionary. Only executing a transition increments the counter.
- **Validation.** Require one existing start state. Allow zero or more final states. Reject duplicate state IDs and transition keys, unknown state references, symbols outside their alphabets, invalid moves, and outgoing rules from final states.

Check the current configuration in this order, including at step `0` and exactly at the budget boundary.

| Priority | Condition | Result | Halts within budget |
| --- | --- | --- | --- |
| 1 | Current state is final | `final_state` | Yes |
| 2 | Current state is non-final and no rule matches | `missing_transition` | Yes |
| 3 | A rule matches and the step count equals the budget | `step_limit` | No |
| 4 | A rule matches and budget remains | Execute it and repeat | Pending |

Reaching a final state ends the run immediately. If there is no matching transition, the machine halts without reaching a final state and consumes zero extra steps. The prediction target counts both outcomes as halts.

### Simulation API contract

The `machine` payload includes `states`, `input_alphabet`, `tape_alphabet`, `blank_symbol`, `start_state`, `final_states`, and `transitions`. Each transition includes `from_state`, `read`, `to_state`, `write`, and `move`. The simulation endpoint accepts `machine`, `input`, and `step_limit`.

| Endpoint | Contract |
| --- | --- |
| `POST /api/simulate` | Accept a budget from 0 to 1,000. Return `halted_within_limit`, `stop_reason`, `steps`, the initial configuration, and one event per executed transition. Each event identifies the rule, head position before and after, previous and written symbol, and resulting state. |
| `GET /api/health` | Report service readiness for the local deployment. |

Keep the Python simulation function independent of HTTP so the ML teammate can use it for batch generation. Give it an optional trace limit so it can record only an initial prefix or skip trace capture entirely. The HTTP route records the full bounded playback trace. Use compact events so replay can reverse a write without rerunning the simulator. On invalid input return field-level errors. Enforce server-side limits on states, transitions, input length, request size, and step count. Confirm numeric size limits during the local demo.

#### Exact wire format and shared Python entry point

- `states` is an array of `{ "id": string, "name": string }`. Use stable nonempty IDs and nonempty display names. `start_state`, `final_states`, `from_state`, and `to_state` refer to IDs. Reject duplicate IDs and duplicate alphabet entries. `final_states` is an array of unique IDs. Symbols are single Unicode scalar values. Use Python code-point iteration and JavaScript `Array.from`, and reject unpaired surrogates consistently. Preserve exact symbol values and input text, including spaces, rather than trimming them.
- `input` is a string. `step_limit` is a strict integer in `0..1000`, including zero. The import envelope uses integer `schema_version: 1` and optional `layout` entries of `{ "x": number, "y": number }` with finite coordinates. Reject unknown versions and dangling layout IDs. Layout-free imports get default node positions.
- In `backend/app/simulator.py`, expose `simulate(machine, input_text, step_limit, *, trace_limit=None)`. Pass a validated machine. `trace_limit=None` captures all executed events, `0` captures none, and a positive integer captures at most that many initial events. Trace capture has no effect on the simulation budget or stop reason. For example, a budget of `1000` and trace limit of `10` yields the result at budget `1000` with at most ten recorded events.
- Start with size limits of 64 states, 32 tape symbols, 1,024 rules, 512 input code points, and 256 KiB per JSON request. Cap body size before parsing. Use HTTP `413` for oversized bodies and `422` with field locations for invalid payloads. `GET /api/health` returns `{ "status": "ok" }` when the service is ready.

Example `POST /api/simulate` request. The machine takes one step, lands on a blank, and halts without reaching a final state.

```json
{
  "machine": {
    "states": [{"id": "q0", "name": "Start"}],
    "input_alphabet": ["1"],
    "tape_alphabet": ["1", "□"],
    "blank_symbol": "□",
    "start_state": "q0",
    "final_states": [],
    "transitions": [{"from_state": "q0", "read": "1", "to_state": "q0", "write": "1", "move": "R"}]
  },
  "input": "1",
  "step_limit": 1
}
```

Expected response. `initial.cells` contains only nonblank cells. The event's `transition_index` is the zero-based index in the submitted rule list, and `step` is one-based.

```json
{
  "halted_within_limit": true,
  "stop_reason": "missing_transition",
  "steps": 1,
  "initial": {"state": "q0", "head": 0, "cells": [{"position": 0, "symbol": "1"}]},
  "trace": [{"step": 1, "transition_index": 0, "state_before": "q0", "state_after": "q0", "head_before": 0, "head_after": 1, "symbol_before": "1", "symbol_after": "1"}]
}
```

## 5. Person 3 · Data and ML

Import `simulate(machine, input_text, step_limit, *, trace_limit=None)` from `backend/app/simulator.py`. Pass the validated machine type defined by the simulator plan. For labels and prefix features, run with `step_limit=1000, trace_limit=10`. For online-equivalent prefix inference, use `step_limit=10, trace_limit=10`. For exact-simulation timing, set `trace_limit=0`. The shared engine returns `steps`, `stop_reason`, and trace events. Use its stop reason to distinguish an observed halt at the limit from a machine that could still execute a rule.

### Dependencies and artifacts

**Dependencies.** Put compatible pinned versions of `scikit-learn`, `pandas`, `pyarrow`, `joblib`, and `matplotlib` in `backend/requirements-ml.txt`. Install them alongside the simulator's Python dependencies. Use `pytest` for tests. Keep ML packages out of the standalone simulator requirements. Train on CPU using generated machine definitions and input strings.

| Path | Purpose |
| --- | --- |
| `backend/experiments/config.json` | Seeds, family mix, input ranges, budgets, prefix length, and training settings |
| `backend/experiments/generate.py` | Create valid machines and inputs, simulate them, label examples, and write a data-quality summary |
| `backend/app/features.py` | Named feature columns and feature extraction shared by training and inference |
| `backend/app/predictor.py` | Callable inference entry point for prefix simulation, artifact loading, and scoring, testable without HTTP |
| `backend/experiments/train.py` | Create grouped splits, train model pipelines, and select the demo models on validation data |
| `backend/experiments/evaluate.py` | Evaluate frozen models and splits, measure timing, and generate report tables and figures |
| `backend/tests/` | Label-boundary, generator, leakage, and inference parity tests |
| `data/generated/` | Generated `machines.jsonl`, `runs.parquet`, `features.parquet`, split manifest, and dataset summary |
| `models/` | Selected pipelines, one per supported budget, and a versioned manifest |
| `report/` | Metrics tables, figures, and error-analysis examples |

Keep experiment scripts, configuration, and small fixtures in Git. Generate larger data locally from the documented configuration. Package only the selected trusted model files in the local demo.

Give each experiment a `--run-id`, and write its outputs under `data/generated/<run-id>/`, `models/<run-id>/`, and `report/<run-id>/`. Record the resolved configuration, seed, and input dataset ID with each run. Keep pilot and final outputs separate. Stop with a clear error for missing inputs, incompatible manifests, or accidental overwrites of completed runs. The generator config must explicitly record budgets, prefix length, family weights, machine and input limits, inputs per machine, seeds, and split targets. Validate it before generation.

### Step 1 · Lock the prediction target and test fixtures

The prediction target is whether this machine halts on this input in at most `B` executed transitions. Use budgets of **50, 200, and 1,000**. A machine halts when it reaches a final state or when no rule matches. A missing rule consumes zero transitions. Both stop reasons get a positive label when they occur at or before the budget.

For a known halt step `T`, set `halt_by_B = 1` exactly when `T <= B`. If the machine is still running at 1,000, set `halt_step = null`, `stop_reason = step_limit`, and all three labels to `0`. A null halt step records the limit of observation.

| Fixture | `halt_by_50` | `halt_by_200` | `halt_by_1000` |
| --- | --- | --- | --- |
| Starts in a final state or starts with no matching rule (`T = 0`) | 1 | 1 | 1 |
| Halts after the 50th transition (`T = 50`) | 1 | 1 | 1 |
| Halts after the 51st transition (`T = 51`) | 0 | 1 | 1 |
| Halts after the 1,000th transition (`T = 1000`) | 0 | 0 | 1 |
| Still has a matching rule after 1,000 transitions | 0 | 0 | 0 |

Implement the boundary fixtures for both halt reasons. Include a machine that moves left into blank tape, a write-and-erase example, and a loop that remains active at every budget. Ask the simulator owner to sign off on the expected outcomes before using the engine to label the dataset.

### Step 2 · Build the generators and run a pilot

1. **Create repeatable machine generators.** Start with binary inputs, a blank symbol, and a few optional tape markers. Use seeds and stable IDs. Track the originating template lineage separately from the broader family. Random machines should vary state count, tape alphabet size, and transition density. Generate at most one rule per `(state, symbol)` and no outgoing rules from final states.
2. **Mix behaviors that exercise the target.** Start with five groups as a planning mix. Use generated behavior templates alongside random tables.

   | Group | What to generate |
   | --- | --- |
   | Random rule tables | Sparse and dense rules across several state-count ranges. The simulator determines the outcomes. |
   | Scans and rewrites | Machines that traverse the input, replace or erase symbols, and eventually reach a final state or an undefined transition. |
   | Input-dependent branches | Machines whose outcomes or halt times differ with input length or symbols. Run several inputs on the same definition. |
   | Delayed halts | Multi-pass scans or countdown-style templates with examples around 50, 200, and 1,000 steps. Use hand-checked fixtures for exact boundaries. |
   | Long-running runs | Machines that repeat behavior or keep moving into blanks. Record active-at-budget outcomes from the simulator. |

3. **Generate about five distinct inputs per machine.** Mix empty input where relevant, short and longer strings, different symbol patterns, and lengths near behavior changes. Avoid using only one kind of input for one target class. Keep data generation within the simulator's supported machine and input bounds.
4. **Start with a smoke run.** Generate a small batch across all groups and inspect machine JSON, traces, and labels by hand. Then run the pilot at **500 machines × about 5 inputs**. Time generation and record seeds and counts. The upper bound for 2,500 pairs at 1,000 transitions each is 2.5 million executed transitions, before early halts.
5. **Inspect the pilot before scaling.** Count positives and negatives at each budget, especially among examples still running at step 10. Cross-tabulate by generator family, state count, rule density, and input length. Check for duplicate machine definitions, near-identical templates, or a class that is effectively identified by one generator type. Add useful diversity before adding volume.
6. **Freeze the final configuration.** Start from the plan's target of **about 3,000 machines and 15,000 pairs**. Adjust based on pilot coverage and runtime. Generate the final dataset with a separate seed and exclude pilot cases and inspected template lineages from final test groups. Write actual counts, seed, configuration version, and runtime to the summary.

**Exit check:** There are enough independent machine groups and examples of both classes for each headline budget and for the cases still running at step 10. If a subgroup is sparse, combine sensible complexity bins or report its sample count and limited coverage.

### Step 3 · Store the runs and derive features

Run each machine–input pair once up to 1,000 transitions. Keep the first 10 events or an equivalent reproducible prefix record. Derive all three labels from the observed halt step. Spot-check labels against direct simulation at budgets 50 and 200 on a sample.

Use one row per unique `(machine_id, input)` pair. Store `active_at_prefix` as an eligibility flag, separate from model features. Compute it as `halt_step is null or halt_step > 10`, then verify it agrees with the actual 10-step run on fixtures, including a halt at exactly step 10. Treat simulator errors and invalid generated machines as failures to investigate. Every negative training label must come from a valid simulation result.

| Data | Required columns or fields |
| --- | --- |
| `machines.jsonl` | `machine_id`, `family`, `lineage_id`, generator seed, canonical machine definition |
| `runs.parquet` | `run_id`, `machine_id`, input, executed steps, nullable `halt_step`, `stop_reason`, `halt_by_50`, `halt_by_200`, `halt_by_1000`, and the prefix record or summary |
| `features.parquet` | `run_id`, versioned static and prefix feature columns. Join on `run_id` for training and evaluation. |
| Split manifest | Machine or lineage group, assigned split, split seed, and reserved family |

Use an explicit feature allowlist. IDs, raw state names, generator labels, split tags, full-run outcomes, and steps after the prefix belong to metadata or targets. Keep a stable feature order for training and the API.

| Feature set | Initial columns |
| --- | --- |
| Static | State count, tape alphabet size, rule density, any final state reachable in the state graph, self-loop fraction, left/right move fractions, input length, and input symbol diversity |
| Static plus prefix | All static columns, plus distinct states visited, signed head displacement, tape span visited, count of write events that change a symbol, and count of repeated rule executions in the first 10 transitions |

Define each feature once in `features.py`. For rule density, use defined rules divided by possible non-final-state and tape-symbol pairs. Define empty denominators as zero. Graph reachability follows arrows and serves as a structural feature. For the prefix, count a write as a change only when the new symbol differs from the old symbol, and count repeated executions after a rule's first use in the prefix. Test a known trace to lock these definitions.

Use these column names in this order. Static columns are `state_count`, `tape_alphabet_size`, `rule_density`, `final_reachable`, `self_loop_fraction`, `left_move_fraction`, `right_move_fraction`, `input_length`, and `input_symbol_diversity`. Append `prefix_states_visited`, `prefix_head_displacement`, `prefix_tape_span`, `prefix_symbol_changes`, and `prefix_rule_repeats` for the prefix variant. Include the initial head position and start state in visited features. Define tape span as the maximum visited position minus the minimum plus one. Define move and self-loop fractions over the number of rules. Count distinct input symbols for input diversity. Use finite numeric values and check feature names and ordering when loading a model.

**Prefix decision:** Run the simulator with a budget of 10. If it halts at step 0 through 10, return the exact observed halt for all three supported budgets. If it is active after step 10, compute the features and call the selected model. The feature builder and simulator should produce identical feature values during training and API inference for the same machine and input.

### Step 4 · Freeze splits and train

1. **Reserve the test sets.** Choose a family with multiple independent lineages for a separate generalization test where the pilot shows enough coverage. For the remaining data, start with a grouped **70/15/15 train/validation/test target**, adjusting counts to keep enough groups and both classes in each split. Check this at all three budgets on the still-active subset. Use the same split manifest across budgets and feature sets.
2. **Keep related machines together.** Assign all inputs for a machine to one split. Put variants from a common template lineage together. Deduplicate identical machine definitions or place them in the same group even if they have different IDs. Keep held-out outcomes out of model selection.
3. **Train on the cases where a prediction is needed.** For each budget, fit the same candidates on cases still active at step 10. Run one comparison with static features and a second with static plus the prefix. This measures what the prefix adds on the same evaluation examples. The inference pipeline handles early halts with direct observation.

   | Candidate | Starting configuration |
   | --- | --- |
   | Majority baseline | Predict the most common class in the training split for the budget. |
   | Decision Tree | Try a small set of maximum depths such as 3, 5, and 8. |
   | Random Forest | Start with 100 trees. Compare a small set of depth or minimum-leaf settings. |
   | Small neural network | Use `MLPClassifier` with one hidden layer of 32 units as a starting point. Fit `StandardScaler` within the training pipeline. Use seeded runs and watch for convergence warnings. |

4. **Select models using validation only.** Use balanced accuracy as the primary metric and macro F1 as a secondary metric. Start with a fixed threshold of `0.5` for the halt-class score. If validation scores are similar, use inference time and simplicity to choose. Save the selected model, feature set, and threshold for each budget before evaluating on the held-out sets.

Freeze the actual split assignments in a manifest keyed by group. Use the same manifest for all models, and check it for group overlap and class coverage before fitting. Preserve the candidate models and configurations needed for the final model-comparison report. Only the validation-selected models go into the handoff package. Read the halt-class score from the model class labeled `1` using `classes_`, rather than assuming its column index. Fail clearly if an intended headline split lacks a class and revisit data coverage before reporting a comparison.

### Step 5 · Evaluate and write the results

| Question | Measurement |
| --- | --- |
| How does the step budget change prediction quality? | Report balanced accuracy, macro F1, confusion matrices, class counts, and test sample sizes at 50, 200, and 1,000 steps. Use the same test cases across budgets. |
| Does the early trace help? | Compare static and static-plus-prefix performance on the same still-active cases. Show full-pipeline results with early observed halts separately. |
| What changes with machine complexity? | Predefine state-count bins after the pilot, then report scores and sample counts in each bin. Include density and input-length summaries so readers can see how those characteristics vary. Flag bins with too few groups or only one observed class. |
| Does performance hold on an unseen family? | Evaluate the reserved family separately and report how its class balance and behavior differ from the main test set. |
| How much computation does prediction save or cost? | Time the warmed-up prediction pipeline, including prefix simulation and feature extraction, against exact simulation with playback trace disabled. Use the same cases and budgets, separate early-halt and still-active cases, and report the environment and median and 95th-percentile latency. |

Produce a table of model metrics, a score-by-budget figure, a complexity breakdown, and several misclassified example traces. Include errors near the budget boundary and at least one machine whose outcome changes with the input if the evaluation set contains such a case. Report the sampling mix and interpret results in the context of the generated families. Treat model scores as scores unless calibration is measured.

### Step 6 · Package and hand off

- Export the selected fitted pipelines for **50, 200, and 1,000** steps, including preprocessing. Load artifacts only from the trusted project build.
- Include a manifest with model ID, budget, feature names and version, prefix length, classification threshold, dataset and split IDs, and dependency versions. Pin the inference environment to compatible package versions.
- Supply API examples for an observed halt, a model prediction, and a simulation that remains active at its limit. Include expected feature values or a feature-row fixture for the parity test.
- Verify that the same example gives the same features and score in the training environment and the callable inference module. Verify both positive halt reasons, including a missing transition exactly at the prefix boundary. Pass these cases to the backend owner for future HTTP parity tests.
- Document the commands for generating data, training, and evaluating, plus expected file outputs. Proposed entry points from the repository root are `python -m backend.experiments.generate`, `python -m backend.experiments.train`, and `python -m backend.experiments.evaluate`. Confirm the commands against the implementation before the demo.

Expose a callable `predict_bounded(machine, input_text, step_limit, models)` that accepts the validated machine and preloaded model bundle. Reject unsupported budgets. Return `source`, `predicted_halted_within_limit`, and `observed_steps`. When `source` is `observed`, include the exact `stop_reason` and omit model fields. When `source` is `model`, include `model_id` and `halt_score`, with the class determined using the manifest threshold. Export selected pipelines as `halt_by_50.joblib`, `halt_by_200.joblib`, and `halt_by_1000.joblib` with `manifest.json`. Validate expected budgets and feature metadata when loading the trusted artifacts. Include these expected response fields in the handoff fixtures for the future API.

### Implementation commands and completion checks

Implement and document these commands from the repository root. Keep the generate, train, and evaluate entry points separate so training can be repeated against a fixed dataset and evaluation can load frozen models and splits without retraining.

```text
python -m backend.experiments.generate --config backend/experiments/config.json --run-id final
python -m backend.experiments.train --run-id final
python -m backend.experiments.evaluate --run-id final
python -m pytest backend/tests/test_dataset.py backend/tests/test_predictor.py
```

Use a smaller configuration and a distinct run ID for local smoke checks. The smoke check must generate valid artifacts, exercise both halt reasons, and run through training and evaluation on a fixture dataset with adequate class and group coverage. It serves as a pipeline check. Use the frozen final run for report results.

- [ ] Boundary labels pass the simulator fixtures and budget consistency checks (`halt_by_50 <= halt_by_200 <= halt_by_1000`).
- [ ] All headline splits have both classes, with disjoint machine and template groups.
- [ ] Model inputs are restricted to static and prefix feature columns.
- [ ] One command sequence reproduces data, training, and evaluation from versioned configuration.
- [ ] All three requested classifier types and the baseline appear in the report.
- [ ] The callable inference module and training pipeline agree on features and scores for the same example. The fixtures are ready for future API integration.
- [ ] The report distinguishes **has not halted within the budget** from eventual halting and states the limits of the synthetic dataset.

**Planning assumptions:** Start with local CPU training, five inputs per machine, a 10-step prefix, and the three agreed budgets. The pilot determines the final sample size, viable holdout family, and complexity bins. All scores and timings are outcomes to measure during implementation.

## 6. Integrate prediction after the ML handoff

Hand the tested Python engine, machine schema, and boundary fixtures to the ML teammate. The ML pipeline imports the engine directly to generate the dataset. The standalone local demo uses that same engine through the simulation API.

After the ML teammate delivers the versioned models, callable inference code, dependency versions, and parity fixtures, add `POST /api/predict` and a prediction panel in a separate integration phase. Reuse the machine, input, and budget fields. Show model predictions, observed early halts, and exact simulation outcomes as distinct results. Check API scores against the offline fixtures before enabling prediction in the local build. Keep exact simulation available when the model is unavailable.

## 7. Standalone build order and local startup

| Implementation order | Actions | Exit check |
| --- | --- | --- |
| Engine and fixtures | Implement and test the schema and engine. Prepare the React shell and initial canvas using the same fixtures. | The engine passes the class-rule and budget-boundary tests. |
| Editor and API | Build graph and table editing, request validation, and `/api/simulate`. Create example machines. | A machine drawn in the browser runs through the API. |
| Playback and files | Finish tape playback and JSON import/export. | A machine can be exported, reloaded, run, and replayed. |
| Release checks | Build and serve the frontend with the API, test error cases and keyboard interactions, then verify the local deployment. | The standalone release passes the acceptance checklist. |

Run `python -m pytest backend/tests/test_simulator.py backend/tests/test_api.py` from the repository root for the standalone backend. In `frontend/`, run `npm ci`, `npm test`, and `npm run build`. For development, use `npm run dev` and start Uvicorn with `--reload`. For the built demo, run `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` from the repository root, then open `http://127.0.0.1:8000`. Register API routes before serving frontend files so static handling preserves API errors.

## 8. Standalone verification and delivery checklist

- [ ] Engine tests cover empty input, moving left from cell 0, rewriting and erasing cells, immediate final-state and missing-rule halts, looping until the budget, and both kinds of halt exactly at the budget.
- [ ] Validation tests cover duplicate rules, bad symbols and moves, outgoing rules on final states, invalid JSON imports, and oversized requests.
- [ ] Frontend checks cover synchronized graph/table edits, self-loops, forward and backward trace replay, JSON round-tripping, and clearing stale results after edits.
- [ ] The localhost smoke test creates a machine from scratch and replays the exact outcome. A looping example displays **Has not halted within the step limit**.
- [ ] The local simulator starts and runs with only its web and simulation dependencies installed.
- [ ] Deliver the localhost address, repository, machine examples, and setup and deployment instructions.

Direct simulation decides whether the machine halts within a finite budget. A machine still active at the limit may halt later. The general halting problem remains undecidable.
