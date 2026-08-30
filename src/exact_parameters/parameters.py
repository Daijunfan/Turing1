from __future__ import annotations

from functools import lru_cache
from itertools import combinations

import networkx as nx

from src.clone_ascent.polymorphisms import NAMED_WITNESSES, preservation_signature_leq3
from src.clone_ascent.relations import Relation
from .joinwidth import exact_joinwidth


TARGET_WITNESS = {
    "affine": "minority",
    "horn": "and",
    "dual_horn": "or",
    "bijunctive": "majority",
}
SCATTERED_WITNESSES = tuple(TARGET_WITNESS.values()) + ("constant_0", "constant_1")


def _primal_graph(relations: tuple[Relation, ...]) -> nx.Graph:
    graph = nx.Graph()
    for relation in relations:
        graph.add_nodes_from(relation.scope)
        graph.add_edges_from(combinations(relation.scope, 2))
    return graph


def _incidence_graph(relations: tuple[Relation, ...]) -> nx.Graph:
    graph = nx.Graph()
    for index, relation in enumerate(relations):
        constraint = ("c", index)
        graph.add_node(constraint)
        for variable in relation.scope:
            node = ("v", variable)
            graph.add_edge(constraint, node)
    return graph


def _elimination_neighbours(adjacency: list[int], eliminated: int, vertex: int) -> int:
    remaining = ((1 << len(adjacency)) - 1) ^ eliminated
    reached = 0
    frontier = adjacency[vertex] & eliminated
    neighbours = adjacency[vertex] & remaining & ~(1 << vertex)
    while frontier:
        bit = frontier & -frontier
        frontier ^= bit
        if reached & bit:
            continue
        reached |= bit
        index = bit.bit_length() - 1
        neighbours |= adjacency[index] & remaining & ~(1 << vertex)
        frontier |= adjacency[index] & eliminated & ~reached
    return neighbours


def exact_treewidth(graph: nx.Graph) -> tuple[int, tuple[object, ...]]:
    nodes = tuple(graph.nodes())
    if len(nodes) <= 1:
        return 0, nodes
    position = {node: index for index, node in enumerate(nodes)}
    adjacency = [0] * len(nodes)
    for left, right in graph.edges():
        adjacency[position[left]] |= 1 << position[right]
        adjacency[position[right]] |= 1 << position[left]
    full = (1 << len(nodes)) - 1

    @lru_cache(maxsize=None)
    def solve(eliminated: int) -> tuple[int, tuple[int, ...]]:
        if eliminated == full:
            return 0, tuple()
        best_width = len(nodes)
        best_order = tuple()
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
    return width, tuple(nodes[index] for index in order)


def _treewidth_record(graph: nx.Graph, exact_limit: int) -> dict[str, object]:
    if graph.number_of_nodes() <= exact_limit:
        value, order = exact_treewidth(graph)
        return {"value": value, "status": "EXACT", "lower": value, "upper": value, "witness": list(order)}
    upper, _ = nx.approximation.treewidth_min_fill_in(graph)
    lower = max(nx.core_number(graph).values(), default=0) if graph.number_of_edges() else 0
    return {"value": None, "status": "UNKNOWN", "lower": lower, "upper": upper, "witness": []}


def _restrict(relation: Relation, assignment: tuple[tuple[int, int], ...]) -> Relation:
    fixed = dict(assignment)
    keep = tuple(variable for variable in relation.scope if variable not in fixed)
    position = {variable: index for index, variable in enumerate(relation.scope)}
    allowed = set()
    for bits in relation.allowed:
        if any(((bits >> position[variable]) & 1) != value for variable, value in fixed.items() if variable in position):
            continue
        projected = 0
        for index, variable in enumerate(keep):
            projected |= ((bits >> position[variable]) & 1) << index
        allowed.add(projected)
    return Relation.from_allowed(keep, sorted(allowed))


def _restrict_all(relations: tuple[Relation, ...], assignment: tuple[tuple[int, int], ...]) -> tuple[Relation, ...]:
    return tuple(sorted(_restrict(relation, assignment) for relation in relations))


def _components(relations: tuple[Relation, ...]) -> tuple[tuple[Relation, ...], ...]:
    graph = nx.Graph()
    graph.add_nodes_from(range(len(relations)))
    by_variable: dict[int, list[int]] = {}
    for index, relation in enumerate(relations):
        for variable in relation.scope:
            by_variable.setdefault(variable, []).append(index)
    for indices in by_variable.values():
        graph.add_edges_from(combinations(indices, 2))
    return tuple(tuple(relations[index] for index in sorted(component)) for component in nx.connected_components(graph))


def _has_witness(relations: tuple[Relation, ...], witness: str) -> bool:
    bit = NAMED_WITNESSES[witness]
    return all(preservation_signature_leq3(relation) & bit for relation in relations)


