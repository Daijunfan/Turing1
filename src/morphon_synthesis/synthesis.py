from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import combinations, permutations, product
from random import Random
from typing import Iterable

from src.clone_ascent.models import AscentState, bca_successors, clause_level_state, lca_successors


TARGETS = {
    "affine": ("minority",),
    "bijunctive": ("majority",),
    # Coordinate complementation can dualize Horn. Robustness therefore accepts
    # either orientation but records the endpoint actually obtained.
    "horn": ("and", "or"),
}


@dataclass(frozen=True, slots=True)
class MorphonCheck:
    valid: bool
    target_class: str
    model: str
    reason: str
    witness_state: AscentState | None
    polarity_cases: int
    rename_cases: int
    order_cases: int
    standard_gate_signatures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        state = self.witness_state
        return {
            "valid": self.valid,
            "target_class": self.target_class,
            "model": self.model,
            "reason": self.reason,
            "polarity_cases": self.polarity_cases,
            "rename_cases": self.rename_cases,
            "order_cases": self.order_cases,
            "standard_gate_signatures": list(self.standard_gate_signatures),
            "births": len(state.steps) if state else None,
            "generation_depth": state.max_depth if state else None,
            "endpoint_witnesses": list(state.witnesses) if state else [],
        }


def clause_universe(nvars: int, max_width: int = 3) -> tuple[tuple[int, ...], ...]:
    clauses = []
    for width in range(1, min(max_width, nvars) + 1):
        for variables in combinations(range(1, nvars + 1), width):
            for signs in product((1, -1), repeat=width):
                clauses.append(tuple(variable * sign for variable, sign in zip(variables, signs)))
    return tuple(clauses)


def complement_formula(formula: tuple[tuple[int, ...], ...], flip_mask: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(-literal if flip_mask & (1 << (abs(literal) - 1)) else literal for literal in clause)
        for clause in formula
    )


def rename_formula(formula: tuple[tuple[int, ...], ...], image: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(image[abs(literal) - 1] if literal > 0 else -image[abs(literal) - 1] for literal in clause)
        for clause in formula
    )


def _successors(state: AscentState, model: str) -> tuple[AscentState, ...]:
    return lca_successors(state) if model == "LCA" else bca_successors(state)


def find_trajectory(
    formula: tuple[tuple[int, ...], ...],
    target_class: str,
    model: str = "LCA",
    max_births: int = 4,
) -> AscentState | None:
    targets = TARGETS[target_class]
    initial = clause_level_state(formula)
    if initial.witnesses:
        return None
    first = _successors(initial, model)
    if any(any(target in state.witnesses for target in targets) for state in first):
        return None
    queue = deque(first)
    while queue:
        state = queue.popleft()
        recursive_parent = any(
            state.steps[index - 1].new_relation_id in state.steps[index].parent_ids
            for index in range(1, len(state.steps))
        )
        if (
            len(state.steps) >= 2
            and state.max_depth >= 2
            and recursive_parent
            and any(target in state.witnesses for target in targets)
        ):
            return state
        if len(state.steps) < max_births:
            queue.extend(_successors(state, model))
    return None


def _standard_gate_signatures(formula: tuple[tuple[int, ...], ...]) -> tuple[str, ...]:
    clause_set = {tuple(sorted(clause, key=lambda literal: (abs(literal), literal < 0))) for clause in formula}
    variables = sorted({abs(literal) for clause in formula for literal in clause})
    found = set()
    for a, b, z in permutations(variables, 3):
        for flip in range(8):
            def lit(variable: int, positive: bool) -> int:
                index = (a, b, z).index(variable)
                return variable if positive ^ bool(flip & (1 << index)) else -variable

            patterns = {
                "and": ((lit(a, False), lit(b, False), lit(z, True)), (lit(a, True), lit(z, False)), (lit(b, True), lit(z, False))),
                "or": ((lit(a, True), lit(b, True), lit(z, False)), (lit(a, False), lit(z, True)), (lit(b, False), lit(z, True))),
            }
            for name, pattern in patterns.items():
                normalized = {tuple(sorted(clause, key=lambda item: (abs(item), item < 0))) for clause in pattern}
                if normalized <= clause_set:
                    found.add(name)
        parity = {
            tuple(sorted(clause, key=lambda item: (abs(item), item < 0)))
            for clause in ((a, b, -z), (a, -b, z), (-a, b, z), (-a, -b, -z))
        }
        if parity <= clause_set:
            found.add("xor")
    return tuple(sorted(found))


