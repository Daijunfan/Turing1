# Clone-Ascent notation

Every statement in the v0.3 theory files is prefixed by one of `PROVED`,
`COMPUTATIONALLY_VERIFIED`, `CONJECTURE`, or `DISPROVED`.  A finite exhaustive
search is not called a proof about an infinite class.

## Instances and relations

- The Boolean domain is `D={0,1}`.
- A relation `R` has an ordered scope `S(R)=(x_1,...,x_k)` and a set
  `T(R) subseteq D^k` of allowed tuples.
- `Gamma_t` is the multiset of active scoped relations at time `t`.  Unless a
  legacy ablation explicitly says otherwise, each DIMACS clause is one initial
  relation; clauses with equal scopes are not grouped.
- `join(S)` is the natural join of the relations in a selected active subset
  `S`.  `pi_X(R)` is projection to variables `X`.
- `Pol(Gamma)` is the set of all finitary Boolean operations preserving every
  relation in `Gamma`.
- `Pol_le3(Gamma)` is only the set of preserving operations of arity at most
  three.  It is a low-arity signature and is not asserted to determine a Post
  clone.

## Certified contraction

For active relation indices `A` and internal variables `Y`, a certified
contraction replaces `{R_i : i in A}` by

`R' = pi_(union_i S(R_i) minus Y) (join_i R_i)`.

Its certificate records parent identifiers, parent scopes and bitmasks,
eliminated variables, the joined scope, the projected scope and bitmask,
operation counts, depth and original-clause provenance.

## Models

- `LCA` (Linear Clone Ascent): choose one variable `x`, take every active
  relation incident with `x`, and project `x`.  A legacy option can require at
  least two incident relations, matching MORPH-SAT v0.1.
- `BCA` (Branching Clone Ascent): choose two active relations, join them, and
  project precisely the variables in their union that occur in no other active
  relation.  The two parents are replaced by the child.  This is a binary
  join-project process, not the published joinwidth parameter unless its
  separator and pruning semantics are also imposed.

## Costs and widths

For a trajectory `tau`, the implemented cost record contains:

1. maximum born scope arity `w_scope`;
2. maximum and cumulative allowed-tuple counts;
3. maximum `log2(|R|+1)`;
4. maximum and cumulative truth-table bitset bytes;
5. actual tuple combinations inspected by joins and projections;
6. birth count;
7. maximum generation depth;
8. discovery work (successor candidates and preservation checks);
9. endpoint solver cost.

For a target tractability filter `T`, `CAF_T(I)` is the Pareto-minimal set of
these cost records over certified trajectories reaching `T`.  No scalar named
"CAF width" is used without naming its coordinate or scalarization.

For published joinwidth, `#tup(I)` is the maximum input relation size and the
width of a join-decomposition node `j` is
`log_(#tup(I)) |C(j)|`, where `C(j)` is obtained by natural join, projection to
the subtree/outside separator, and pruning against every original constraint.
Linear joinwidth restricts each internal node to have a leaf child.

## Tractability witnesses

The named low-arity witnesses are constant 0, constant 1, binary AND, binary
OR, ternary majority and ternary minority/XOR.  Their simultaneous presence is
reported directly from `Pol_le3`; class names are not inferred from syntax.

