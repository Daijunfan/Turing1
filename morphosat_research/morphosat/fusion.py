from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .relations import RelationBlock
from .schaefer import classify_block


@dataclass(slots=True)
class MacroRelation:
    relation_id: int
    scope: tuple[int, ...]
    allowed: tuple[int, ...]
    parents: tuple[int, ...]
    eliminated_variable: int | None
    depth: int
    original_blocks: frozenset[int]
    classes: frozenset[str] = field(default_factory=frozenset)
    representations: dict[str, object] = field(default_factory=dict)

    @property
    def arity(self) -> int:
        return len(self.scope)


@dataclass(slots=True)
class FusionStep:
    new_relation_id: int
    parent_ids: tuple[int, ...]
    eliminated_variable: int
    new_scope: tuple[int, ...]
    new_allowed: tuple[int, ...]
    depth: int


@dataclass(slots=True)
class FusionResult:
    relations: list[MacroRelation]
    steps: list[FusionStep]
    all_relations: dict[int, MacroRelation]
    common_classes: frozenset[str]
    eliminated_variables: int
    max_depth: int
    elapsed_seconds: float
    exact_steps_verified: bool
    order_trace: list[dict[str, object]]


def _classify_macro(rel: MacroRelation) -> None:
    proxy = RelationBlock(
        block_id=rel.relation_id,
        scope=rel.scope,
        clause_ids=tuple(),
        clauses=tuple(),
        allowed=rel.allowed,
    )
    classify_block(proxy)
    rel.classes = proxy.classes
    rel.representations = proxy.representations


def common_tractable_classes(relations: list[MacroRelation]) -> frozenset[str]:
    common: set[str] | None = None
    universe = {"affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid"}
    for rel in relations:
        if not rel.classes:
            _classify_macro(rel)
        c = set(rel.classes) & universe
        common = c if common is None else common & c
    return frozenset(common or set())


def _relation_holds(rel: MacroRelation, assignment: dict[int, int]) -> bool:
    t = 0
    for i, var in enumerate(rel.scope):
        t |= (assignment[var] & 1) << i
    return t in rel.allowed


