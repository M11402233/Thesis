# Benchmark Datasets

This directory contains the benchmark datasets used in the experiments presented in the thesis.

The raw ns-3/mmWave simulation traces are intentionally excluded from this repository due to their large size (>100 MB per trace).

Only the processed benchmark datasets required to reproduce the experiments are provided.

---

## Directory Structure

```
seeds/
├── batchFinal_seeds/
└── si_lstm_seeds/
```

---

## batchFinal_seeds/

Baseline datasets used for evaluating the **Cᵢ (Field Cardinality Conservation Residual)**.

Contents:

- 10 independent simulation seeds
- Seven-UE O-RAN NPN scenario
- Used in cardinality conservation experiments

```
seed4200.txt
...
seed4209.txt
```

---

## si_lstm_seeds/

Benchmark datasets used for evaluating the **Sᵢ residual** and the **single-node LSTM baseline**.

Contents:

- Four independent 300-second simulations
- LTE anchor cell throughput sequences
- Used in the LSTM baseline comparison

```
ues1_t300_seed4200.txt
...
ues1_t300_seed4203.txt
```

---

## Notes

The original simulator traces (e.g., `DlPhyTransmissionTrace.txt`,
`RxPacketTrace.txt`, `MmWaveSinrTime.txt`) are not included.

These benchmark datasets are sufficient to reproduce all experiments reported in this repository.
