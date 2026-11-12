# Data and ML Pipeline Plan

This plan covers the offline data and ML workstream. Start dataset generation after receiving the tested Python simulator, machine schema, and boundary fixtures from the [Frontend and Backend Plan](PROJECT_PLAN.md). The ML owner reuses that simulator to label data, trains and compares classifiers, and delivers a tested inference package and experimental report. The app team then integrates the package into the localhost demo.

**Implementation brief.** Build the offline pipeline, tests, and callable inference module. Inspect the existing engine and schemas first. Import the shared simulator and follow its machine validation and stop reasons. If the engine is missing, the configuration, generators, and fixtures can be prepared against the documented interface. Generate real labels once the shared engine is available. Leave app API routes and frontend changes to the later integration phase.

## 1. Ownership and dependencies

| Person | Responsibility |
| --- | --- |
| Data and ML owner | Write generators and dataset checks, own feature extraction and split manifests, train models, evaluate results, and package the selected pipelines. |
| Simulator/backend owner | Supply the machine schema and callable Python simulator and review labeling fixtures. In the later integration phase, connect the exported models to `/api/predict`. |
| Frontend owner | Use the ML teammate's example responses to test the prediction panel during the later integration phase. |

With two people, one teammate can own both the simulator and ML work. Confirm the shared simulator contract before generating the labeled dataset.

Import `simulate(machine, input_text, step_limit, *, trace_limit=None)` from `backend/app/simulator.py`. Pass the validated machine type defined by the simulator plan. For labels and prefix features, run with `step_limit=1000, trace_limit=10`. For online-equivalent prefix inference, use `step_limit=10, trace_limit=10`. For exact-simulation timing, set `trace_limit=0`. The shared engine returns `steps`, `stop_reason`, and trace events. Use its stop reason to distinguish an observed halt at the limit from a machine that could still execute a rule.

## 2. Files and expected outputs

```text
Toc/
├── DATA_AND_ML_PLAN.md
├── backend/
│   ├── requirements-ml.txt
│   ├── app/
│   │   ├── schemas.py            # Existing shared machine schema
│   │   ├── simulator.py          # Existing shared simulation engine
│   │   ├── features.py           # Ordered, versioned feature extraction
│   │   └── predictor.py          # Offline callable inference
│   ├── experiments/
│   │   ├── config.json
│   │   ├── generate.py
│   │   ├── train.py
│   │   └── evaluate.py
│   └── tests/
│       ├── test_dataset.py       # Generator, labels, determinism, split integrity
│       └── test_predictor.py     # Feature definitions, artifact and scoring parity
├── data/generated/              # One subdirectory per named experiment run
├── models/                      # Selected pipelines and manifest per run
└── report/                      # Metrics, predictions, figures, and final write-up
```

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

## 3. Step 1 · Lock the prediction target and test fixtures

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

## 4. Step 2 · Build the generators and run a pilot

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

## 5. Step 3 · Store the runs and derive features

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

## 6. Step 4 · Freeze splits and train

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

## 7. Step 5 · Evaluate and write the results

| Question | Measurement |
| --- | --- |
| How does the step budget change prediction quality? | Report balanced accuracy, macro F1, confusion matrices, class counts, and test sample sizes at 50, 200, and 1,000 steps. Use the same test cases across budgets. |
| Does the early trace help? | Compare static and static-plus-prefix performance on the same still-active cases. Show full-pipeline results with early observed halts separately. |
| What changes with machine complexity? | Predefine state-count bins after the pilot, then report scores and sample counts in each bin. Include density and input-length summaries so readers can see how those characteristics vary. Flag bins with too few groups or only one observed class. |
| Does performance hold on an unseen family? | Evaluate the reserved family separately and report how its class balance and behavior differ from the main test set. |
| How much computation does prediction save or cost? | Time the warmed-up prediction pipeline, including prefix simulation and feature extraction, against exact simulation with playback trace disabled. Use the same cases and budgets, separate early-halt and still-active cases, and report the environment and median and 95th-percentile latency. |

Produce a table of model metrics, a score-by-budget figure, a complexity breakdown, and several misclassified example traces. Include errors near the budget boundary and at least one machine whose outcome changes with the input if the evaluation set contains such a case. Report the sampling mix and interpret results in the context of the generated families. Treat model scores as scores unless calibration is measured.

## 8. Step 6 · Package and hand off

- Export the selected fitted pipelines for **50, 200, and 1,000** steps, including preprocessing. Load artifacts only from the trusted project build.
- Include a manifest with model ID, budget, feature names and version, prefix length, classification threshold, dataset and split IDs, and dependency versions. Pin the inference environment to compatible package versions.
- Supply API examples for an observed halt, a model prediction, and a simulation that remains active at its limit. Include expected feature values or a feature-row fixture for the parity test.
- Verify that the same example gives the same features and score in the training environment and the callable inference module. Verify both positive halt reasons, including a missing transition exactly at the prefix boundary. Pass these cases to the backend owner for future HTTP parity tests.
- Document the commands for generating data, training, and evaluating, plus expected file outputs. Proposed entry points from the repository root are `python -m backend.experiments.generate`, `python -m backend.experiments.train`, and `python -m backend.experiments.evaluate`. Confirm the commands against the implementation before the demo.

Expose a callable `predict_bounded(machine, input_text, step_limit, models)` that accepts the validated machine and preloaded model bundle. Reject unsupported budgets. Return `source`, `predicted_halted_within_limit`, and `observed_steps`. When `source` is `observed`, include the exact `stop_reason` and omit model fields. When `source` is `model`, include `model_id` and `halt_score`, with the class determined using the manifest threshold. Export selected pipelines as `halt_by_50.joblib`, `halt_by_200.joblib`, and `halt_by_1000.joblib` with `manifest.json`. Validate expected budgets and feature metadata when loading the trusted artifacts. Include these expected response fields in the handoff fixtures for the future API.

## 9. Implementation commands and completion checks

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
