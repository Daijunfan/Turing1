from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterable

from .canonical import canonical_state_key
from .costs import CostVector
from .models import AscentState, bca_successors, lca_successors
from .polymorphisms import NAMED_WITNESSES


@dataclass(frozen=True, slots=True)
class SearchConfig:
    model: str = "LCA"
    recursive_births: bool = True
    early_stop: bool = True
    target_witnesses: tuple[str, ...] = tuple(NAMED_WITNESSES)
    max_births: int = 8
    max_scope: int | None = None
    minimum_lca_parents: int = 1
    isomorphism_dedup: bool = True
    legacy_empty_validity: bool = False


@dataclass(frozen=True, slots=True)
class TrajectoryResult:
    state: AscentState
    endpoint_witnesses: tuple[str, ...]
    cost: CostVector

    def to_dict(self) -> dict[str, object]:
        return {
            "endpoint_witnesses": list(self.endpoint_witnesses),
            "cost": self.cost.to_dict(),
            "steps": [step.to_dict() for step in self.state.steps],
            "trajectory": [self.state.to_snapshot(0)] + [
                {
                    "step": index,
                    "signature": step.to_dict()["signature_after"],
                    "new_witnesses": list(step.gained_witnesses),
                    "relation_count": len(self.state.active) if index == len(self.state.steps) else None,
                    "max_scope": step.child.arity,
                    "table_size": step.child.tuple_count,
                    "generation_depth": step.depth,
                }
                for index, step in enumerate(self.state.steps, 1)
            ],
        }


@dataclass(frozen=True, slots=True)
class SearchResult:
    config: SearchConfig
    found: bool
    minimum_births: int | None
    frontier: tuple[TrajectoryResult, ...]
    explored_states: int
    generated_states: int
    memo_pruned: int
    dominance_pruned: int
    scope_pruned: int
    infeasible_depths: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "config": asdict(self.config),
            "found": self.found,
            "minimum_births": self.minimum_births,
            "explored_states": self.explored_states,
            "generated_states": self.generated_states,
            "memo_pruned": self.memo_pruned,
            "dominance_pruned": self.dominance_pruned,
            "scope_pruned": self.scope_pruned,
            "infeasible_depths": list(self.infeasible_depths),
            "frontier": [item.to_dict() for item in self.frontier],
        }


def _target(state: AscentState, config: SearchConfig) -> tuple[str, ...]:
    names = tuple(name for name in config.target_witnesses if state.signature & NAMED_WITNESSES[name])
    if config.legacy_empty_validity and any(node.relation.tuple_count == 0 for node in state.active):
        # v0.1 did not label the empty relation 0-valid or 1-valid, despite
        # vacuous polymorphism preservation. This switch exists only to replay
        # its reported MorphWidth values exactly.
        names = tuple(name for name in names if name not in {"constant_0", "constant_1"})
    return names


def _successors(state: AscentState, config: SearchConfig) -> tuple[AscentState, ...]:
    if config.model.upper() == "LCA":
        return lca_successors(state, config.recursive_births, config.minimum_lca_parents)
    if config.model.upper() == "BCA":
        return bca_successors(state, config.recursive_births)
    raise ValueError(f"unknown clone-ascent model: {config.model}")


def _goal(state: AscentState, successors: tuple[AscentState, ...], config: SearchConfig) -> tuple[str, ...]:
    witnesses = _target(state, config)
    if not witnesses:
        return tuple()
    if config.early_stop:
        return witnesses
    if not successors or all(not node.relation.scope for node in state.active):
        return witnesses
    return tuple()


def _prefix_dominated(cost: CostVector, goals: Iterable[TrajectoryResult]) -> bool:
    prefix = cost.as_tuple()[:-1]
    for goal in goals:
        goal_prefix = goal.cost.as_tuple()[:-1]
        # Endpoint solver cost can decrease after an additional contraction.
        # Zero is its only general lower bound, so prefix pruning is sound only
        # when the dominating completed trajectory already attains zero.
        if goal.cost.endpoint_solver_cost == 0 and all(left <= right for left, right in zip(goal_prefix, prefix)):
            return True
    return False


