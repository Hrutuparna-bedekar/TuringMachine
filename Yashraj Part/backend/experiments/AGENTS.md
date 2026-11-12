# Turing Machine Simulator and Bounded Halting Predictor — Antigravity handoff

## Role and working style
You are taking over development of the **data generation, validation, feature extraction, and ML** workstream in an existing university Theory of Computation team project. Act as a coding agent on the local repository. Inspect code and execute tests rather than assuming this document guarantees current file contents. The user prefers complete, tested changes with concise reasoning and a final summary, **not** dozens of micro-steps or repeated manual copy-pasting. Explain key choices, but do the implementation yourself. Ask for approval before destructive changes or changes outside this workstream; never fabricate test results.

## Local repository / environment
- Windows, PowerShell; workspace: `C:\Users\TUF\TuringMachine\Yashraj Part`
- GitHub repository: `https://github.com/Hrutuparna-bedekar/TuringMachine`
- User's working branch was `Shantanu-part` (based on `yashraj-part`); **check actual branch and worktree**, do not reset/rebase/merge or commit unless explicitly asked.
- Python 3.13 in `.venv` inside `Yashraj Part`. Use existing interpreter and dependencies. Commands run from `Yashraj Part`:
  - `python -m pytest backend/tests/test_simulator.py -v` (previously 29 passed)
  - `python -m backend.experiments.generate_pilot`
- Keep changes scoped to the user's data/ML responsibility; teammates own the simulator/backend API and frontend. Avoid changing `backend/app/simulator.py` and `backend/app/schemas.py` without review.

## Existing implementation (verify against disk)
- `backend/app/schemas.py`: validated Pydantic `TuringMachine` schema.
- `backend/app/simulator.py`: authoritative deterministic single-tape simulator, import `simulate(machine, input_text, step_limit=1000, trace_limit=10)`.
- `backend/experiments/machine_generators.py`: existing `generate_random_machine`, `generate_scan_machine`, `generate_loop_machine`.
- `backend/experiments/generate.py`: prototype data creation with `create_record`; structured so importing does not execute generation.
- `backend/experiments/generator_prototype.py`, `backend/experiments/smoke_demo.py`: earlier backups; preserve.
- `backend/experiments/generate_pilot.py`: full, seeded 500-machine dataset generator. It creates different random, scan-delay, and cyclic-loop machine configurations and writes JSONL. Inspect implementation: scan and loop variants are related templates; distinct JSON definitions do **not** imply independent behaviors.
- `data/generated/pilot_v1/machines.jsonl` and `runs.jsonl`: generated locally.
- If present, read `DATA_AND_ML_PLAN.md` and `PROJECT_PLAN.md` as the primary project specifications. The project deliverable is bounded halting prediction, **not** solving the general undecidable Halting Problem.

## Most recent observed successful run (user's actual PowerShell output)
```
Machines saved: 500
Records saved: 2500
Machine families: {'cyclic_loop': 100, 'random_rule_tables': 225, 'scan_delay': 175}
Stop reasons: {'step_limit': 813, 'missing_transition': 682, 'final_state': 1005}
Budget 50: positive=1330, negative=1170
Budget 200: positive=1509, negative=991
Budget 1000: positive=1687, negative=813
Output directory: data\generated\pilot_v1
```
Those are **observations**, not a certification of generalization or ML readiness. Generator checks counts/duplicate machine definitions/unique inputs/monotonic labels, but further quality tests and independent verification are needed.

## Simulator/label semantics — critical invariants
- Prediction target: machine halts on this exact input within **50, 200, or 1000 executed transitions**.
- Both `stop_reason='final_state'` and `stop_reason='missing_transition'` are observed halts. A missing transition can halt at step 0. Halting at exactly a budget is positive.
- `stop_reason='step_limit'` means **not observed to halt within the budget**, NOT a proof of non-halting forever. When still active at step 1000, labels `[0,0,0]`.
- Use actual deterministic simulator for ground-truth labels; no heuristic labels based on family type.
- For known halt at transition T, `halt_by_B = int(T <= B)`.
- Label ordering must obey `halt_by_50 <= halt_by_200 <= halt_by_1000`.
- Example scan-to-blank with input `'1'*50` halts in 51 transitions and labels `[0,1,1]`. Input `'1'*200` halts in 201 and labels `[0,0,1]`. Input `'1'*1000` hits step limit at 1000 and labels `[0,0,0]`.
- Simulate labeling with `step_limit=1000, trace_limit=10`. A bounded prefix at step 10 is allowed as an ML input; eventual halt result is a label, **never an ML feature**.

