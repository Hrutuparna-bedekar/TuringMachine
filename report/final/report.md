# Bounded halting evaluation

Run: `final`. Generated rows: 12,500. Grouped test rows: 1,029, with 609 active at step 10.

The engine reports early observed halts exactly. Models estimate whether an active run will halt within a finite budget. Performance reflects the synthetic dataset and selected holdouts.

## Held-out performance

| Budget | Selected model | Features | Active-only balanced accuracy | Active-only macro F1 | Full-pipeline balanced accuracy | Unseen-family balanced accuracy |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 50 | `mlp_32_static_50` | static | 97.52% | 98.42% | 99.45% | 63.47% |
| 200 | `mlp_32_static_200` | static | 97.63% | 97.69% | 98.67% | 64.92% |
| 1000 | `rf_100_d8_static_plus_prefix_1000` | static_plus_prefix | 98.18% | 98.19% | 99.24% | 86.03% |

The unseen family is `delayed_halts`. It contains 3 distinct machine definitions with multiple inputs each. The main split keeps identical definitions and template lineages together and removes repeated machine/input pairs.

## Best validation result by feature set

| Budget | Static | Static plus prefix |
| ---: | ---: | ---: |
| 50 | 97.12% | 95.49% |
| 200 | 98.56% | 95.78% |
| 1000 | 99.46% | 99.82% |

The full candidate comparison, class counts, confusion matrices, complexity breakdown, and misclassified examples are in [metrics.json](metrics.json).

## Latency

Measured on Windows-11-10.0.26300-SP0 with trace-free exact simulation.

| Budget | Cases | Exact median (ms) | Predictor median (ms) |
| ---: | --- | ---: | ---: |
| 50 | active_at_prefix | 0.128 | 1.313 |
| 50 | early_halt | 0.032 | 0.034 |
| 200 | active_at_prefix | 0.163 | 1.294 |
| 200 | early_halt | 0.037 | 0.038 |
| 1000 | active_at_prefix | 0.361 | 4.023 |
| 1000 | early_halt | 0.034 | 0.035 |

A run that is active at the budget may halt later. The general halting problem remains undecidable.
