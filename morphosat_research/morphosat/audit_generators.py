from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random

import networkx as nx

from .bruteforce import solve_bruteforce
from .cnf import CNF
from .generators import GeneratedInstance, encode_relation


def _regular_graph(vertices: int, seed: int, degree: int = 3) -> nx.Graph:
    for attempt in range(100):
        graph = nx.random_regular_graph(degree, vertices, seed=seed + 1009 * attempt)
        if nx.is_connected(graph):
            return graph
    raise RuntimeError("failed to generate a connected regular graph")


def _obfuscate(cnf: CNF, rng: Random) -> CNF:
    permutation = list(range(1, cnf.nvars + 1))
    rng.shuffle(permutation)
    flip = [False] + [bool(rng.getrandbits(1)) for _ in range(cnf.nvars)]
    clauses: list[tuple[int, ...]] = []
    for clause in cnf.clauses:
        mapped = []
        for literal in clause:
            old = abs(literal)
            new = permutation[old - 1] if literal > 0 else -permutation[old - 1]
            mapped.append(-new if flip[old] else new)
        rng.shuffle(mapped)
        clauses.append(tuple(mapped))
    rng.shuffle(clauses)
    return CNF(cnf.nvars, clauses)


@dataclass
class _Circuit:
    next_var: int
    clauses: list[tuple[int, ...]]

    def fresh(self) -> int:
        var = self.next_var
        self.next_var += 1
        return var

    def gate(self, kind: str, inputs: tuple[int, ...], value: int | None = None) -> int:
        kind = kind.lower()
        output = self.fresh()
        scope = inputs + (output,)
        allowed: list[int] = []
        for bits in range(1 << len(inputs)):
            values = [(bits >> i) & 1 for i in range(len(inputs))]
            if kind == "not":
                expected = 1 - values[0]
            elif kind == "and":
                expected = values[0] & values[1]
            elif kind == "or":
                expected = values[0] | values[1]
            elif kind == "nand":
                expected = 1 - (values[0] & values[1])
            elif kind == "nor":
                expected = 1 - (values[0] | values[1])
            elif kind == "mux":
                expected = values[1] if values[0] else values[2]
            elif kind == "maj":
                expected = int(sum(values) >= 2)
            else:
                raise ValueError(kind)
            allowed.append(bits | (expected << len(inputs)))
        self.clauses.extend(encode_relation(scope, allowed))
        return output

    def const(self, value: int) -> int:
        output = self.fresh()
        self.clauses.append((output if value else -output,))
        return output

    def xor(self, a: int, b: int, template: str) -> int:
        if template == "nand":
            t = self.gate("nand", (a, b))
            u = self.gate("nand", (a, t))
            v = self.gate("nand", (b, t))
            return self.gate("nand", (u, v))
        if template == "nor":
            t = self.gate("nor", (a, b))
            u = self.gate("nor", (a, t))
            v = self.gate("nor", (b, t))
            xnor = self.gate("nor", (u, v))
            return self.gate("nor", (xnor, xnor))
        if template == "mux":
            nb = self.gate("not", (b,))
            return self.gate("mux", (a, nb, b))
        if template == "maj":
            na = self.gate("not", (a,))
            nb = self.gate("not", (b,))
            zero = self.const(0)
            one = self.const(1)
            p = self.gate("maj", (a, nb, zero))
            q = self.gate("maj", (na, b, zero))
            return self.gate("maj", (p, q, one))
        if template == "and_or_not":
            either = self.gate("or", (a, b))
            both = self.gate("and", (a, b))
            not_both = self.gate("not", (both,))
            return self.gate("and", (either, not_both))
        raise ValueError(template)


XOR_TEMPLATES = ("nand", "nor", "mux", "maj", "and_or_not")


def verify_xor_templates() -> dict[str, bool]:
    """Exhaustively eliminate auxiliaries for every circuit template."""
    verified: dict[str, bool] = {}
    for template in XOR_TEMPLATES:
        circuit = _Circuit(3, [])
        output = circuit.xor(1, 2, template)
        cnf = CNF(circuit.next_var - 1, circuit.clauses)
        observed: set[tuple[int, int, int]] = set()
        for assignment in range(1 << cnf.nvars):
            if cnf.is_satisfied(assignment):
                observed.add(
                    ((assignment >> 0) & 1, (assignment >> 1) & 1,
                     (assignment >> (output - 1)) & 1)
                )
        expected = {(a, b, a ^ b) for a in (0, 1) for b in (0, 1)}
        verified[template] = observed == expected
    return verified


