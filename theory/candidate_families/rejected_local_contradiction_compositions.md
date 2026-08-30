# Rejected Morphon compositions

Status: `DISPROVED` as a separation candidate.

## Definition

For each skeleton `G` (path, balanced tree, square grid, bounded-degree random
regular graph, or a graph intended as a Tseitin core), place one copy of the
affine-emergent 4-variable Morphon at every vertex.  Identify local variable 1
with the skeleton vertex and keep the other three variables private.  The size
parameter is `n=|V(G)|`; the formula has `3n+|V(G)|=4n` variables before any
accidental identification and six clauses per gadget.

## Required checklist

1. **Initial language:** each gadget begins without a common named Schaefer
   witness (`COMPUTATIONALLY_VERIFIED`).
2. **Fixed ascent:** each isolated copy has a two-birth LCA trajectory
   (`COMPUTATIONALLY_VERIFIED`).
3. **CAF upper bound:** a constant local trajectory exists, but this statement
   is irrelevant because of the shortcut below (`PROVED`).
4. **Nearest-neighbour lower bound:** none. No unbounded joinwidth,
   backdoor-treewidth, or recursive-backdoor-depth lower bound is claimed.
5. **Recursive birth:** necessary for the affine and Horn catalog items but not
   for the bijunctive item (`COMPUTATIONALLY_VERIFIED`).
6. **One-step shortcut:** there is a stronger constant-size shortcut: every
   isolated gadget is already UNSAT (`COMPUTATIONALLY_VERIFIED`).
7. **Scope recovery:** clause-level trajectories work, but this does not repair
   the contradiction shortcut (`COMPUTATIONALLY_VERIFIED`).
8. **Resolution:** CaDiCaL emits independently checked DRAT proofs of 107–517
   bytes for sizes 2–8 across all skeletons (`COMPUTATIONALLY_VERIFIED`).

## Rejection

Every family member contains a constant-size unsatisfiable subformula.  Hence
the external skeleton, including an expander or Tseitin graph, is semantically
irrelevant and ordinary Resolution has a constant-local refutation.  This is
not an infinite separation family.  It is retained as a negative composition
result so that constant CAF caused by a local contradiction cannot be mistaken
for clone-ascent power.