def _target(relations: tuple[Relation, ...], target: str) -> bool:
    if target == "scattered":
        return all(
            any(_has_witness(component, witness) for witness in SCATTERED_WITNESSES)
            for component in _components(relations)
        )
    return _has_witness(relations, TARGET_WITNESS[target])


def _strong(relations: tuple[Relation, ...], candidate: tuple[int, ...], target: str) -> bool:
    for bits in range(1 << len(candidate)):
        assignment = tuple((variable, (bits >> index) & 1) for index, variable in enumerate(candidate))
        if not _target(_restrict_all(relations, assignment), target):
            return False
    return True


def exact_strong_backdoor(relations: tuple[Relation, ...], target: str) -> tuple[int, tuple[int, ...]]:
    variables = tuple(sorted({variable for relation in relations for variable in relation.scope}))
    for size in range(len(variables) + 1):
        for candidate in combinations(variables, size):
            if _strong(relations, candidate, target):
                return size, candidate
    return len(variables), variables


def exact_backdoor_depth(relations: tuple[Relation, ...], target: str, recursive: bool) -> int:
    @lru_cache(maxsize=None)
    def solve(state: tuple[Relation, ...]) -> int:
        if _target(state, target):
            return 0
        if recursive:
            components = _components(state)
            if len(components) > 1:
                return max(solve(component) for component in components)
        variables = tuple(sorted({variable for relation in state for variable in relation.scope}))
        if not variables:
            return 0
        return min(
            1 + max(
                solve(_restrict_all(state, ((variable, 0),))),
                solve(_restrict_all(state, ((variable, 1),))),
            )
            for variable in variables
        )

    return solve(tuple(sorted(relations)))


def _torso(primal: nx.Graph, backdoor: tuple[int, ...]) -> nx.Graph:
    selected = set(backdoor)
    torso = primal.subgraph(selected).copy()
    outside = primal.subgraph(set(primal.nodes()) - selected)
    for component in nx.connected_components(outside):
        boundary = set().union(*(set(primal.neighbors(variable)) for variable in component)) & selected
        torso.add_edges_from(combinations(boundary, 2))
    return torso


def exact_backdoor_treewidth(relations: tuple[Relation, ...], target: str) -> tuple[int, tuple[int, ...]]:
    variables = tuple(sorted({variable for relation in relations for variable in relation.scope}))
    primal = _primal_graph(relations)
    best = len(variables)
    witness = variables
    for size in range(len(variables) + 1):
        for candidate in combinations(variables, size):
            if not _strong(relations, candidate, target):
                continue
            width, _ = exact_treewidth(_torso(primal, candidate))
            if width < best or (width == best and size < len(witness)):
                best, witness = width, candidate
    return best, witness


def exact_parameter_bundle(
    relations: tuple[Relation, ...],
    exact_variable_limit: int = 10,
    exact_graph_limit: int = 16,
    exact_constraint_limit: int = 12,
) -> dict[str, object]:
    primal = _treewidth_record(_primal_graph(relations), exact_graph_limit)
    incidence = _treewidth_record(_incidence_graph(relations), exact_graph_limit)
    record: dict[str, object] = {
        "primal_treewidth": primal,
        "incidence_treewidth": incidence,
        "induced_width": dict(primal),
    }
    if len(relations) <= exact_constraint_limit:
        record["linear_joinwidth"] = exact_joinwidth(relations, linear=True).to_dict()
        record["general_joinwidth"] = exact_joinwidth(relations, linear=False).to_dict()
    else:
        record["linear_joinwidth"] = {"value": None, "status": "UNKNOWN"}
        record["general_joinwidth"] = {"value": None, "status": "UNKNOWN"}
    variables = {variable for relation in relations for variable in relation.scope}
    for target in ("affine", "horn", "dual_horn", "bijunctive", "scattered"):
        if len(variables) <= exact_variable_limit:
            size, size_witness = exact_strong_backdoor(relations, target)
            depth = exact_backdoor_depth(relations, target, recursive=False)
            recursive_depth = exact_backdoor_depth(relations, target, recursive=True)
            treewidth, treewidth_witness = exact_backdoor_treewidth(relations, target)
            record[target] = {
                "strong_backdoor_size": {"value": size, "status": "EXACT", "witness": list(size_witness)},
                "backdoor_depth": {"value": depth, "status": "EXACT"},
                "recursive_backdoor_depth": {"value": recursive_depth, "status": "EXACT"},
                "backdoor_treewidth": {
                    "value": treewidth, "status": "EXACT", "witness": list(treewidth_witness)
                },
            }
        else:
            record[target] = {
                "strong_backdoor_size": {"value": None, "status": "UNKNOWN", "lower": 0, "upper": len(variables)},
                "backdoor_depth": {"value": None, "status": "UNKNOWN", "lower": 0, "upper": len(variables)},
                "recursive_backdoor_depth": {"value": None, "status": "UNKNOWN", "lower": 0, "upper": len(variables)},
                "backdoor_treewidth": {"value": None, "status": "UNKNOWN"},
            }
    return record

