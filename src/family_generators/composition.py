from __future__ import annotations

import math

import networkx as nx


def skeleton_graph(kind: str, size: int, seed: int = 0) -> nx.Graph:
    if kind == "path":
        return nx.path_graph(size)
    if kind == "balanced_tree":
        height = max(0, math.ceil(math.log2(size + 1)) - 1)
        graph = nx.balanced_tree(2, height)
        return graph.subgraph(sorted(graph.nodes())[:size]).copy()
    if kind == "grid":
        side = math.ceil(math.sqrt(size))
        graph = nx.convert_node_labels_to_integers(nx.grid_2d_graph(side, side))
        return graph.subgraph(range(size)).copy()
    if kind == "expander":
        degree = min(3, size - 1)
        if size * degree % 2:
            degree -= 1
        return nx.random_regular_graph(max(1, degree), size, seed=seed)
    if kind == "tseitin_core":
        degree = min(3, size - 1)
        if size * degree % 2:
            degree -= 1
        return nx.random_regular_graph(max(1, degree), size, seed=seed)
    raise ValueError(kind)


def compose_morphon(
    formula: tuple[tuple[int, ...], ...],
    kind: str,
    size: int,
    seed: int = 0,
) -> tuple[int, tuple[tuple[int, ...], ...], dict[str, object]]:
    """Place one gadget at each skeleton vertex and share its first variable.

    The current v0.3-discovered Morphons are locally inconsistent. This
    generator is retained to make that composition failure explicit rather
    than silently omitting the attempted infinite families.
    """
    graph = skeleton_graph(kind, size, seed)
    local_variables = sorted({abs(literal) for clause in formula for literal in clause})
    shared = {vertex: index + 1 for index, vertex in enumerate(sorted(graph.nodes()))}
    next_variable = len(shared) + 1
    clauses = []
    maps = []
    for vertex in sorted(graph.nodes()):
        mapping = {local_variables[0]: shared[vertex]}
        for variable in local_variables[1:]:
            mapping[variable] = next_variable
            next_variable += 1
        maps.append(mapping)
        clauses.extend(
            tuple(mapping[abs(literal)] if literal > 0 else -mapping[abs(literal)] for literal in clause)
            for clause in formula
        )
    return next_variable - 1, tuple(clauses), {
        "skeleton": kind,
        "size": size,
        "vertices": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "gadget_maps": maps,
        "locally_inconsistent_gadget": True,
        "candidate_rejected": True,
    }

