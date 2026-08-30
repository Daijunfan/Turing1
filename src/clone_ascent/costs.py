from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .relations import Relation, RelationWork


@dataclass(frozen=True, slots=True)
class CostVector:
    scope_width: int = 0
    max_tuple_count: int = 0
    total_tuple_count: int = 0
    max_log_tuple_count: float = 0.0
    max_bitset_bytes: int = 0
    total_bitset_bytes: int = 0
    birth_count: int = 0
    generation_depth: int = 0
    discovery_work: int = 0
    endpoint_solver_cost: int = 0

    @classmethod
    def initial(cls, relations: Iterable[Relation]) -> "CostVector":
        items = tuple(relations)
        return cls(
            max_tuple_count=max((relation.tuple_count for relation in items), default=0),
            total_tuple_count=sum(relation.tuple_count for relation in items),
            max_log_tuple_count=max((relation.log_tuple_cost for relation in items), default=0.0),
            max_bitset_bytes=max((relation.bitset_bytes for relation in items), default=0),
            total_bitset_bytes=sum(relation.bitset_bytes for relation in items),
        )

    def born(self, relation: Relation, depth: int, work: RelationWork, discovery: int = 0) -> "CostVector":
        return CostVector(
            scope_width=max(self.scope_width, relation.arity),
            max_tuple_count=max(self.max_tuple_count, relation.tuple_count),
            total_tuple_count=self.total_tuple_count + relation.tuple_count,
            max_log_tuple_count=max(self.max_log_tuple_count, relation.log_tuple_cost),
            max_bitset_bytes=max(self.max_bitset_bytes, relation.bitset_bytes),
            total_bitset_bytes=self.total_bitset_bytes + relation.bitset_bytes,
            birth_count=self.birth_count + 1,
            generation_depth=max(self.generation_depth, depth),
            discovery_work=self.discovery_work + work.operations + discovery,
            endpoint_solver_cost=self.endpoint_solver_cost,
        )

    def with_endpoint_cost(self, value: int) -> "CostVector":
        return CostVector(*self.as_tuple()[:-1], value)

    def as_tuple(self) -> tuple[int | float, ...]:
        return (
            self.scope_width,
            self.max_tuple_count,
            self.total_tuple_count,
            self.max_log_tuple_count,
            self.max_bitset_bytes,
            self.total_bitset_bytes,
            self.birth_count,
            self.generation_depth,
            self.discovery_work,
            self.endpoint_solver_cost,
        )

    def dominates(self, other: "CostVector") -> bool:
        left, right = self.as_tuple(), other.as_tuple()
        return all(a <= b for a, b in zip(left, right)) and any(a < b for a, b in zip(left, right))

    def to_dict(self) -> dict[str, int | float]:
        names = (
            "scope_width", "max_tuple_count", "total_tuple_count", "max_log_tuple_count",
            "max_bitset_bytes", "total_bitset_bytes", "birth_count", "generation_depth",
            "discovery_work", "endpoint_solver_cost",
        )
        return dict(zip(names, self.as_tuple()))


def pareto_min(costs: Iterable[CostVector]) -> tuple[CostVector, ...]:
    frontier: list[CostVector] = []
    for cost in costs:
        if any(existing == cost or existing.dominates(cost) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not cost.dominates(existing)]
        frontier.append(cost)
    return tuple(sorted(frontier, key=CostVector.as_tuple))

