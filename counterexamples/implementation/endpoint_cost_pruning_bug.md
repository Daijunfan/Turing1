# Endpoint-cost prefix pruning

Status: `DISPROVED` implementation invariant, fixed before experiments.

The optimized search initially pruned a partial state whenever an existing
goal dominated all non-endpoint cost coordinates.  This is unsound because
`endpoint_solver_cost` is the table size of the endpoint and can decrease after
another contraction.  The naive enumerator exposed multiple missing BCA
frontier vectors and one missing LCA vector.

Fix: prefix dominance is used only if the completed trajectory has endpoint
cost zero, the universal lower bound.  Full optimized/naive Pareto frontiers
then agree on all cross-check formulas.

