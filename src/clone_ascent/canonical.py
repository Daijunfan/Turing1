from __future__ import annotations

from functools import lru_cache
from itertools import permutations

from .models import AscentState
from .relations import Relation


SemanticState = tuple[tuple[tuple[int, ...], int, int], ...]


def semantic_state(state: AscentState) -> SemanticState:
    return tuple(sorted((node.relation.scope, node.relation.mask, node.depth) for node in state.active))


def _cheap_mapping(relations: SemanticState, variables: tuple[int, ...]) -> dict[int, int]:
    features = {}
    for variable in variables:
        occurrence = []
        for scope, mask, _ in relations:
            if variable in scope:
                occurrence.append((len(scope), mask.bit_count(), scope.index(variable)))
        features[variable] = tuple(sorted(occurrence))
    ordered = sorted(variables, key=lambda variable: (features[variable], variable))
    return {variable: index + 1 for index, variable in enumerate(ordered)}


def _rename_semantic(relations: SemanticState, mapping: dict[int, int]) -> SemanticState:
    return tuple(sorted(
        _decorated
        for scope, mask, depth in relations
        for renamed in (Relation(scope, mask).rename(mapping),)
        for _decorated in ((renamed.scope, renamed.mask, depth),)
    ))


@lru_cache(maxsize=None)
def canonical_semantic_key(relations: SemanticState, isomorphism: bool = True) -> SemanticState:
    relations = tuple(sorted(relations))
    if not isomorphism:
        return relations
    variables = tuple(sorted({variable for scope, _, _ in relations for variable in scope}))
    if len(variables) <= 1:
        return relations
    if len(variables) > 8:
        return _rename_semantic(relations, _cheap_mapping(relations, variables))
    best = None
    for image in permutations(range(1, len(variables) + 1)):
        candidate = _rename_semantic(relations, dict(zip(variables, image)))
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best


def canonical_state_key(state: AscentState, isomorphism: bool = True) -> SemanticState:
    return canonical_semantic_key(semantic_state(state), isomorphism)
