from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .costs import CostVector
from .polymorphisms import (
    common_signature,
    gained_operations,
    gained_witnesses,
    preservation_signature_leq3,
    signature_hex,
    signature_names,
)
from .relations import Relation, RelationWork, clause_relation, contract_relations


class MonotonicityError(AssertionError):
    def __init__(self, before: int, after: int, step: dict[str, object]) -> None:
        super().__init__(f"low-arity signature decreased: {signature_hex(before)} -> {signature_hex(after)}")
        self.before = before
        self.after = after
        self.step = step


@dataclass(frozen=True, slots=True)
class RelationNode:
    relation_id: int
    relation: Relation
    parents: tuple[int, ...]
    eliminated: tuple[int, ...]
    depth: int
    originals: frozenset[int]

    def to_dict(self) -> dict[str, object]:
        return {
            "relation_id": self.relation_id,
            "relation": self.relation.to_dict(),
            "parents": list(self.parents),
            "eliminated": list(self.eliminated),
            "depth": self.depth,
            "originals": sorted(self.originals),
        }


@dataclass(frozen=True, slots=True)
class ContractionStep:
    model: str
    new_relation_id: int
    parent_ids: tuple[int, ...]
    eliminated: tuple[int, ...]
    joined_scope: tuple[int, ...]
    child: Relation
    depth: int
    signature_before: int
    signature_after: int
    gained_operations: tuple[tuple[int, int], ...]
    gained_witnesses: tuple[str, ...]
    work: RelationWork

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "new_relation_id": self.new_relation_id,
            "parent_ids": list(self.parent_ids),
            "eliminated": list(self.eliminated),
            "joined_scope": list(self.joined_scope),
            "child": self.child.to_dict(),
            "depth": self.depth,
            "signature_before": signature_hex(self.signature_before),
            "signature_after": signature_hex(self.signature_after),
            "gained_operations": [list(item) for item in self.gained_operations],
            "gained_witnesses": list(self.gained_witnesses),
            "work": {
                "join_pairs": self.work.join_pairs,
                "compatibility_checks": self.work.compatibility_checks,
                "projected_tuples": self.work.projected_tuples,
                "operations": self.work.operations,
            },
        }


@dataclass(frozen=True, slots=True)
class AscentState:
    active: tuple[RelationNode, ...]
    history: tuple[RelationNode, ...]
    steps: tuple[ContractionStep, ...]
    signature: int
    cost: CostVector

    @property
    def relations(self) -> tuple[Relation, ...]:
        return tuple(node.relation for node in self.active)

    @property
    def witnesses(self) -> tuple[str, ...]:
        return signature_names(self.signature)

    @property
    def max_scope(self) -> int:
        return max((node.relation.arity for node in self.active), default=0)

    @property
    def table_size(self) -> int:
        return sum(node.relation.tuple_count for node in self.active)

    @property
    def max_depth(self) -> int:
        return max((node.depth for node in self.active), default=0)

    def to_snapshot(self, step: int | None = None) -> dict[str, object]:
        return {
            "step": len(self.steps) if step is None else step,
            "signature": signature_hex(self.signature),
            "witnesses": list(self.witnesses),
            "relation_count": len(self.active),
            "max_scope": self.max_scope,
            "table_size": self.table_size,
            "generation_depth": self.max_depth,
            "cost": self.cost.to_dict(),
        }


def initial_state(relations: Iterable[Relation]) -> AscentState:
    nodes = tuple(
        RelationNode(index, relation, tuple(), tuple(), 0, frozenset({index}))
        for index, relation in enumerate(relations)
    )
    signature = common_signature(node.relation for node in nodes)
    return AscentState(nodes, nodes, tuple(), signature, CostVector.initial(node.relation for node in nodes))


def clause_level_state(clauses: Iterable[tuple[int, ...]]) -> AscentState:
    return initial_state(clause_relation(tuple(clause)) for clause in clauses)


