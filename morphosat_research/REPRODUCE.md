# Reproduction guide

Run commands from the repository root.

## 1. Syntax and unit tests

```bash
python3 -m compileall -q morphosat tests experiments solve.py \
  verify_model.py verify_certificate.py verify_fusion_certificate.py
python3 -m unittest discover -s tests -v
```

## 2. Verify the largest supplied UNSAT artifacts

```bash
python3 verify_certificate.py \
  results/flagship_direct_8192.cnf \
  results/flagship_direct_8192.cert.json

python3 verify_fusion_certificate.py \
  results/flagship_gate_fusion_192.cnf \
  results/flagship_gate_fusion_192.cert.json
```

Expected invariant in both outputs:

```json
{"final_coefficient_weight": 0, "final_rhs": 1, "verified": true}
```

## 3. Verify supplied SAT models

```bash
python3 verify_model.py \
  results/flagship_direct_8192_sat.cnf \
  results/flagship_direct_8192_sat.model.json

python3 verify_model.py \
  results/flagship_gate_fusion_192_sat.cnf \
  results/flagship_gate_fusion_192_sat.model.json
```

Both checkers independently parse DIMACS and test every original clause.

## 4. Inspect raw evidence

- `results/correctness_summary.json`
- `results/correctness_families.csv`
- `results/direct_affine_scaling.csv`
- `results/fusion_affine_scaling.csv`
- `results/cross_language_emergence.csv`
- `results/polymorphism_order_trace.csv`
- `results/width_threshold.csv`
- `results/random_3sat_negative_control.csv`
- `results/adaptive_trajectory_ablation.csv`
- `results/validation_summary.json`

## 5. Regenerate the main suite

```bash
python3 experiments/run_validation.py
```

The script uses fixed seeds and writes each scaling row incrementally.
