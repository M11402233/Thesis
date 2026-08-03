# Zero-Trust Verification of E2 Measurement-Data Trustworthiness for NPN O-RAN Edge Nodes: Defending KPM Falsification via Cross-Node Spatial-Physical Consistency

This repository contains the implementation of a runtime verification framework for **Zero Trust O-RAN Non-Public Networks (NPNs)** developed as part of my master's thesis.

The framework verifies the trustworthiness of O-RAN KPM (Key Performance Measurement) streams by introducing multiple complementary verification residuals, providing an explainable alternative to purely learning-based anomaly detection.

---

## Research Contributions

This repository implements three runtime verification residuals:

- **Cᵢ — Field Cardinality Conservation Residual**
  - Detects violations of field cardinality conservation in a closed NPN.

- **Sᵢ — Spatial Consistency Residual**
  - Detects slow numerical drift using cross-cell spatial consistency.

- **Hᵢ — Mobility Consistency Residual**
  - Verifies UE mobility consistency based on network topology constraints.

These residuals are further combined into a unified runtime trust verification framework for Zero Trust O-RAN.

---

## Repository Structure

```
config/
    Runtime configuration

decoder/
    FlexRIC KPM decoder extensions

docs/
    Architecture and documentation

scripts/
    Data collection and experiment scripts

seeds/
    Benchmark datasets used in the paper

xapps/
    Runtime verification implementation
```

---

## Benchmark Datasets

The repository includes lightweight benchmark datasets required to reproduce the experiments.

```
seeds/
├── batchFinal_seeds/
│   Benchmark datasets for Cᵢ evaluation
│
└── si_lstm_seeds/
    Benchmark datasets for Sᵢ and LSTM baseline evaluation
```

Large ns-3/mmWave simulator traces are intentionally excluded due to GitHub storage limitations.

---

## Requirements

- Python 3.10+
- NumPy
- Matplotlib
- PyTorch (for the LSTM baseline)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running Experiments

```bash
# C_i
python xapps/verification/residuals/run_Ci_experiments.py

# S_i
python xapps/verification/residuals/run_Si_experiments.py

# H_i
python xapps/verification/residuals/run_Hi_experiments.py

# Fusion
python xapps/verification/residuals/run_fusion_replay.py
```

---

## License

This repository is released for academic and research purposes.

