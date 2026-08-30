from __future__ import annotations

from dataclasses import dataclass
from random import Random
from time import perf_counter

from .cnf import CNF
from .fusion import MacroRelation, _classify_macro, _project_join, common_tractable_classes
from .relations import RelationBlock, enumerate_relation


@dataclass(slots=True)
class AblationResult:
    success: bool
    common_classes: frozenset[str]
    births: int
    max_birth_arity: int
    max_depth: int
    total_relation_table_size: int
    remaining_relations: int
    preprocessing_seconds: float
    trajectory: list[int]


def discover_clause_relations(cnf: CNF) -> list[RelationBlock]:
    blocks: list[RelationBlock] = []
    for index, clause in enumerate(cnf.clauses):
        scope = tuple(sorted({abs(literal) for literal in clause}))
        blocks.append(
            RelationBlock(index, scope, (index,), (clause,), enumerate_relation(scope, (clause,)))
        )
    return blocks


def discover_scope_blocks_in_input_order(cnf: CNF) -> list[RelationBlock]:
    grouped: dict[tuple[int, ...], list[tuple[int, tuple[int, ...]]]] = {}
    for index, clause in enumerate(cnf.clauses):
        scope = tuple(sorted({abs(literal) for literal in clause}))
        grouped.setdefault(scope, []).append((index, clause))
    return [
        RelationBlock(
            block_id,
            scope,
            tuple(index for index, _ in entries),
            tuple(clause for _, clause in entries),
            enumerate_relation(scope, (clause for _, clause in entries)),
        )
        for block_id, (scope, entries) in enumerate(grouped.items())
    ]


def run_ablation_fusion(
    blocks: list[RelationBlock],
    max_macro_arity: int,
    order: str = "min_scope",
    seed: int = 0,
    recursive_births: bool = True,
    stop_at_tractable: bool = True,
    forced_trajectory: list[int] | None = None,
    allow_single_parent: bool = False,
) -> AblationResult:
    start = perf_counter()
    rng = Random(seed)
    relations: dict[int, MacroRelation] = {}
    next_id = 0
    for block in blocks:
        relation = MacroRelation(
            next_id, block.scope, block.allowed, tuple(), None, 0, frozenset({block.block_id})
        )
        _classify_macro(relation)
        relations[next_id] = relation
        next_id += 1
    common = common_tractable_classes(list(relations.values()))
    births = max_arity = max_depth = 0
    table_size = sum(len(relation.allowed) for relation in relations.values())
    trajectory: list[int] = []

    while relations and not (stop_at_tractable and common):
        incidence: dict[int, list[int]] = {}
        for relation_id, relation in relations.items():
            if not recursive_births and relation.depth:
                continue
            for variable in relation.scope:
                incidence.setdefault(variable, []).append(relation_id)
        candidates: list[tuple[int, int, int, tuple[int, ...]]] = []
        for variable, parent_ids in incidence.items():
            if len(parent_ids) < (1 if allow_single_parent else 2):
                continue
            union = {item for relation_id in parent_ids for item in relations[relation_id].scope}
            width = len(union) - 1
            if width <= max_macro_arity:
                candidates.append(
                    (width, sum(relations[relation_id].arity for relation_id in parent_ids), variable,
                     tuple(sorted(parent_ids)))
                )
        if not candidates:
            break
        if forced_trajectory is not None:
            index = len(trajectory)
            if index >= len(forced_trajectory):
                break
            desired = forced_trajectory[index]
            selected = next((candidate for candidate in candidates if candidate[2] == desired), None)
            if selected is None:
                break
        elif order == "random":
            selected = rng.choice(candidates)
        elif order == "shuffled_score":
            selected = min(candidates, key=lambda candidate: rng.random())
        elif order == "input_variable":
            selected = min(candidates, key=lambda candidate: candidate[2])
        elif order == "input_relation":
            selected = min(candidates, key=lambda candidate: (min(candidate[3]), candidate[2]))
        elif order == "min_scope":
            selected = min(candidates)
        else:
            raise ValueError(order)
        _, _, variable, parent_ids = selected
        parents = [relations[relation_id] for relation_id in parent_ids]
        scope, allowed = _project_join(parents, variable)
        depth = max(parent.depth for parent in parents) + 1
        born = MacroRelation(
            next_id,
            scope,
            allowed,
            parent_ids,
            variable,
            depth,
            frozenset().union(*(parent.original_blocks for parent in parents)),
        )
        _classify_macro(born)
        for relation_id in parent_ids:
            del relations[relation_id]
        if not allowed or len(allowed) != 1 << len(scope):
            relations[next_id] = born
        next_id += 1
        births += 1
        max_arity = max(max_arity, len(scope))
        max_depth = max(max_depth, depth)
        table_size += len(allowed)
        trajectory.append(variable)
        common = common_tractable_classes(list(relations.values())) if relations else frozenset(TRACTABLE_CLASSES)
    success = bool(common or not relations or any(not relation.allowed for relation in relations.values()))
    return AblationResult(
        success,
        common,
        births,
        max_arity,
        max_depth,
        table_size,
        len(relations),
        perf_counter() - start,
        trajectory,
    )


TRACTABLE_CLASSES = (
    "affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid"
)