def _split_clauses(cnf: CNF, rng: Random) -> CNF:
    """Replace each C by a two-step existential chain equivalent to C."""
    next_var = cnf.nvars + 1
    split: list[tuple[int, ...]] = []
    for clause in cnf.clauses:
        p, q = next_var, next_var + 1
        next_var += 2
        first = list(clause) + [p]
        rng.shuffle(first)
        chain = [tuple(first), (-p, q), (-q,)]
        if rng.getrandbits(1):
            chain[1] = tuple(reversed(chain[1]))
        split.extend(chain)
    rng.shuffle(split)
    return CNF(next_var - 1, split)


def generate_heterogeneous_tseitin(
    vertices: int,
    unsat: bool,
    seed: int,
    split_relations: bool = False,
) -> GeneratedInstance:
    """B/C layer: every hidden XOR independently chooses a circuit basis."""
    rng = Random(seed)
    graph = _regular_graph(vertices, seed)
    edges = sorted(tuple(sorted(edge)) for edge in graph.edges())
    edge_var = {edge: i + 1 for i, edge in enumerate(edges)}
    circuit = _Circuit(len(edges) + 1, [])
    charges = [rng.getrandbits(1) for _ in range(vertices)]
    if (sum(charges) & 1) != int(unsat):
        charges[-1] ^= 1
    choices = [rng.choice(XOR_TEMPLATES) for _ in range(2 * vertices)]
    if len(set(choices)) == 1 and len(choices) > 1:
        choices[-1] = XOR_TEMPLATES[(XOR_TEMPLATES.index(choices[0]) + 1) % len(XOR_TEMPLATES)]
    choice_index = 0
    for vertex in range(vertices):
        incident = sorted(edge_var[tuple(sorted((vertex, other)))] for other in graph.neighbors(vertex))
        first = circuit.xor(incident[0], incident[1], choices[choice_index])
        choice_index += 1
        output = circuit.xor(first, incident[2], choices[choice_index])
        choice_index += 1
        circuit.clauses.append((output if charges[vertex] else -output,))
    raw = CNF(circuit.next_var - 1, circuit.clauses)
    if split_relations:
        raw = _split_clauses(raw, rng)
    cnf = _obfuscate(raw, rng)
    scope_counts = Counter(tuple(sorted({abs(literal) for literal in clause})) for clause in cnf.clauses)
    layer = "C" if split_relations else "B"
    return GeneratedInstance(
        cnf=cnf,
        expected_status="UNSAT" if unsat else "SAT",
        family=f"layer_{layer.lower()}_heterogeneous_tseitin",
        seed=seed,
        metadata={
            "layer": layer,
            "vertices": vertices,
            "gate_templates": dict(Counter(choices)),
            "random_polarities": True,
            "scope_boundaries_exposed": False,
            "split_requires_multistep_join_project": split_relations,
            "max_initial_same_scope_clause_block": max(scope_counts.values(), default=0),
            "true_multigeneration_candidate": True,
            "charge_parity": sum(charges) & 1,
        },
    )


def generate_resolution_tseitin(
    vertices: int,
    unsat: bool,
    seed: int,
    reordered: bool = False,
) -> GeneratedInstance:
    """D layer resolution reference; no claim of endogenous morphology."""
    rng = Random(seed)
    graph = _regular_graph(vertices, seed)
    edges = sorted(tuple(sorted(edge)) for edge in graph.edges())
    edge_var = {edge: i + 1 for i, edge in enumerate(edges)}
    charges = [rng.getrandbits(1) for _ in range(vertices)]
    if (sum(charges) & 1) != int(unsat):
        charges[-1] ^= 1
    clauses: list[tuple[int, ...]] = []
    for vertex in range(vertices):
        scope = tuple(sorted(edge_var[tuple(sorted((vertex, other)))] for other in graph.neighbors(vertex)))
        allowed = [bits for bits in range(8) if bits.bit_count() % 2 == charges[vertex]]
        clauses.extend(encode_relation(scope, allowed))
    raw = CNF(len(edges), clauses)
    cnf = _obfuscate(raw, rng) if reordered else raw
    name = "random_reordered_parity" if reordered else "resolution_tseitin_reference"
    return GeneratedInstance(
        cnf=cnf,
        expected_status="UNSAT" if unsat else "SAT",
        family=f"layer_d_{name}",
        seed=seed,
        metadata={
            "layer": "D",
            "vertices": vertices,
            "resolution_hard_reference": True,
            "true_multigeneration_candidate": False,
            "random_reordered": reordered,
            "charge_parity": sum(charges) & 1,
        },
    )


def verify_small_instance(cnf: CNF, expected_status: str, max_vars: int = 22) -> bool | None:
    if cnf.nvars > max_vars:
        return None
    status, _ = solve_bruteforce(cnf)
    return status == expected_status
