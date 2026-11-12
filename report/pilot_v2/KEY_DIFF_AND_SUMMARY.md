# Key Differences & Improvements (`Shantanu-part` vs. `origin/Trained-Model`)

This document summarizes the data-quality audit, dataset upgrades, zero-leakage splitting, retrained models, and inference improvements added on `Shantanu-part` after fast-forward merging `origin/Trained-Model` (`6a06db8`).

---

## 1. Side-by-Side Comparison

| Area | `origin/Trained-Model` (`6a06db8`) | `Shantanu-part` Additions & Upgrades |
|---|---|---|
| **Data Quality Audit** | None | `backend/experiments/audit_pilot.py` — validates schemas, full re-simulation, exact boundary steps (`T = 0, 10, 11, 49, 50, 51, 199, 200, 201, 999, 1000`), within-machine variance, and behavioral-clone collapse. |
| **Dataset (`pilot_v2`)** | `backend/experiments/generate.py` (`m_idx // 10` lineages; 6 fixed scan templates) | `backend/experiments/generate_pilot_v2.py` — 1,000 unique machines $\times$ 5 distinct inputs = **5,000 runs** across 5 symbol-branching families (`99.7%` within-machine label variation, `0` symbol-agnostic machines, `0` inputs $>512$ chars, `25%` unconfounded `final_reachable = 0`). |
| **Train / Val / Test Splits** | Grouped only by `lineage_id` (`m_idx // 10`) | `backend/experiments/split_dataset.py` — groups by connected components of **both** `lineage_id` and 12-probe behavioral equivalence (`0` clone leakage across splits). |
| **Leak-Free CSV Export** | Parquet only (`runs.parquet`, `features.parquet`) | `backend/experiments/export_features_csv.py` — exports `features_and_labels.csv` (5,000 rows) and `features_active_after_10.csv` (4,532 active rows) with diagnostic/leakage columns excluded. |
| **Trained Models & Generalization** | `models/final/` (`0.3834` / `0.5321` / `0.4927` active balanced accuracy on unseen `pilot_v2` test set) | `backend/experiments/train_pilot_v2.py` & `models/pilot_v2/` (**`0.8434` / `0.8847` / `0.7894`** active balanced accuracy; **`0.8812` / `0.8891` / `0.7908`** full pipeline balanced accuracy). |
| **Inference (`predictor.py`)** | Single-budget `predict_bounded(...)` | Added `predict_all_budgets(...)` in `backend/app/predictor.py` enforcing monotonic probabilities & labels across `50 <= 200 <= 1000`. |
| **Automated Tests** | 66 tests (`test_simulator.py`, `test_api.py`, `test_ml_fixtures.py`, `test_dataset.py`, `test_predictor.py`) | Added 14 tests in `backend/tests/test_audit_and_pilot.py` (**80 total passing**). |

---

## 2. Preserved Files (Per Project Guidelines)

- `data/generated/pilot_v1/` and prototype scripts (`generator_prototype.py`, `smoke_demo.py`, `generate_v1_proto.py`) are preserved as historical baselines.
- `models/final/` and `report/final/` from `origin/Trained-Model` are preserved untouched alongside `models/pilot_v2/` and `report/pilot_v2/`.

---

## 3. Verification Commands

Run from `Yashraj Part`:

```powershell
# Re-generate pilot_v2, audit, split, and export CSVs
.\.venv\Scripts\python.exe -m backend.experiments.generate_pilot_v2
.\.venv\Scripts\python.exe -m backend.experiments.audit_pilot --data-dir data/generated/pilot_v2
.\.venv\Scripts\python.exe -m backend.experiments.split_dataset --data-dir data/generated/pilot_v2
.\.venv\Scripts\python.exe -m backend.experiments.export_features_csv --data-dir data/generated/pilot_v2

# Train & evaluate pilot_v2 models
.\.venv\Scripts\python.exe -m backend.experiments.train_pilot_v2

# Run full test suite (80 passed)
.\.venv\Scripts\python.exe -m pytest backend/tests -v
```

