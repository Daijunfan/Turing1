# Canonical-state depth omission

Status: `DISPROVED` implementation invariant, fixed before experiments.

The first optimized-vs-naive cross-check failed on 2026-08-31.  The naive
frontier contained cost vector

`(2, 7, 22, 3.0, 1, 8, 2, 1, 123, 2)`

which the optimized search had pruned.  The canonical memo key contained only
active relation scopes and masks.  Two isomorphic semantic states can attach
the same relations to different generation depths, which changes future depth
cost and the non-recursive-birth ablation.  Merging them was unsound.

Fix: the canonical multiset now contains `(scope, mask, relation_depth)` and
renames only the variable coordinates.  The independent no-pruning enumerator
is retained as a regression oracle.

