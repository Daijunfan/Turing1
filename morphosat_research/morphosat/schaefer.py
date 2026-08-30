from __future__ import annotations

from dataclasses import dataclass

from .affine import affine_relation_equations, verify_affine_relation
from .relations import (
    RelationBlock,
    all_assignments_satisfying,
    entailed_horn_clauses,
    entailed_unit_binary_clauses,
)


@dataclass(slots=True)
class ClassificationSummary:
    common_classes: frozenset[str]
    counts: dict[str, int]


def classify_block(block: RelationBlock) -> RelationBlock:
    k = block.arity
    allowed = block.allowed
    classes: set[str] = set()
    reps: dict[str, object] = {}

    if not allowed:
        classes.update({"empty", "affine", "horn", "dual_horn", "bijunctive"})
        reps["affine"] = [(0, 1)]
        reps["horn"] = [tuple()]
        reps["dual_horn"] = [tuple()]
        reps["bijunctive"] = [tuple()]
    else:
        if 0 in allowed:
            classes.add("zero_valid")
        if (1 << k) - 1 in allowed:
            classes.add("one_valid")

        is_affine, equations = affine_relation_equations(allowed, k)
        if is_affine and verify_affine_relation(allowed, k, equations):
            classes.add("affine")
            reps["affine"] = equations

        two_cnf = entailed_unit_binary_clauses(allowed, k)
        if all_assignments_satisfying(k, two_cnf) == allowed:
            classes.add("bijunctive")
            reps["bijunctive"] = two_cnf

        horn = entailed_horn_clauses(allowed, k, dual=False)
        if all_assignments_satisfying(k, horn) == allowed:
            classes.add("horn")
            reps["horn"] = horn

        dual = entailed_horn_clauses(allowed, k, dual=True)
        if all_assignments_satisfying(k, dual) == allowed:
            classes.add("dual_horn")
            reps["dual_horn"] = dual

    block.classes = frozenset(classes)
    block.representations = reps
    return block


def classify_blocks(blocks: list[RelationBlock]) -> ClassificationSummary:
    common: set[str] | None = None
    counts: dict[str, int] = {}
    for block in blocks:
        classify_block(block)
        for c in block.classes:
            counts[c] = counts.get(c, 0) + 1
        tractable = set(block.classes) & {
            "affine", "bijunctive", "horn", "dual_horn", "zero_valid", "one_valid"
        }
        common = tractable if common is None else common & tractable
    return ClassificationSummary(frozenset(common or set()), counts)
