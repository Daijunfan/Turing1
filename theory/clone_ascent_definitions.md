# Clone-Ascent Computing and the Clone-Ascent Frontier

## Definition 1 — certified contraction (`PROVED` semantic equivalence)

Let `Gamma_t` be a Boolean CSP and select active relations `S subseteq Gamma_t`.
Let `Y` be variables occurring in the selected relations.  Define

`R' = exists Y . conjunction_(R in S) R`.

`Gamma_(t+1) = (Gamma_t minus S) union {R'}`.

When the eliminated variables occur nowhere outside `S`, this replacement is
solution-equivalent on all surviving variables.  If they do occur outside
`S`, the operation remains a pp-definition but replacement is not in general
solution-equivalent; the implementation therefore rejects such a BCA step.
LCA selects all incident relations, so its eliminated variable is safe by
construction.

The certificate is intentionally representation-level: a checker can
re-enumerate the join and projection without trusting a solver or a gate label.

## Definition 2 — LCA (`PROVED`)

An LCA step selects a variable `x`, contracts all active relations containing
`x`, and eliminates `{x}`.  Born relations may be used recursively unless the
explicit non-recursive ablation is selected.  A trajectory may stop when the
active language obtains a target witness, or continue to full elimination.

MORPH-SAT v0.1 is the configuration with exact-scope grouped initial
relations, at least two incident parents, recursive births, a bound on born
scope, min-scope candidate ordering and early stopping at a supported Schaefer
class.

## Definition 3 — BCA (`PROVED`)

A BCA step selects two active relations `R_1,R_2`.  Let `O` be the union of
the scopes of all other active relations.  It creates

`R' = exists ((S(R_1) union S(R_2)) minus O) . (R_1 and R_2)`.

Thus a variable is projected exactly when it cannot be needed by an outside
active constraint.  A BCA trajectory is a binary join decomposition with
early projection, but it has no implicit joinwidth pruning step.

## Definition 4 — low-arity clone trajectory (`PROVED` as a definition)

`signature_t = intersection_(R in Gamma_t) preservation_signature_leq3(R)`.
The signature has 276 positions: four unary, sixteen binary, and 256 ternary
Boolean truth-table operations.  It is called a low-arity polymorphism
signature, not a complete representation of a Post clone.

The first step adding one of the six named tractability witnesses is the
low-arity clone-crossing time for that witness.

## Definition 5 — CAF (`PROVED` as a definition)

For target filter `T`, let `Traj_T(I)` be all valid certified trajectories
whose endpoint has a witness in `T`.  Map each trajectory to the nine cost
coordinates listed in `notation.md`.  Then

`CAF_T(I) = ParetoMin { cost(tau) : tau in Traj_T(I) }`.

The tuple-count, logarithmic tuple-count, packed-bitset, and measured
join/project operation coordinates are all mandatory.  Scope width alone is
never substituted for CAF.

## Definition 6 — Morphon (`PROVED` as a definition)

A Morphon is a finite gadget whose clause-level initial relations have no
common named Schaefer witness, but a verified recursive trajectory first gains
one after at least two generations.  At least one born relation is a parent of
a later birth; no one-step contraction may reach the target; exact-scope
grouping is disabled; and the property survives variable renaming, independent
literal complementation, and clause reordering.  Gate-like syntax is measured
and reported rather than silently ignored.