def grouped_scope_state(clauses: Iterable[tuple[int, ...]]) -> AscentState:
    grouped: dict[tuple[int, ...], list[tuple[int, ...]]] = {}
    for clause in clauses:
        relation = clause_relation(tuple(clause))
        grouped.setdefault(relation.scope, []).append(tuple(clause))
    relations: list[Relation] = []
    for scope, items in sorted(grouped.items()):
        mask = (1 << (1 << len(scope))) - 1
        for clause in items:
            mask &= clause_relation(clause).mask
        relations.append(Relation(scope, mask))
    return initial_state(relations)


def apply_contraction(
    state: AscentState,
    parent_ids: Iterable[int],
    eliminate: Iterable[int],
    model: str,
    discovery_work: int = 0,
) -> AscentState:
    ids = tuple(sorted(set(parent_ids)))
    by_id = {node.relation_id: node for node in state.active}
    if not ids or any(relation_id not in by_id for relation_id in ids):
        raise ValueError("contraction parents must be active")
    parents = tuple(by_id[relation_id] for relation_id in ids)
    eliminated = tuple(sorted(set(eliminate)))
    parent_variables = set().union(*(set(parent.relation.scope) for parent in parents))
    outside_variables = set().union(*(
        set(node.relation.scope) for node in state.active if node.relation_id not in ids
    )) if len(state.active) > len(ids) else set()
    if not set(eliminated) <= parent_variables:
        raise ValueError("eliminated variable is absent from the selected parents")
    if set(eliminated) & outside_variables:
        raise ValueError("unsafe projection: an eliminated variable occurs outside the selected parents")
    child, work = contract_relations((parent.relation for parent in parents), eliminated)
    next_id = max((node.relation_id for node in state.history), default=-1) + 1
    depth = max(parent.depth for parent in parents) + 1
    child_node = RelationNode(
        next_id,
        child,
        ids,
        eliminated,
        depth,
        frozenset().union(*(parent.originals for parent in parents)),
    )
    active = tuple(sorted(
        (node for node in state.active if node.relation_id not in ids),
        key=lambda node: node.relation_id,
    )) + (child_node,)
    after = common_signature(node.relation for node in active)
    step = ContractionStep(
        model,
        next_id,
        ids,
        eliminated,
        tuple(sorted(parent_variables)),
        child,
        depth,
        state.signature,
        after,
        gained_operations(state.signature, after),
        gained_witnesses(state.signature, after),
        work,
    )
    if state.signature & ~after:
        raise MonotonicityError(state.signature, after, step.to_dict())
    return AscentState(
        active,
        state.history + (child_node,),
        state.steps + (step,),
        after,
        state.cost.born(child, depth, work, discovery_work),
    )


def lca_successors(
    state: AscentState,
    recursive_births: bool = True,
    minimum_parents: int = 1,
) -> tuple[AscentState, ...]:
    incidence: dict[int, list[RelationNode]] = {}
    for node in state.active:
        for variable in node.relation.scope:
            incidence.setdefault(variable, []).append(node)
    successors = []
    for variable in sorted(incidence):
        parents = incidence[variable]
        if len(parents) < minimum_parents:
            continue
        if not recursive_births and any(parent.depth > 0 for parent in parents):
            continue
        successors.append(
            apply_contraction(
                state,
                (parent.relation_id for parent in parents),
                (variable,),
                "LCA",
                discovery_work=len(incidence),
            )
        )
    return tuple(successors)


def bca_successors(state: AscentState, recursive_births: bool = True) -> tuple[AscentState, ...]:
    active = state.active
    successors = []
    candidate_count = len(active) * (len(active) - 1) // 2
    for left_index in range(len(active)):
        for right_index in range(left_index + 1, len(active)):
            parents = (active[left_index], active[right_index])
            if not recursive_births and any(parent.depth > 0 for parent in parents):
                continue
            outside = set().union(*(
                set(node.relation.scope)
                for index, node in enumerate(active)
                if index not in {left_index, right_index}
            )) if len(active) > 2 else set()
            union = set(parents[0].relation.scope) | set(parents[1].relation.scope)
            eliminate = tuple(sorted(union - outside))
            successors.append(
                apply_contraction(
                    state,
                    (parents[0].relation_id, parents[1].relation_id),
                    eliminate,
                    "BCA",
                    discovery_work=candidate_count,
                )
            )
    return tuple(successors)

