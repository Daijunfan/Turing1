# MORPH-SAT

**MORPH-SAT: Morphogenetic Polymorphism Compilation for Boolean Constraints**

MORPH-SAT is a certified research prototype for **endogenous constraint-language computation**. It receives an ordinary DIMACS CNF without XOR annotations, gate labels, graph metadata, or relation boundaries. Instead of committing to one solver in advance, it:

1. reconstructs bounded local Boolean relations from clauses;
2. repeatedly creates exact macro-relations by local join and existential projection;
3. measures which algebraic closure operations (polymorphisms) are becoming common;
4. when a common tractable language emerges, compiles the residual instance into the matching exact algorithm;
5. reconstructs a model or emits a replayable contradiction certificate.

Implemented backends:

- affine/minority relations → Gaussian elimination over `GF(2)`;
- bijunctive/majority relations → 2-SAT SCC;
- Horn/AND relations → forward chaining;
- dual-Horn/OR relations → dual forward chaining;
- 0-valid and 1-valid relations → immediate canonical model.

If bounded exact fusion does not expose a supported language, the solver returns `UNKNOWN`; it does not guess.

## Core operation

For all active relations incident to variable `x`, MORPH-SAT births a new relation

```text
R_new(B) = exists x . AND_i R_i(B_i, x)
```

and replaces the parents by `R_new`. This is exact bucket elimination restricted by a maximum macro-relation arity. Every fusion is logged and independently replayable.

The new runtime order parameter for a polymorphism `p` is

```text
Omega_p(t) = (# active relations preserved by p) / (# active relations).
```

A tractable language emerges at the first step where `Omega_p(t) = 1` for a supported `p`.

## Quick use

```bash
python3 solve.py instance.cnf --mode auto
python3 solve.py instance.cnf --mode fusion --max-macro-arity 8
python3 solve.py sat_instance.cnf --model-out model.json
python3 verify_model.py sat_instance.cnf model.json
```

Verify an UNSAT certificate:

```bash
python3 verify_certificate.py \
  results/flagship_direct_8192.cnf \
  results/flagship_direct_8192.cert.json

python3 verify_fusion_certificate.py \
  results/flagship_gate_fusion_192.cnf \
  results/flagship_gate_fusion_192.cert.json
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the complete validation suite:

```bash
python3 experiments/run_validation.py
```

## Reproduced headline evidence

- 5,000 random six-variable CNFs checked against exhaustive enumeration. MORPH-SAT made 760 decisive claims; all 760 were correct and internally verified. The other 4,240 returned `UNKNOWN`.
- 142 hidden-language SAT/UNSAT instances spanning direct affine, recursively fused affine, 2-SAT, and Horn families: 142/142 correct, 142/142 verified, and 142/142 agreement with an independent Z3 run when Z3 was decisive.
- 36 additional cross-language scaling instances: 36/36 correct and verified.
- Direct hidden-affine scaling reached 28,672 variables and 229,376 ordinary CNF clauses. Median solve time over three seeds was 6.744 s in the recorded environment; empirical power-law exponent 1.008 (`R²=0.99986`) over tested sizes.
- Heterogeneous compact AND/OR/NOT tissue reached 1,824 variables and 4,416 clauses, with 1,679 exact fusion births and a verified affine contradiction.
- The 608-variable order-trace instance began with 1,344 relations, no common supported polymorphism, and only 14.29% affine relations. After 558 exact local fusions, all 18 residual relations were affine.
- A fixed width-threshold instance failed to expose affine order under macro arities 2–5; at arity 6 the final affine order parameter became 1.0.
- 200 random phase-transition 3-SAT negative controls produced 200 `UNKNOWN` results, with no false claim.
- Standalone model and UNSAT-certificate checkers validate outputs directly against the original DIMACS input.

These are **finite experimental results**, not a proof that the algorithm is polynomial on arbitrary CNF and not a guarantee of scientific prizes.

## Repository map

```text
morphosat/
  cnf.py                  DIMACS and model checking
  relations.py            exact bounded truth-table relation recovery
  schaefer.py              semantic polymorphism/class recognition
  fusion.py                exact join/project births and order trace
  fusion_solver.py         adaptive morphogenetic compiler
  affine.py                GF(2) backend and provenance
  tractable.py             2-SAT and Horn backends
  certificate.py           direct affine certificate
  fusion_certificate.py    full fusion + affine certificate
  generators.py            hidden-language benchmark generators
  z3ffi.py                 optional independent Z3 C-API wrapper

experiments/run_validation.py
results/                   raw CSV/JSON, flagship CNFs and certificates
figures/                   generated plots
tests/                     soundness, model, certificate, and tamper tests
```

## Requirements

Core solver:

- Python 3.11 or newer.

Benchmark generation and experiments:

- NetworkX
- NumPy
- pandas
- Matplotlib
- optional system `libz3` for independent cross-checks.

See `requirements.txt`.

## Scope and limits

The current prototype is exact but intentionally incomplete:

- local truth tables are bounded to small arity;
- exact fusion can suffer width explosion;
- only Boolean Schaefer tractable languages are compiled;
- the benchmark families are synthetic and semantically obfuscated, not a substitute for SAT Competition evaluation;
- no theorem yet proves that the current local trajectory policy discovers a tractable language whenever a low-width successful trajectory exists;
- no formal lower bound yet separates this model from all strong modern no-new-language proof systems.

The research report states precisely what has been established and what remains open.
