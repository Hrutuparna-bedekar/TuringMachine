# `pilot_v2` Model Training & Evaluation Report

- **Dataset**: `data\generated\pilot_v2` (`train` active=3258, `val` active=648, `test` active=626, `test` full=690)
- **Zero-Leakage Grouping**: Connected components of `(lineage_id, behavioral_signature)`

## 1. Selected `pilot_v2` Models vs. `models/final` on `pilot_v2` Test Set

| Budget | Selected `pilot_v2` Model | `pilot_v2` Active Bal Acc | `pilot_v2` Active F1 | `pilot_v2` Full Bal Acc | `models/final` Active Bal Acc |
|---:|---|---:|---:|---:|---:|
| **50** | `rf_100_d8_static_plus_prefix_50` | **0.8434** | **0.8622** | **0.8812** | 0.3834 |
| **200** | `rf_100_d8_static_plus_prefix_200` | **0.8847** | **0.8868** | **0.8891** | 0.5321 |
| **1000** | `rf_100_d8_static_plus_prefix_1000` | **0.7894** | **0.8224** | **0.7908** | 0.4927 |

## 2. Static vs. Static+Prefix Comparison (Active Test Set)

| Budget | Candidate | Feature Set | Val Bal Acc | Test Bal Acc | Test Macro F1 | Test ROC-AUC |
|---:|---|---|---:|---:|---:|---:|
| 50 | `majority` | `static` | 0.5000 | 0.5000 | 0.4225 | 0.5000 |
| 50 | `dt_depth3` | `static` | 0.7748 | 0.7730 | 0.7930 | 0.9102 |
| 50 | `dt_depth5` | `static` | 0.7814 | 0.8353 | 0.8272 | 0.9339 |
| 50 | `dt_depth8` | `static` | 0.7924 | 0.8225 | 0.8100 | 0.9043 |
| 50 | `rf_100_d8` | `static` | 0.8302 | 0.8206 | 0.8342 | 0.9551 |
| 50 | `mlp_32` | `static` | 0.7835 | 0.7447 | 0.7572 | 0.8805 |
| 50 | `majority` | `static_plus_prefix` | 0.5000 | 0.5000 | 0.4225 | 0.5000 |
| 50 | `dt_depth3` | `static_plus_prefix` | 0.7638 | 0.7565 | 0.7808 | 0.9036 |
| 50 | `dt_depth5` | `static_plus_prefix` | 0.8317 | 0.8107 | 0.8095 | 0.9294 |
| 50 | `dt_depth8` | `static_plus_prefix` | 0.8143 | 0.8538 | 0.8465 | 0.9244 |
| 50 | `rf_100_d8` | `static_plus_prefix` | 0.8549 | 0.8434 | 0.8622 | 0.9675 |
| 50 | `mlp_32` | `static_plus_prefix` | 0.6029 | 0.5863 | 0.5902 | 0.7294 |
| 200 | `majority` | `static` | 0.5000 | 0.5000 | 0.3459 | 0.5000 |
| 200 | `dt_depth3` | `static` | 0.8060 | 0.8118 | 0.8134 | 0.8775 |
| 200 | `dt_depth5` | `static` | 0.8505 | 0.8290 | 0.8287 | 0.8999 |
| 200 | `dt_depth8` | `static` | 0.8373 | 0.8247 | 0.8259 | 0.8680 |
| 200 | `rf_100_d8` | `static` | 0.8454 | 0.8511 | 0.8520 | 0.9348 |
| 200 | `mlp_32` | `static` | 0.7856 | 0.7800 | 0.7799 | 0.8729 |
| 200 | `majority` | `static_plus_prefix` | 0.5000 | 0.5000 | 0.3459 | 0.5000 |
| 200 | `dt_depth3` | `static_plus_prefix` | 0.8486 | 0.8160 | 0.8167 | 0.8870 |
| 200 | `dt_depth5` | `static_plus_prefix` | 0.8855 | 0.8581 | 0.8596 | 0.9147 |
| 200 | `dt_depth8` | `static_plus_prefix` | 0.9010 | 0.8667 | 0.8680 | 0.8990 |
| 200 | `rf_100_d8` | `static_plus_prefix` | 0.9133 | 0.8847 | 0.8868 | 0.9553 |
| 200 | `mlp_32` | `static_plus_prefix` | 0.8591 | 0.8472 | 0.8492 | 0.9216 |
| 1000 | `majority` | `static` | 0.5000 | 0.5000 | 0.4262 | 0.5000 |
| 1000 | `dt_depth3` | `static` | 0.6426 | 0.6276 | 0.6446 | 0.7459 |
| 1000 | `dt_depth5` | `static` | 0.7497 | 0.7205 | 0.7453 | 0.8123 |
| 1000 | `dt_depth8` | `static` | 0.7479 | 0.7120 | 0.7339 | 0.7984 |
| 1000 | `rf_100_d8` | `static` | 0.7578 | 0.7090 | 0.7327 | 0.8733 |
| 1000 | `mlp_32` | `static` | 0.7019 | 0.6755 | 0.6931 | 0.8228 |
| 1000 | `majority` | `static_plus_prefix` | 0.5000 | 0.5000 | 0.4262 | 0.5000 |
| 1000 | `dt_depth3` | `static_plus_prefix` | 0.7414 | 0.7007 | 0.7231 | 0.7839 |
| 1000 | `dt_depth5` | `static_plus_prefix` | 0.8599 | 0.7850 | 0.8123 | 0.8399 |
| 1000 | `dt_depth8` | `static_plus_prefix` | 0.8649 | 0.8360 | 0.8634 | 0.8739 |
| 1000 | `rf_100_d8` | `static_plus_prefix` | 0.8656 | 0.7894 | 0.8224 | 0.9198 |
| 1000 | `mlp_32` | `static_plus_prefix` | 0.8322 | 0.7499 | 0.7810 | 0.8877 |