def check_morphon(
    formula: Iterable[tuple[int, ...]],
    target_class: str,
    model: str = "LCA",
    max_births: int = 4,
    robustness: bool = True,
) -> MorphonCheck:
    normalized = tuple(sorted(tuple(clause) for clause in formula))
    variables = sorted({abs(literal) for clause in normalized for literal in clause})
    if not variables:
        return MorphonCheck(False, target_class, model, "empty formula", None, 0, 0, 0, tuple())
    base = find_trajectory(normalized, target_class, model, max_births)
    gates = _standard_gate_signatures(normalized)
    if base is None:
        return MorphonCheck(False, target_class, model, "no qualifying multi-generation trajectory", None, 0, 0, 0, gates)
    polarity_cases = rename_cases = order_cases = 1
    if robustness:
        polarity_cases = 1 << len(variables)
        for flip in range(polarity_cases):
            if find_trajectory(complement_formula(normalized, flip), target_class, model, max_births) is None:
                return MorphonCheck(False, target_class, model, f"polarity case {flip} fails", base, flip + 1, 0, 0, gates)
        rename_cases = 1
        if len(variables) <= 6:
            for image in permutations(variables):
                rename_cases += 1
                if find_trajectory(rename_formula(normalized, image), target_class, model, max_births) is None:
                    return MorphonCheck(False, target_class, model, "variable-renaming case fails", base, polarity_cases, rename_cases, 0, gates)
            rename_cases -= 1
        order_variants = (normalized, tuple(reversed(normalized)))
        order_cases = len(order_variants)
        for ordered in order_variants:
            if find_trajectory(ordered, target_class, model, max_births) is None:
                return MorphonCheck(False, target_class, model, "clause-order case fails", base, polarity_cases, rename_cases, order_cases, gates)
    return MorphonCheck(True, target_class, model, "verified", base, polarity_cases, rename_cases, order_cases, gates)


def minimize_morphon(
    formula: Iterable[tuple[int, ...]],
    target_class: str,
    model: str = "LCA",
    max_births: int = 4,
) -> tuple[tuple[tuple[int, ...], ...], dict[str, object]]:
    current = list(sorted(tuple(clause) for clause in formula))

    def valid(candidate: list[tuple[int, ...]]) -> bool:
        return bool(candidate) and check_morphon(candidate, target_class, model, max_births, robustness=True).valid

    changed = True
    clause_checks = literal_checks = 0
    while changed:
        changed = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1:]
            clause_checks += 1
            if valid(candidate):
                current = candidate
                changed = True
                break
    changed = True
    while changed:
        changed = False
        for clause_index, clause in enumerate(current):
            if len(clause) <= 1:
                continue
            for literal_index in range(len(clause)):
                shortened = clause[:literal_index] + clause[literal_index + 1:]
                candidate = current[:clause_index] + [shortened] + current[clause_index + 1:]
                if len(set(candidate)) != len(candidate):
                    continue
                literal_checks += 1
                if valid(candidate):
                    current = sorted(candidate)
                    changed = True
                    break
            if changed:
                break
    # Literal shortening can make a formerly necessary clause redundant (and
    # vice versa), so alternate both reductions to a joint fixed point.
    while True:
        progressed = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1:]
            clause_checks += 1
            if valid(candidate):
                current = candidate
                progressed = True
                break
        if progressed:
            continue
        for clause_index, clause in enumerate(current):
            if len(clause) <= 1:
                continue
            for literal_index in range(len(clause)):
                shortened = clause[:literal_index] + clause[literal_index + 1:]
                candidate = current[:clause_index] + [shortened] + current[clause_index + 1:]
                if len(set(candidate)) != len(candidate):
                    continue
                literal_checks += 1
                if valid(candidate):
                    current = sorted(candidate)
                    progressed = True
                    break
            if progressed:
                break
        if not progressed:
            break
    minimal = all(not valid(current[:index] + current[index + 1:]) for index in range(len(current)))
    return tuple(current), {
        "one_clause_minimal": minimal,
        "clause_checks": clause_checks,
        "literal_checks": literal_checks,
        "variables": len({abs(literal) for clause in current for literal in clause}),
        "clauses": len(current),
        "total_literals": sum(len(clause) for clause in current),
        "max_clause_width": max(map(len, current), default=0),
    }