def _project_join(parents: list[MacroRelation], eliminate: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    union = sorted({v for rel in parents for v in rel.scope})
    if eliminate not in union:
        raise ValueError("elimination variable not in parent scopes")
    scope = tuple(v for v in union if v != eliminate)
    allowed: list[int] = []
    for t in range(1 << len(scope)):
        base = {v: (t >> i) & 1 for i, v in enumerate(scope)}
        ok = False
        for value in (0, 1):
            base[eliminate] = value
            if all(_relation_holds(rel, base) for rel in parents):
                ok = True
                break
        if ok:
            allowed.append(t)
    return scope, tuple(allowed)


def verify_fusion_step(parents: list[MacroRelation], step: FusionStep) -> bool:
    scope, allowed = _project_join(parents, step.eliminated_variable)
    return scope == step.new_scope and allowed == step.new_allowed


def final_relations_hold(result: FusionResult, assignment: int) -> bool:
    values = {v: (assignment >> (v - 1)) & 1
              for rel in result.relations for v in rel.scope}
    return all(_relation_holds(rel, values) for rel in result.relations)


def reconstruct_eliminated_assignment(result: FusionResult, final_assignment: int, nvars: int) -> int | None:
    """Reverse exact existential fusion and reconstruct a full CNF assignment.

    Every fusion step stores R_new = exists v . conjunction(parents).  Given a
    satisfying assignment of the final macro relations, reverse traversal can
    therefore choose a witness value for each eliminated variable.
    """
    values = {v: (final_assignment >> (v - 1)) & 1 for v in range(1, nvars + 1)}
    for step in reversed(result.steps):
        parents = [result.all_relations[rid] for rid in step.parent_ids]
        witness = None
        for bit in (0, 1):
            values[step.eliminated_variable] = bit
            if all(_relation_holds(rel, values) for rel in parents):
                witness = bit
                break
        if witness is None:
            return None
        values[step.eliminated_variable] = witness
    assignment = 0
    for var, bit in values.items():
        if bit:
            assignment |= 1 << (var - 1)
    return assignment


def fuse_until_tractable(
    initial_blocks: list[RelationBlock],
    max_macro_arity: int = 8,
    stop_preference: tuple[str, ...] = ("affine", "bijunctive", "horn", "dual_horn"),
    max_steps: int | None = None,
    tie_seed: int = 0,
) -> FusionResult:
    """Exact bounded existential fusion.

    At each step, all relations incident to a variable are joined and that
    variable is existentially projected. The candidate with minimum resulting
    scope is selected. This is a representation-birth operation: heterogeneous
    local relations can become a new relation with a different polymorphism.
    """
    start = perf_counter()
    relations: dict[int, MacroRelation] = {}
    history: dict[int, MacroRelation] = {}
    next_id = 0
    for block in initial_blocks:
        rel = MacroRelation(
            relation_id=next_id,
            scope=block.scope,
            allowed=block.allowed,
            parents=tuple(),
            eliminated_variable=None,
            depth=0,
            original_blocks=frozenset({block.block_id}),
        )
        _classify_macro(rel)
        relations[next_id] = rel
        history[next_id] = rel
        next_id += 1

    steps: list[FusionStep] = []
    max_depth = 0
    exact_ok = True
    order_trace: list[dict[str, object]] = []

    def snapshot(step_index: int, current: dict[int, MacroRelation], common_now: frozenset[str]) -> None:
        rels = list(current.values())
        denom = max(1, len(rels))
        classes = ("affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid")
        item: dict[str, object] = {
            "step": step_index,
            "relation_count": len(rels),
            "max_arity": max((r.arity for r in rels), default=0),
            "mean_depth": (sum(r.depth for r in rels) / len(rels)) if rels else 0.0,
            "common_classes": sorted(common_now),
        }
        for c in classes:
            item[f"{c}_fraction"] = sum(c in r.classes for r in rels) / denom
        order_trace.append(item)

    def preferred(common: frozenset[str]) -> bool:
        return any(c in common for c in stop_preference)

    common = common_tractable_classes(list(relations.values()))
    snapshot(0, relations, common)
    if preferred(common):
        return FusionResult(
            list(relations.values()), steps, history, common, 0, 0,
            perf_counter() - start, True, order_trace
        )

    while True:
        if max_steps is not None and len(steps) >= max_steps:
            break
        incidence: dict[int, list[int]] = {}
        for rid, rel in relations.items():
            for v in rel.scope:
                incidence.setdefault(v, []).append(rid)

        candidates: list[tuple[int, int, int, int, int, tuple[int, ...]]] = []
        # score = resulting width, number of parents, total parent arity,
        # deterministic seeded tie order, variable id. Different tie seeds give
        # exact alternative developmental trajectories without changing semantics.
        for var, rids in incidence.items():
            if len(rids) < 2:
                continue
            union = {x for rid in rids for x in relations[rid].scope}
            width = len(union) - 1
            if width <= max_macro_arity:
                total_arity = sum(relations[rid].arity for rid in rids)
                tie = var if tie_seed == 0 else (((var * 0x9E3779B1) ^ (tie_seed * 0x85EBCA77)) & 0xFFFFFFFF)
                candidates.append((width, len(rids), total_arity, tie, var, tuple(sorted(rids))))
        if not candidates:
            break
        candidates.sort()
        _, _, _, _, var, parent_ids = candidates[0]
        parents = [relations[rid] for rid in parent_ids]
        new_scope, new_allowed = _project_join(parents, var)
        depth = max(p.depth for p in parents) + 1
        original = frozenset().union(*(p.original_blocks for p in parents))
        new_rel = MacroRelation(
            relation_id=next_id,
            scope=new_scope,
            allowed=new_allowed,
            parents=parent_ids,
            eliminated_variable=var,
            depth=depth,
            original_blocks=original,
        )
        _classify_macro(new_rel)
        history[next_id] = new_rel
        step = FusionStep(next_id, parent_ids, var, new_scope, new_allowed, depth)
        exact_ok &= verify_fusion_step(parents, step)
        for rid in parent_ids:
            del relations[rid]
        # A tautological zero-arity or full relation can be omitted. An empty
        # relation must be retained because it is an UNSAT witness.
        if len(new_allowed) != (1 << len(new_scope)) or not new_allowed:
            relations[next_id] = new_rel
        next_id += 1
        steps.append(step)
        max_depth = max(max_depth, depth)

        if not relations:
            common = frozenset({"zero_valid", "one_valid", "affine", "horn", "dual_horn", "bijunctive"})
            break
        common = common_tractable_classes(list(relations.values()))
        snapshot(len(steps), relations, common)
        if preferred(common):
            break

    return FusionResult(
        relations=list(relations.values()),
        steps=steps,
        all_relations=history,
        common_classes=common,
        eliminated_variables=len(steps),
        max_depth=max_depth,
        elapsed_seconds=perf_counter() - start,
        exact_steps_verified=exact_ok,
        order_trace=order_trace,
    )
