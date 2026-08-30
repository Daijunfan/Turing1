from __future__ import annotations

from functools import lru_cache
from itertools import combinations

import networkx as nx

from .cnf import CNF
from .exact_width import TRACTABLE
from .relations import RelationBlock
from .schaefer import classify_block


SemanticRelation = tuple[tuple[int, ...], tuple[int, ...]]


def _primal_graph(blocks: list[RelationBlock]) -> nx.Graph:
    graph = nx.Graph()
    for block in blocks:
        graph.add_nodes_from(block.scope)
        graph.add_edges_from(combinations(block.scope, 2))
    return graph


def _incidence_graph(cnf: CNF) -> nx.Graph:
    graph = nx.Graph()
    variables = [("v", variable) for variable in range(1, cnf.nvars + 1)]
    clauses = [("c", index) for index in range(len(cnf.clauses))]
    graph.add_nodes_from(variables + clauses)
    for index, clause in enumerate(cnf.clauses):
        graph.add_edges_from((("v", abs(literal)), ("c", index)) for literal in clause)
    return graph


def _elimination_neighbours(adjacency: list[int], eliminated: int, vertex: int) -> int:
    remaining = ((1 << len(adjacency)) - 1) ^ eliminated
    reached_eliminated = 0
    frontier = adjacency[vertex] & eliminated
    neighbours = adjacency[vertex] & remaining & ~(1 << vertex)
    while frontier:
        bit = frontier & -frontier
        frontier ^= bit
        if reached_eliminated & bit:
            continue
        reached_eliminated |= bit
        index = bit.bit_length() - 1
        neighbours |= adjacency[index] & remaining & ~(1 << vertex)
        frontier |= adjacency[index] & eliminated & ~reached_eliminated
    return neighbours


def exact_treewidth(graph: nx.Graph) -> tuple[int, list[object]]:
    nodes = list(graph.nodes())
    if len(nodes) <= 1:
        return 0, nodes
    position = {node: index for index, node in enumerate(nodes)}
    adjacency = [0] * len(nodes)
    for a, b in graph.edges():
        adjacency[position[a]] |= 1 << position[b]
        adjacency[position[b]] |= 1 << position[a]
    full = (1 << len(nodes)) - 1

    @lru_cache(maxsize=None)
    def solve(eliminated: int) -> tuple[int, tuple[int, ...]]:
        if eliminated == full:
            return 0, tuple()
        best_width = len(nodes)
        best_order: tuple[int, ...] = tuple()
        remaining = full ^ eliminated
        while remaining:
            bit = remaining & -remaining
            remaining ^= bit
            vertex = bit.bit_length() - 1
            degree = _elimination_neighbours(adjacency, eliminated, vertex).bit_count()
            tail_width, tail = solve(eliminated | bit)
            width = max(degree, tail_width)
            if width < best_width:
                best_width = width
                best_order = (vertex,) + tail
        return best_width, best_order

    width, order = solve(0)
    return width, [nodes[index] for index in order]


def treewidth_bounds(graph: nx.Graph, exact_limit: int = 14) -> dict[str, object]:
    if graph.number_of_nodes() <= exact_limit:
        width, order = exact_treewidth(graph)
        return {"value": width, "kind": "exact", "lower": width, "upper": width, "order": order}
    upper, _ = nx.approximation.treewidth_min_fill_in(graph)
    lower = max(nx.core_number(graph).values(), default=0) if graph.number_of_edges() else 0
    return {"value": None, "kind": "bounds", "lower": lower, "upper": upper, "order": []}


@lru_cache(maxsize=None)
def _relation_classes(relation: SemanticRelation) -> frozenset[str]:
    scope, allowed = relation
    block = RelationBlock(0, scope, tuple(), tuple(), allowed)
    classify_block(block)
    return block.classes & TRACTABLE


def _restrict(relation: SemanticRelation, assignment: tuple[tuple[int, int], ...]) -> SemanticRelation:
    scope, allowed = relation
    fixed = dict(assignment)
    remaining = tuple(variable for variable in scope if variable not in fixed)
    positions = {variable: index for index, variable in enumerate(scope)}
    residual: set[int] = set()
    for bits in allowed:
        if any(((bits >> positions[var]) & 1) != value for var, value in fixed.items() if var in positions):
            continue
        projected = 0
        for index, variable in enumerate(remaining):
            projected |= ((bits >> positions[variable]) & 1) << index
        residual.add(projected)
    return remaining, tuple(sorted(residual))


def _restrict_all(relations: tuple[SemanticRelation, ...], assignment: tuple[tuple[int, int], ...]):
    return tuple(sorted(set(_restrict(relation, assignment) for relation in relations)))


def _in_class(relations: tuple[SemanticRelation, ...], target: str) -> bool:
    return all(target in _relation_classes(relation) for relation in relations)


def _scattered(relations: tuple[SemanticRelation, ...]) -> bool:
    if not relations:
        return True
    graph = nx.Graph()
    graph.add_nodes_from(range(len(relations)))
    by_variable: dict[int, list[int]] = {}
    for index, (scope, _) in enumerate(relations):
        for variable in scope:
            by_variable.setdefault(variable, []).append(index)
    for indices in by_variable.values():
        graph.add_edges_from(combinations(indices, 2))
    targets = {"affine", "horn", "bijunctive"}
    return all(
        bool(set.intersection(*[set(_relation_classes(relations[index])) for index in component]) & targets)
        for component in nx.connected_components(graph)
    )