def random_cegis_search(
    nvars: int,
    clause_count: int,
    target_class: str,
    trials: int,
    seed: int,
    model: str = "LCA",
) -> tuple[tuple[tuple[int, ...], ...] | None, dict[str, object]]:
    rng = Random(seed)
    universe = clause_universe(nvars)
    rejected_initial = rejected_trajectory = 0
    for trial in range(trials):
        candidate = tuple(sorted(rng.sample(universe, clause_count)))
        if any(clause_level_state(complement_formula(candidate, flip)).witnesses for flip in range(1 << nvars)):
            rejected_initial += 1
            continue
        check = check_morphon(candidate, target_class, model, robustness=True)
        if check.valid:
            return candidate, {
                "method": "seeded_random_CEGIS",
                "trial": trial,
                "seed": seed,
                "rejected_initial": rejected_initial,
                "rejected_trajectory": rejected_trajectory,
            }
        rejected_trajectory += 1
    return None, {
        "method": "seeded_random_CEGIS",
        "trials": trials,
        "seed": seed,
        "rejected_initial": rejected_initial,
        "rejected_trajectory": rejected_trajectory,
    }


def complete_enumeration_search(
    nvars: int,
    maximum_clauses: int,
    target_class: str,
    model: str = "LCA",
) -> tuple[tuple[tuple[int, ...], ...] | None, dict[str, object]]:
    universe = clause_universe(nvars)
    checked = 0
    for size in range(1, min(maximum_clauses, len(universe)) + 1):
        for candidate in combinations(universe, size):
            checked += 1
            if check_morphon(candidate, target_class, model, robustness=True).valid:
                return tuple(candidate), {
                    "method": "complete_enumeration", "checked": checked,
                    "nvars": nvars, "maximum_clauses": maximum_clauses,
                }
    return None, {
        "method": "complete_enumeration", "checked": checked,
        "nvars": nvars, "maximum_clauses": maximum_clauses,
    }


def local_mutation_search(
    start: Iterable[tuple[int, ...]],
    target_class: str,
    mutations: int,
    seed: int,
    model: str = "LCA",
) -> tuple[tuple[tuple[int, ...], ...] | None, dict[str, object]]:
    rng = Random(seed)
    current = list(sorted(tuple(clause) for clause in start))
    nvars = max(abs(literal) for clause in current for literal in clause)
    universe = clause_universe(nvars)
    for iteration in range(mutations):
        candidate = list(current)
        candidate[rng.randrange(len(candidate))] = rng.choice(universe)
        candidate = sorted(set(candidate))
        if len(candidate) != len(current):
            continue
        if check_morphon(candidate, target_class, model, robustness=True).valid:
            return tuple(candidate), {
                "method": "local_mutation", "iteration": iteration, "seed": seed,
            }
    return None, {"method": "local_mutation", "mutations": mutations, "seed": seed}


def satisfiable_robust_random_search(
    nvars: int,
    trials: int,
    seed: int,
    minimum_clauses: int = 6,
    maximum_clauses: int = 11,
) -> tuple[tuple[tuple[int, ...], ...] | None, dict[str, object]]:
    rng = Random(seed)
    universe = clause_universe(nvars)

    def satisfiable(formula: tuple[tuple[int, ...], ...]) -> bool:
        return any(
            all(
                any(bool((bits >> (abs(literal) - 1)) & 1) == (literal > 0) for literal in clause)
                for clause in formula
            )
            for bits in range(1 << nvars)
        )

    satisfiable_candidates = robust_initial_candidates = 0
    for trial in range(trials):
        count = rng.randint(minimum_clauses, maximum_clauses)
        formula = tuple(sorted(rng.sample(universe, count)))
        if not satisfiable(formula):
            continue
        satisfiable_candidates += 1
        if any(clause_level_state(complement_formula(formula, flip)).witnesses for flip in range(1 << nvars)):
            continue
        robust_initial_candidates += 1
        for target in TARGETS:
            if check_morphon(formula, target, robustness=True).valid:
                return formula, {
                    "method": "satisfiable_robust_random_search", "trial": trial,
                    "seed": seed, "target": target,
                    "satisfiable_candidates": satisfiable_candidates,
                    "robust_initial_candidates": robust_initial_candidates,
                }
    return None, {
        "method": "satisfiable_robust_random_search", "trials": trials,
        "seed": seed, "satisfiable_candidates": satisfiable_candidates,
        "robust_initial_candidates": robust_initial_candidates,
    }
