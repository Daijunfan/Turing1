from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Iterable

from .fusion import MacroRelation, _project_join, fuse_until_tractable
from .relations import RelationBlock
from .schaefer import classify_block


TRACTABLE = frozenset(
    {"affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid"}
)
RelationKey = tuple[tuple[int, ...], tuple[int, ...], int]
SemanticKey = tuple[tuple[int, ...], tuple[int, ...]]


@dataclass(slots=True)
class ExactWidthResult:
    min_width: int | None
    min_births: int | None
    min_max_depth: int | None
    target_class: str | None
    witness: list[dict[str, object]]
    infeasible_widths: list[int]
    states_explored: int
    exhaustive: bool
    initial_state_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalize(relations: Iterable[RelationKey]) -> tuple[RelationKey, ...]:
    # Identical conjuncts are redundant. Retaining the shallowest copy is also
    # optimal for the secondary maximum-depth objective.
    unique: dict[SemanticKey, int] = {}
    for scope, allowed, depth in relations:
        key = (tuple(scope), tuple(allowed))
        unique[key] = min(depth, unique.get(key, depth))
    return tuple(sorted((scope, allowed, depth) for (scope, allowed), depth in unique.items()))


def _semantic_state(state: tuple[RelationKey, ...]) -> tuple[SemanticKey, ...]:
    return tuple((scope, allowed) for scope, allowed, _ in state)


def _state_digest(state: tuple[RelationKey, ...]) -> str:
    payload = json.dumps(_semantic_state(state), separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _classes(scope: tuple[int, ...], allowed: tuple[int, ...]) -> frozenset[str]:
    block = RelationBlock(0, scope, tuple(), tuple(), allowed)
    classify_block(block)
    return block.classes & TRACTABLE


def _common_class(state: tuple[RelationKey, ...]) -> str | None:
    if not state:
        return "affine"
    common: set[str] | None = None
    for scope, allowed, _ in state:
        classes = set(_classes(scope, allowed))
        common = classes if common is None else common & classes
        if not common:
            return None
    for candidate in ("affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid"):
        if candidate in (common or set()):
            return candidate
    return None


def _macro(index: int, relation: RelationKey) -> MacroRelation:
    scope, allowed, depth = relation
    return MacroRelation(index, scope, allowed, tuple(), None, depth, frozenset())


def _successors(state: tuple[RelationKey, ...], width: int):
    incidence: dict[int, list[int]] = {}
    for index, (scope, _, _) in enumerate(state):
        for variable in scope:
            incidence.setdefault(variable, []).append(index)
    for variable in sorted(incidence):
        indices = incidence[variable]
        if len(indices) < 2:
            continue
        parents = [_macro(index, state[index]) for index in indices]
        scope, allowed = _project_join(parents, variable)
        if len(scope) > width:
            continue
        depth = max(parent.depth for parent in parents) + 1
        remaining = [rel for index, rel in enumerate(state) if index not in set(indices)]
        if not allowed or len(allowed) != 1 << len(scope):
            remaining.append((scope, allowed, depth))
        new_state = _normalize(remaining)
        step = {
            "eliminated_variable": variable,
            "parent_relations": [
                {"scope": list(parent.scope), "allowed": list(parent.allowed), "depth": parent.depth}
                for parent in parents
            ],
            "new_relation": {"scope": list(scope), "allowed": list(allowed), "depth": depth},
            "resulting_state_sha256": _state_digest(new_state),
        }
        yield new_state, step, depth


def _fixed_width(
    initial: tuple[RelationKey, ...], width: int, state_limit: int | None
) -> tuple[dict[str, object] | None, int]:
    """Exhaustive breadth-first branch-and-bound for one width."""
    initial_class = _common_class(initial)
    if initial_class:
        return {"class": initial_class, "steps": [], "max_depth": 0}, 1
    queue = deque([(initial, [], 0)])
    visited = {initial}
    explored = 0
    best: dict[str, object] | None = None
    best_births: int | None = None
    while queue:
        state, path, max_depth = queue.popleft()
        explored += 1
        if state_limit is not None and explored > state_limit:
            raise RuntimeError(f"exact state limit {state_limit} exceeded at width {width}")
        if best_births is not None and len(path) >= best_births:
            continue
        for successor, step, depth in _successors(state, width):
            new_path = path + [step]
            new_max_depth = max(max_depth, depth)
            target = _common_class(successor)
            if target:
                candidate = {"class": target, "steps": new_path, "max_depth": new_max_depth}
                if (
                    best is None
                    or len(new_path) < len(best["steps"])  # type: ignore[arg-type]
                    or (
                        len(new_path) == len(best["steps"])  # type: ignore[arg-type]
                        and new_max_depth < int(best["max_depth"])
                    )
                ):
                    best = candidate
                    best_births = len(new_path)
                continue
            if successor not in visited:
                visited.add(successor)
                queue.append((successor, new_path, new_max_depth))
    return best, explored


def exact_morph_width(
    blocks: list[RelationBlock],
    max_width: int | None = None,
    state_limit: int | None = None,
) -> ExactWidthResult:
    """Return the exact minimum birth arity under the v0.1 fusion semantics.

    A legal step selects a variable occurring in at least two active relations,
    joins *all* incident relations, and projects that variable. Width is the
    maximum arity of a born relation; initial input arity is reported separately
    by callers and is not charged, matching ``max_macro_arity`` in v0.1.
    """
    initial = _normalize((block.scope, block.allowed, 0) for block in blocks)
    union = {variable for scope, _, _ in initial for variable in scope}
    ceiling = max_width if max_width is not None else max(0, len(union) - 1)
    infeasible: list[int] = []
    explored_total = 0
    for width in range(ceiling + 1):
        result, explored = _fixed_width(initial, width, state_limit)
        explored_total += explored
        if result is not None:
            steps = list(result["steps"])  # type: ignore[arg-type]
            return ExactWidthResult(
                width,
                len(steps),
                int(result["max_depth"]),
                str(result["class"]),
                steps,
                infeasible,
                explored_total,
                True,
                _state_digest(initial),
            )
        infeasible.append(width)
    return ExactWidthResult(
        None, None, None, None, [], infeasible, explored_total, True, _state_digest(initial)
    )


def brute_force_morph_width(blocks: list[RelationBlock], max_width: int) -> int | None:
    """Independent no-memo trajectory enumeration for tiny cross-checks."""
    initial = _normalize((block.scope, block.allowed, 0) for block in blocks)

    def reachable(state: tuple[RelationKey, ...], width: int, ancestors: set[tuple[RelationKey, ...]]) -> bool:
        if _common_class(state):
            return True
        for successor, _, _ in _successors(state, width):
            if successor not in ancestors and reachable(successor, width, ancestors | {successor}):
                return True
        return False

    for width in range(max_width + 1):
        if reachable(initial, width, {initial}):
            return width
    return None


def heuristic_morph_width(blocks: list[RelationBlock]) -> dict[str, object]:
    variables = {variable for block in blocks for variable in block.scope}
    result = fuse_until_tractable(blocks, max_macro_arity=max(0, len(variables) - 1))
    success = bool(result.common_classes or not result.relations or any(not rel.allowed for rel in result.relations))
    return {
        "success": success,
        "width": max((len(step.new_scope) for step in result.steps), default=0) if success else None,
        "births": len(result.steps),
        "max_depth": result.max_depth,
        "variables": [step.eliminated_variable for step in result.steps],
    }
