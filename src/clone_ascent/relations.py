from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
from typing import Iterable, Mapping


@dataclass(frozen=True, order=True, slots=True)
class Relation:
    scope: tuple[int, ...]
    mask: int

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.scope))) != self.scope:
            raise ValueError(f"scope must be sorted and duplicate-free: {self.scope}")
        limit = 1 << (1 << len(self.scope))
        if self.mask < 0 or self.mask >= limit:
            raise ValueError("relation bitmask exceeds its truth-table size")

    @property
    def arity(self) -> int:
        return len(self.scope)

    @property
    def tuple_count(self) -> int:
        return self.mask.bit_count()

    @property
    def log_tuple_cost(self) -> float:
        return log2(self.tuple_count + 1)

    @property
    def bitset_bytes(self) -> int:
        return max(1, ceil((1 << self.arity) / 8))

    @property
    def allowed(self) -> tuple[int, ...]:
        return tuple(index for index in range(1 << self.arity) if (self.mask >> index) & 1)

    @classmethod
    def from_allowed(cls, scope: Iterable[int], allowed: Iterable[int]) -> "Relation":
        ordered = tuple(scope)
        mask = 0
        for item in allowed:
            mask |= 1 << int(item)
        return cls(ordered, mask)

    def holds_bits(self, bits: int) -> bool:
        return bool((self.mask >> bits) & 1)

    def holds_assignment(self, assignment: Mapping[int, int]) -> bool:
        bits = sum((int(assignment[var]) & 1) << index for index, var in enumerate(self.scope))
        return self.holds_bits(bits)

    def project(self, keep: Iterable[int]) -> tuple["Relation", int]:
        keep_scope = tuple(sorted(set(keep) & set(self.scope)))
        old_position = {variable: index for index, variable in enumerate(self.scope)}
        mask = 0
        inspected = 0
        for bits in self.allowed:
            inspected += 1
            projected = 0
            for index, variable in enumerate(keep_scope):
                projected |= ((bits >> old_position[variable]) & 1) << index
            mask |= 1 << projected
        return Relation(keep_scope, mask), inspected

    def rename(self, mapping: Mapping[int, int]) -> "Relation":
        renamed_scope = tuple(sorted(mapping.get(variable, variable) for variable in self.scope))
        old_position = {mapping.get(variable, variable): index for index, variable in enumerate(self.scope)}
        mask = 0
        for bits in self.allowed:
            renamed_bits = 0
            for index, variable in enumerate(renamed_scope):
                renamed_bits |= ((bits >> old_position[variable]) & 1) << index
            mask |= 1 << renamed_bits
        return Relation(renamed_scope, mask)

    def to_dict(self) -> dict[str, object]:
        return {"scope": list(self.scope), "mask": self.mask, "allowed": list(self.allowed)}


@dataclass(frozen=True, slots=True)
class RelationWork:
    join_pairs: int = 0
    compatibility_checks: int = 0
    projected_tuples: int = 0

    @property
    def operations(self) -> int:
        return self.join_pairs + self.compatibility_checks + self.projected_tuples

    def __add__(self, other: "RelationWork") -> "RelationWork":
        return RelationWork(
            self.join_pairs + other.join_pairs,
            self.compatibility_checks + other.compatibility_checks,
            self.projected_tuples + other.projected_tuples,
        )


def clause_relation(clause: tuple[int, ...]) -> Relation:
    scope = tuple(sorted({abs(literal) for literal in clause}))
    positions = {variable: index for index, variable in enumerate(scope)}
    allowed = []
    for bits in range(1 << len(scope)):
        if any(bool((bits >> positions[abs(literal)]) & 1) == (literal > 0) for literal in clause):
            allowed.append(bits)
    return Relation.from_allowed(scope, allowed)


def natural_join(left: Relation, right: Relation) -> tuple[Relation, RelationWork]:
    union = tuple(sorted(set(left.scope) | set(right.scope)))
    union_position = {variable: index for index, variable in enumerate(union)}
    left_position = {variable: index for index, variable in enumerate(left.scope)}
    right_position = {variable: index for index, variable in enumerate(right.scope)}
    shared = tuple(sorted(set(left.scope) & set(right.scope)))
    mask = 0
    pairs = checks = 0
    for left_bits in left.allowed:
        for right_bits in right.allowed:
            pairs += 1
            compatible = True
            for variable in shared:
                checks += 1
                if ((left_bits >> left_position[variable]) & 1) != ((right_bits >> right_position[variable]) & 1):
                    compatible = False
                    break
            if not compatible:
                continue
            bits = 0
            for variable in left.scope:
                bits |= ((left_bits >> left_position[variable]) & 1) << union_position[variable]
            for variable in right.scope:
                bits |= ((right_bits >> right_position[variable]) & 1) << union_position[variable]
            mask |= 1 << bits
    return Relation(union, mask), RelationWork(pairs, checks, 0)


def contract_relations(relations: Iterable[Relation], eliminate: Iterable[int]) -> tuple[Relation, RelationWork]:
    parents = tuple(sorted(relations))
    if not parents:
        raise ValueError("a contraction needs at least one parent")
    joined = parents[0]
    work = RelationWork()
    for parent in parents[1:]:
        joined, item = natural_join(joined, parent)
        work += item
    keep = set(joined.scope) - set(eliminate)
    projected, inspected = joined.project(keep)
    return projected, work + RelationWork(projected_tuples=inspected)


def relation_set_satisfied(relations: Iterable[Relation], assignment: Mapping[int, int]) -> bool:
    return all(relation.holds_assignment(assignment) for relation in relations)

