from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import log

from src.clone_ascent.relations import Relation, contract_relations


@dataclass(frozen=True, slots=True)
class JoinwidthResult:
    value: float
    status: str
    linear: bool
    maximum_input_tuples: int
    maximum_intermediate_tuples: int
    decomposition: object
    node_relations: dict[int, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "status": self.status,
            "linear": self.linear,
            "maximum_input_tuples": self.maximum_input_tuples,
            "maximum_intermediate_tuples": self.maximum_intermediate_tuples,
            "decomposition": self.decomposition,
            "node_relations": self.node_relations,
        }


def _separator(relations: tuple[Relation, ...], subset: int) -> tuple[int, ...]:
    inside = set().union(*(
        set(relation.scope) for index, relation in enumerate(relations) if subset & (1 << index)
    ))
    outside = set().union(*(
        set(relation.scope) for index, relation in enumerate(relations) if not subset & (1 << index)
    )) if subset != (1 << len(relations)) - 1 else set()
    return tuple(sorted(inside & outside))


def _prune(relation: Relation, originals: tuple[Relation, ...]) -> Relation:
    allowed = []
    relation_position = {variable: index for index, variable in enumerate(relation.scope)}
    projections = []
    for original in originals:
        shared = tuple(sorted(set(relation.scope) & set(original.scope)))
        projected, _ = original.project(shared)
        projections.append(projected)
    for bits in relation.allowed:
        keep = True
        for projection in projections:
            local = 0
            for index, variable in enumerate(projection.scope):
                local |= ((bits >> relation_position[variable]) & 1) << index
            if not projection.holds_bits(local):
                keep = False
                break
        if keep:
            allowed.append(bits)
    return Relation.from_allowed(relation.scope, allowed)


def exact_joinwidth(relations: tuple[Relation, ...], linear: bool = False) -> JoinwidthResult:
    """Exact Definition-3 joinwidth with join, separator projection and pruning.

    This exponential implementation is intended only for small instances.
    """
    if not relations:
        return JoinwidthResult(0.0, "EXACT", linear, 1, 1, None, {})
    count = len(relations)
    full = (1 << count) - 1
    maximum_input = max((relation.tuple_count for relation in relations), default=1)
    base = max(2, maximum_input)

    @lru_cache(maxsize=None)
    def constraint(subset: int) -> Relation:
        selected = tuple(relations[index] for index in range(count) if subset & (1 << index))
        joined, _ = contract_relations(selected, tuple())
        projected, _ = joined.project(_separator(relations, subset))
        return _prune(projected, relations)

    def node_width(subset: int) -> float:
        tuples = constraint(subset).tuple_count
        return log(max(1, tuples), base)

    @lru_cache(maxsize=None)
    def general(subset: int) -> tuple[float, object]:
        if subset & (subset - 1) == 0:
            leaf = subset.bit_length() - 1
            return node_width(subset), leaf
        first_bit = subset & -subset
        best = float("inf")
        best_tree = None
        proper = (subset - 1) & subset
        while proper:
            left = proper
            right = subset ^ left
            if right and left & first_bit:
                left_width, left_tree = general(left)
                right_width, right_tree = general(right)
                width = max(node_width(subset), left_width, right_width)
                if width < best:
                    best, best_tree = width, (left_tree, right_tree)
            proper = (proper - 1) & subset
        assert best_tree is not None
        return best, best_tree

    @lru_cache(maxsize=None)
    def linear_dp(subset: int) -> tuple[float, object]:
        if subset & (subset - 1) == 0:
            leaf = subset.bit_length() - 1
            return node_width(subset), leaf
        best = float("inf")
        best_tree = None
        leaves = subset
        while leaves:
            leaf_bit = leaves & -leaves
            leaves ^= leaf_bit
            rest = subset ^ leaf_bit
            rest_width, rest_tree = linear_dp(rest)
            width = max(node_width(subset), node_width(leaf_bit), rest_width)
            if width < best:
                best = width
                best_tree = (rest_tree, leaf_bit.bit_length() - 1)
        assert best_tree is not None
        return best, best_tree

    value, tree = linear_dp(full) if linear else general(full)
    node_relations = {
        subset: {
            "separator": list(constraint(subset).scope),
            "tuple_count": constraint(subset).tuple_count,
            "width": node_width(subset),
        }
        for subset in range(1, full + 1)
    }
    maximum_intermediate = max(item["tuple_count"] for item in node_relations.values())
    return JoinwidthResult(
        value,
        "EXACT",
        linear,
        maximum_input,
        int(maximum_intermediate),
        tree,
        node_relations,
    )

