# MORPH-SAT result summary

## Correctness

- Random small-CNF exhaustive check: 760 decisive / 760 correct / 0 wrong; 4,240 safe `UNKNOWN`.
- Hidden-language families: 142 / 142 correct, verified, and independently agreed with decisive Z3 checks.
- Additional cross-language scaling: 36 / 36 correct and verified.
- Random 3-SAT negative control: 200 / 200 `UNKNOWN`; no false claim.
- Unit tests: 11 / 11 passed, including certificate tamper rejection.

## Largest direct-language artifacts

- SAT: 28,672 variables, 229,376 clauses, model independently verified.
- UNSAT: 28,672 variables, 229,376 clauses, 13,286 local equations replayed to `0=1`.
- Recorded median at 8,192 organs: 6.744346 s over three seeds.
- Empirical fitted exponent over tested scales: 1.008030, R² 0.999862.

## Largest recursive-fusion artifacts

- SAT: 1,824 variables, 4,416 clauses, 1,667 exact births, reconstructed model verified.
- UNSAT: 1,824 variables, 4,416 clauses, 4,032 initial relations rederived, 1,679 births replayed, 50 final equations checked to `0=1`.
- Recorded UNSAT solve time: 9.694785 s.
- Empirical fitted exponent over tested scales: 1.783143, R² 0.998005.

## Emergence

- Initial order-trace state: 1,344 relations, no common supported class, affine fraction 0.142857.
- Final state after 558 exact births: 18 relations, affine fraction 1.0.
- Fixed trajectory width experiment: no affine emergence at macro arities 2–5; affine order becomes 1.0 at arity 6.

Full details: `RESEARCH_REPORT_CN.md` and `results/final_evidence.json`.
