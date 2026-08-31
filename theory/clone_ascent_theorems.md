# Clone-Ascent statements and status

## Theorem 1 — Clone-Ascent Monotonicity Law (`PROVED`)

For every certified contraction,

`Pol(Gamma_t) subseteq Pol(Gamma_(t+1))`.

### Proof

Let `f in Pol(Gamma_t)`.  Every unselected relation in `Gamma_(t+1)` already
belongs to `Gamma_t`, hence is preserved by `f`.  The born relation is defined
from selected parent relations by a conjunction (natural join) followed by
existential quantification (projection).  This is a primitive-positive
definition.  Polymorphisms preserve pp-definable relations: take any arity-many
tuples in the born relation, choose witnesses for their eliminated variables,
apply `f` coordinatewise to the witnessed parent tuples, and use preservation
of every parent.  The coordinatewise result supplies a witness in the join;
projecting it yields the result tuple in the born relation.  Thus `f` preserves
the child and every active relation at `t+1`.

This is a direct application of standard pp-definability/polymorphism
preservation, not a new universal-algebra theorem.  The research object is the
resource-bounded dynamic trajectory and its frontier.

## Corollary 1 — low-arity signature monotonicity (`PROVED`)

`Pol_le3(Gamma_t) subseteq Pol_le3(Gamma_(t+1))`.  The implementation asserts
this after every step; a violation is an implementation counterexample, not an
empirical exception to the theorem.

## C1 — LCA scope width versus induced width (`PROVED`)

Fix a primal-graph variable order.  Before eliminating `x`, the union of the
scopes of all active relations incident with `x`, minus `x`, is contained in
the later-neighbour bag created by ordinary variable elimination for the same
order.  Therefore the maximum born LCA arity is at most that order's induced
width.  Minimizing an early-stopping LCA prefix and then comparing with a full
optimal order gives

`LCA_early_scope(I,T) <= induced_width(I)`.

If width is defined as bag size rather than remaining-neighbour count, add one
on both sides.  This theorem does not compare tuple or discovery cost.

## C2 — v0.1 MorphWidth (`PROVED`, `COMPUTATIONALLY_VERIFIED`)

Modulo its explicit conventions, v0.1 MorphWidth is an early-stopping LCA
scope coordinate: initial exact-scope grouping, all incident parents, at least
two parents, recursive born relations, supported Schaefer target and a bound on
born arity.  The v0.3 regression suite reproduces all twenty v0.2 exact values.
It requires the recorded legacy convention that v0.1 did not label the empty
relation 0-valid or 1-valid; the mathematically standard low-arity signature
correctly treats preservation of the empty relation as vacuous.

## C3 — BCA and early-stop joinwidth (`DISPROVED` as literal equality)

Literal equality is false at the definition level.  Published joinwidth uses a
complete binary join decomposition, separator projection, pruning against all
original constraints, and the normalized maximum tuple-count coordinate.
Default BCA uses no pruning, may stop at a tractability witness, and CAF is a
Pareto vector.  A scalar restriction of BCA with published pruning may still
reduce to an early-stopping joinwidth variant; that restricted equivalence is a
`CONJECTURE` requiring proof or counterexample.

## C4 — CAF dominated by joinwidth (`CONJECTURE`)

No dominance is asserted.  Joinwidth controls a normalized pruned tuple-count
maximum, while CAF also records unpruned operation work, generation depth,
births and endpoint cost.  Exact finite comparison will test coordinate-wise
and scalarized variants.  Finite reversals will not establish asymptotic
incomparability.

## C5 — dominance by backdoor parameters (`CONJECTURE`)

No simple bound by strong backdoor size, backdoor-treewidth, backdoor depth, or
recursive backdoor depth is currently proved.  v0.2 provides finite order
reversals only and also observes the scope inequality in C1.

## C6 — reverse dominance (`CONJECTURE`)

No reverse dominance from CAF to joinwidth or backdoor parameters is currently
proved.  A valid separation claim requires an explicit infinite family and a
symbolic unbounded lower bound; computation alone can only refute proposed
finite inequalities.