## Data quality risks identified and goals
Current pilot is balanced reasonably at each budget but its labels are potentially confounded with the synthetic families: cyclic loops are all active through the budget, scan delays are structurally simple, random machines often halt quickly or remain active. Many machines have the same labels across all five inputs. It may appear accurate because the model learns synthetic template membership rather than behavior. Need more independent machines and genuinely input-dependent behavior; do not jump to model accuracy claims before proper audits.

### Immediate next assignment — implement and test, not just describe
1. Inspect local files, Git status, simulator/schema, existing plans (if present), generator and generated JSONL files. Don't overwrite user work. Report any inconsistencies between this handoff and code.
2. Build a **standalone reproducible data-quality audit** (`backend/experiments/audit_pilot.py` or similar), and targeted tests. Validate IDs, machine definitions (using schema), each run's reference and input validity, duplicates, exact label boundaries, monotonicity, re-simulate sampled examples including T=0/50/51/200/201/1000, stop reason proportions, input-dependent label changes **within machines**, class balance by family/budget and on subset still active after 10 steps (re-simulate prefix where needed), and lineage/template overlap risk. Compute effective sample/groups, not only raw 2,500 rows. A real simulator return can distinguish an observed halt at step 1000 from continued activity; respect it. Produce a human-readable JSON/Markdown summary.
3. Based on audit results, improve the generator with input-dependent branching and other nontrivial machine families (multi-pass scans, left/right movement, symbol rewrites/erase, delayed halts). Ensure variations actually affect behavior, generate valid machines, avoid trivially determining target by family. Preserve pilot_v1; put new generated outputs under a new run directory (e.g. `pilot_v2`). Add deterministic seeds and tests.
4. Implement properly grouped machine/template-lineage splits with no leakage; check class coverage across budgets and among cases still active at step 10. Save split manifest. If class coverage is insufficient, refine the generator before training.
5. Only then implement shared static and first-10-step feature extractor, baseline, Decision Tree, Random Forest, small MLP, training/evaluation and callable predictor according to `DATA_AND_ML_PLAN.md`. Separate observed early halts from learned predictions. Test feature parity, never leak stop reason/executed_steps/halt_step/IDs/family/lineage/full trace into features. Save models/metrics/manifests only after verification. Do not claim untested generalization.

## Feature protocol from original plan
Static ordered columns: `state_count`, `tape_alphabet_size`, `rule_density`, `final_reachable`, `self_loop_fraction`, `left_move_fraction`, `right_move_fraction`, `input_length`, `input_symbol_diversity`.
Append prefix columns: `prefix_states_visited`, `prefix_head_displacement`, `prefix_tape_span`, `prefix_symbol_changes`, `prefix_rule_repeats`.
Use only machine definition, input, and at most 10 simulation transitions. Do not use end-of-run diagnostic metadata as input. For online inference, if halt is actually observed in first 10 steps, report exact outcome; otherwise use model predictions. Freeze split by machine and template lineage, not random row split.

## Working practices and boundaries
- First show a concise plan, inspect code, then **execute** implementation and tests. Give the user completed files and a clear run command/summary rather than asking them to paste snippets.
- Prioritize correctness and leakage prevention over target counts or flashy accuracy numbers.
- Don't delete `pilot_v1`, prototype backups, or untracked user files. No force pushes, resets, rebase, or background tasks.
- No network calls necessary for the dataset audit; work with the local simulator and files.
- If repo plans differ from this summary, flag and reconcile differences with actual specification before modifying code.