def _is_strong(
    relations: tuple[SemanticRelation, ...], variables: tuple[int, ...], target: str
) -> bool:
    for bits in range(1 << len(variables)):
        assignment = tuple((variable, (bits >> index) & 1) for index, variable in enumerate(variables))
        residual = _restrict_all(relations, assignment)
        if target == "scattered":
            if not _scattered(residual):
                return False
        elif not _in_class(residual, target):
            return False
    return True


def exact_strong_backdoor(
    blocks: list[RelationBlock], target: str
) -> tuple[int, tuple[int, ...]]:
    relations = tuple(sorted((block.scope, block.allowed) for block in blocks))
    variables = sorted({variable for scope, _ in relations for variable in scope})
    for size in range(len(variables) + 1):
        for candidate in combinations(variables, size):
            if _is_strong(relations, candidate, target):
                return size, candidate
    return len(variables), tuple(variables)


def exact_backdoor_depth(blocks: list[RelationBlock], target: str) -> int:
    initial = tuple(sorted((block.scope, block.allowed) for block in blocks))

    @lru_cache(maxsize=None)
    def depth(relations: tuple[SemanticRelation, ...]) -> int:
        if (target == "scattered" and _scattered(relations)) or (
            target != "scattered" and _in_class(relations, target)
        ):
            return 0
        variables = sorted({variable for scope, _ in relations for variable in scope})
        if not variables:
            return 0
        best = len(variables)
        for variable in variables:
            branches = []
            for value in (0, 1):
                branches.append(depth(_restrict_all(relations, ((variable, value),))))
            best = min(best, 1 + max(branches))
        return best

    return depth(initial)


def _torso(primal: nx.Graph, backdoor: tuple[int, ...]) -> nx.Graph:
    selected = set(backdoor)
    torso = primal.subgraph(selected).copy()
    outside = primal.subgraph(set(primal.nodes()) - selected)
    for component in nx.connected_components(outside):
        boundary = set().union(*(set(primal.neighbors(vertex)) for vertex in component)) & selected
        torso.add_edges_from(combinations(boundary, 2))
    return torso


def exact_backdoor_treewidth(blocks: list[RelationBlock], target: str) -> tuple[int, tuple[int, ...]]:
    relations = tuple(sorted((block.scope, block.allowed) for block in blocks))
    variables = sorted({variable for scope, _ in relations for variable in scope})
    primal = _primal_graph(blocks)
    best_width = len(variables)
    best_set: tuple[int, ...] = tuple(variables)
    for size in range(len(variables) + 1):
        for candidate in combinations(variables, size):
            if not _is_strong(relations, candidate, target):
                continue
            width, _ = exact_treewidth(_torso(primal, candidate))
            if width < best_width or (width == best_width and len(candidate) < len(best_set)):
                best_width, best_set = width, candidate
    return best_width, best_set


def compute_parameter_record(
    cnf: CNF,
    blocks: list[RelationBlock],
    exact_variable_limit: int = 10,
    exact_graph_limit: int = 14,
) -> dict[str, object]:
    variables = sorted({variable for block in blocks for variable in block.scope})
    primal = treewidth_bounds(_primal_graph(blocks), exact_graph_limit)
    incidence = treewidth_bounds(_incidence_graph(cnf), exact_graph_limit)
    record: dict[str, object] = {
        "primal_treewidth": primal["value"],
        "primal_treewidth_kind": primal["kind"],
        "primal_treewidth_lower": primal["lower"],
        "primal_treewidth_upper": primal["upper"],
        # Complete relation-variable elimination has exactly the primal induced-width objective.
        "induced_width": primal["value"],
        "induced_width_kind": primal["kind"],
        "induced_width_lower": primal["lower"],
        "induced_width_upper": primal["upper"],
        "incidence_treewidth": incidence["value"],
        "incidence_treewidth_kind": incidence["kind"],
        "incidence_treewidth_lower": incidence["lower"],
        "incidence_treewidth_upper": incidence["upper"],
    }
    for target in ("affine", "horn", "bijunctive", "scattered"):
        prefix = "2cnf" if target == "bijunctive" else target
        if len(variables) <= exact_variable_limit:
            size, witness = exact_strong_backdoor(blocks, target)
            depth = exact_backdoor_depth(blocks, target)
            btw, btw_set = exact_backdoor_treewidth(blocks, target)
            record.update({
                f"{prefix}_strong_backdoor_size": size,
                f"{prefix}_strong_backdoor_kind": "exact",
                f"{prefix}_strong_backdoor_witness": list(witness),
                f"{prefix}_backdoor_depth": depth,
                f"{prefix}_backdoor_depth_kind": "exact",
                f"{prefix}_backdoor_treewidth": btw,
                f"{prefix}_backdoor_treewidth_kind": "exact",
                f"{prefix}_backdoor_treewidth_witness": list(btw_set),
            })
        else:
            already = _is_strong(
                tuple(sorted((block.scope, block.allowed) for block in blocks)), tuple(), target
            )
            lower = upper = 0 if already else None
            record.update({
                f"{prefix}_strong_backdoor_size": 0 if already else None,
                f"{prefix}_strong_backdoor_kind": "exact" if already else "bounds",
                f"{prefix}_strong_backdoor_lower": lower if lower is not None else 1,
                f"{prefix}_strong_backdoor_upper": upper if upper is not None else len(variables),
                f"{prefix}_backdoor_depth": 0 if already else None,
                f"{prefix}_backdoor_depth_kind": "exact" if already else "bounds",
                f"{prefix}_backdoor_depth_lower": lower if lower is not None else 1,
                f"{prefix}_backdoor_depth_upper": upper if upper is not None else len(variables),
                f"{prefix}_backdoor_treewidth": 0 if already else None,
                f"{prefix}_backdoor_treewidth_kind": "exact" if already else "unavailable",
            })
    return record