def _pareto_trajectories(items: Iterable[TrajectoryResult]) -> tuple[TrajectoryResult, ...]:
    frontier: list[TrajectoryResult] = []
    for item in items:
        if any(existing.cost == item.cost or existing.cost.dominates(item.cost) for existing in frontier):
            continue
        frontier = [existing for existing in frontier if not item.cost.dominates(existing.cost)]
        frontier.append(item)
    return tuple(sorted(frontier, key=lambda item: item.cost.as_tuple()))


def _exists_with_depth(initial: AscentState, config: SearchConfig, depth_limit: int) -> tuple[bool, int]:
    explored = 0

    def visit(state: AscentState) -> bool:
        nonlocal explored
        explored += 1
        successors = _successors(state, config)
        if _goal(state, successors, config):
            return True
        if len(state.steps) >= depth_limit:
            return False
        return any(visit(successor) for successor in successors)

    return visit(initial), explored


def exact_clone_ascent(initial: AscentState, config: SearchConfig) -> SearchResult:
    infeasible = []
    minimum_births = None
    iterative_explored = 0
    for depth in range(config.max_births + 1):
        found, explored = _exists_with_depth(initial, config, depth)
        iterative_explored += explored
        if found:
            minimum_births = depth
            break
        infeasible.append(depth)

    goals: list[TrajectoryResult] = []
    memo: dict[object, list[CostVector]] = {}
    explored_states = generated_states = memo_pruned = dominance_pruned = scope_pruned = 0

    def visit(state: AscentState) -> None:
        nonlocal explored_states, generated_states, memo_pruned, dominance_pruned, scope_pruned
        explored_states += 1
        key = canonical_state_key(state, config.isomorphism_dedup)
        previous = memo.setdefault(key, [])
        if any(cost == state.cost or cost.dominates(state.cost) for cost in previous):
            memo_pruned += 1
            return
        memo[key] = [cost for cost in previous if not state.cost.dominates(cost)] + [state.cost]
        if _prefix_dominated(state.cost, goals):
            dominance_pruned += 1
            return
        successors = _successors(state, config)
        witnesses = _goal(state, successors, config)
        if witnesses:
            endpoint_cost = state.cost.with_endpoint_cost(state.table_size)
            goals.append(TrajectoryResult(state, witnesses, endpoint_cost))
            if config.early_stop:
                return
        if len(state.steps) >= config.max_births:
            return
        for successor in successors:
            generated_states += 1
            if config.max_scope is not None and successor.steps[-1].child.arity > config.max_scope:
                scope_pruned += 1
                continue
            visit(successor)

    visit(initial)
    frontier = _pareto_trajectories(goals)
    return SearchResult(
        config,
        bool(frontier),
        minimum_births,
        frontier,
        explored_states + iterative_explored,
        generated_states,
        memo_pruned,
        dominance_pruned,
        scope_pruned,
        tuple(infeasible),
    )


def naive_clone_ascent(initial: AscentState, config: SearchConfig) -> SearchResult:
    goals: list[TrajectoryResult] = []
    explored = generated = scope_pruned = 0

    def visit(state: AscentState) -> None:
        nonlocal explored, generated, scope_pruned
        explored += 1
        successors = _successors(state, config)
        witnesses = _goal(state, successors, config)
        if witnesses:
            goals.append(TrajectoryResult(state, witnesses, state.cost.with_endpoint_cost(state.table_size)))
            if config.early_stop:
                return
        if len(state.steps) >= config.max_births:
            return
        for successor in successors:
            generated += 1
            if config.max_scope is not None and successor.steps[-1].child.arity > config.max_scope:
                scope_pruned += 1
                continue
            visit(successor)

    visit(initial)
    frontier = _pareto_trajectories(goals)
    minimum = min((len(item.state.steps) for item in goals), default=None)
    infeasible = tuple(range(minimum)) if minimum is not None else tuple(range(config.max_births + 1))
    return SearchResult(config, bool(frontier), minimum, frontier, explored, generated, 0, 0, scope_pruned, infeasible)
