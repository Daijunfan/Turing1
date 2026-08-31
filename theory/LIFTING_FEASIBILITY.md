# Lifted-Morph-Tseitin feasibility

## Status

`DISPROVED` for the v0.3 Morphon catalog.  `CONJECTURE` for a future
satisfiable/functional Morphon not found here.

## Relevant known results

- Ben-Sasson--Wigderson width-to-size reasoning and standard Tseitin expansion
  lower bounds apply to the original hard formulas, not automatically to an
  arbitrary extension-variable encoding.
- Itsykson, Riazanov and Smirnov, *Tight Bounds for Tseitin Formulas* (SAT
  2022), prove tight treewidth-based bounds for **regular Resolution** on
  ordinary Tseitin formulas: https://doi.org/10.4230/LIPIcs.SAT.2022.6.
- Proof-complexity lifting theorems use gadgets satisfying explicit functional,
  stifling, discrepancy, or simulation hypotheses.  Results for lifted
  Resolution-over-XOR or Cutting Planes do not by themselves give a lower bound
  for general Resolution after an arbitrary CNF gadget substitution.

## Applicability checks

1. **Functional encoding:** failed.  Every catalogued v0.3 Morphon is locally
   UNSAT, so it does not implement either value of an external parity bit.
2. **Satisfiability preservation:** failed.  Substitution by the gadget makes
   the formula inconsistent independently of the outer Tseitin charge.
3. **No local refutation:** failed.  A single gadget is a constant-size
   contradiction.
4. **Auxiliary variables preserve hardness:** not established.  No restriction
   or projection lemma maps a short proof of the lifted formula back to a proof
   of the core.
5. **Fixed local clone trajectory:** verified, but irrelevant after failures
   1–3.

## Small proof experiment

`results/family_attempts.csv` contains path, balanced-tree, grid, expander and
Tseitin-core skeletons of sizes 2, 4 and 8.  All 15 formulas are UNSAT.  All 15
DRAT traces pass independent `drat-trim`; proof sizes are 107, 241 and 517 bytes
for the three sizes, independent of skeleton type.  This is evidence of the
unexpected short-proof shortcut, not an asymptotic proof claim.

## Missing lemmas for any future route

1. a satisfiable two-port Morphon implementing both Boolean values;
2. a substitution/restriction lemma preserving Resolution width or size;
3. proof that auxiliary definitions do not expose a bounded-width refutation;
4. a symbolic unbounded lower bound for joinwidth, backdoor-treewidth, or
   recursive backdoor depth of the composed family;
5. removal of every one-gadget and bounded-number-of-gadgets shortcut.

No exponential lower bound is claimed from the finite DRAT experiment.

