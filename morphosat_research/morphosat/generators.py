from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Iterable

import networkx as nx

from .cnf import CNF


@dataclass(slots=True)
class GeneratedInstance:
    cnf: CNF
    expected_status: str
    family: str
    seed: int
    metadata: dict[str, object]


def encode_relation(scope: tuple[int, ...], allowed: Iterable[int]) -> list[tuple[int, ...]]:
    allowed_set = set(allowed)
    clauses: list[tuple[int, ...]] = []
    for t in range(1 << len(scope)):
        if t in allowed_set:
            continue
        # This full clause is false on exactly tuple t.
        clause = tuple(
            -var if ((t >> i) & 1) else var
            for i, var in enumerate(scope)
        )
        clauses.append(clause)
    return clauses


def _connected_regular_graph(n: int, degree: int, seed: int) -> nx.Graph:
    if n * degree % 2:
        raise ValueError("n*degree must be even")
    for attempt in range(100):
        g = nx.random_regular_graph(degree, n, seed=seed + 1009 * attempt)
        if nx.is_connected(g):
            return g
    raise RuntimeError("failed to generate a connected regular graph")


def _obfuscate_cnf(cnf: CNF, rng: Random, complement: bool = True) -> CNF:
    perm = list(range(1, cnf.nvars + 1))
    rng.shuffle(perm)
    flips = [False] + [bool(rng.getrandbits(1)) if complement else False for _ in range(cnf.nvars)]
    mapped: list[tuple[int, ...]] = []
    for clause in cnf.clauses:
        out: list[int] = []
        for lit in clause:
            old = abs(lit)
            new_lit = perm[old - 1] if lit > 0 else -perm[old - 1]
            if flips[old]:
                new_lit = -new_lit
            out.append(new_lit)
        rng.shuffle(out)
        mapped.append(tuple(out))
    rng.shuffle(mapped)
    return CNF(cnf.nvars, mapped)


def generate_obfuscated_tseitin(
    vertices: int,
    degree: int = 3,
    private_per_vertex: int = 2,
    unsat: bool = True,
    seed: int = 0,
) -> GeneratedInstance:
    """Generate a large hidden affine-CSP instance as ordinary CNF.

    Every vertex is a bounded-width semantic organ. Its incident edge bits obey
    a parity charge, while private bits are random affine functions of the edge
    bits. The joint relation is encoded only as its forbidden tuples, with all
    variables, literals and clauses shuffled. No XOR metadata reaches the solver.
    """
    rng = Random(seed)
    graph = _connected_regular_graph(vertices, degree, seed)
    edges = sorted(tuple(sorted(e)) for e in graph.edges())
    edge_var = {e: i + 1 for i, e in enumerate(edges)}
    next_var = len(edges) + 1
    private_vars: dict[int, tuple[int, ...]] = {}
    for v in range(vertices):
        private_vars[v] = tuple(range(next_var, next_var + private_per_vertex))
        next_var += private_per_vertex

    charges = [rng.getrandbits(1) for _ in range(vertices)]
    desired = 1 if unsat else 0
    if (sum(charges) & 1) != desired:
        charges[-1] ^= 1

    clauses: list[tuple[int, ...]] = []
    allowed_counts: list[int] = []
    block_arities: list[int] = []
    for v in range(vertices):
        incident = []
        for u in graph.neighbors(v):
            incident.append(edge_var[tuple(sorted((u, v)))])
        incident.sort()
        priv = private_vars[v]
        scope = tuple(incident) + priv
        block_arities.append(len(scope))

        private_specs: list[tuple[int, int]] = []
        for _ in priv:
            mask = 0
            while mask == 0:
                mask = rng.randrange(1, 1 << degree)
            private_specs.append((mask, rng.getrandbits(1)))

        allowed: list[int] = []
        for t in range(1 << len(scope)):
            edge_bits = t & ((1 << degree) - 1)
            if (edge_bits.bit_count() & 1) != charges[v]:
                continue
            ok = True
            for j, (mask, const) in enumerate(private_specs):
                expected = ((edge_bits & mask).bit_count() & 1) ^ const
                actual = (t >> (degree + j)) & 1
                if actual != expected:
                    ok = False
                    break
            if ok:
                allowed.append(t)
        allowed_counts.append(len(allowed))
        clauses.extend(encode_relation(scope, allowed))

    raw = CNF(nvars=next_var - 1, clauses=clauses)
    obfuscated = _obfuscate_cnf(raw, rng, complement=True)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="obfuscated_tseitin",
        seed=seed,
        metadata={
            "vertices": vertices,
            "degree": degree,
            "edges": len(edges),
            "private_per_vertex": private_per_vertex,
            "block_arity": max(block_arities, default=0),
            "allowed_per_block": sorted(set(allowed_counts)),
            "charge_parity": sum(charges) & 1,
            "semantic_labels_exposed": False,
        },
    )


def generate_hidden_2sat_chain(length: int, unsat: bool = True, seed: int = 0) -> GeneratedInstance:
    if length < 2:
        raise ValueError("length must be >=2")
    rng = Random(seed)
    clauses: list[tuple[int, ...]] = [(1,)]
    for i in range(1, length):
        # xi -> x{i+1}
        clauses.append((-i, i + 1))
    clauses.append((-(length),) if unsat else (length,))
    raw = CNF(length, clauses)
    # Polarity complementation preserves bijunctiveness but usually destroys a
    # common Horn orientation, forcing semantic 2-SAT recognition.
    obfuscated = _obfuscate_cnf(raw, rng, complement=True)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="hidden_2sat_chain",
        seed=seed,
        metadata={"length": length, "semantic_labels_exposed": False},
    )


def generate_hidden_horn_cascade(stages: int, unsat: bool = True, seed: int = 0) -> GeneratedInstance:
    if stages < 1:
        raise ValueError("stages must be >=1")
    rng = Random(seed)
    # x1=x2=true. Each stage derives a fresh variable from the last two true
    # variables. The final negative unit creates an UNSAT cascade if requested.
    clauses: list[tuple[int, ...]] = [(1,), (2,)]
    a, b = 1, 2
    next_var = 3
    for _ in range(stages):
        c = next_var
        next_var += 1
        clauses.append((-a, -b, c))
        a, b = b, c
    clauses.append((-b,) if unsat else (b,))
    raw = CNF(next_var - 1, clauses)
    obfuscated = _obfuscate_cnf(raw, rng, complement=False)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="hidden_horn_cascade",
        seed=seed,
        metadata={"stages": stages, "semantic_labels_exposed": False},
    )


def generate_random_small_cnf(nvars: int, nclauses: int, max_width: int, seed: int) -> CNF:
    rng = Random(seed)
    clauses: list[tuple[int, ...]] = []
    for _ in range(nclauses):
        width = rng.randint(1, min(max_width, nvars))
        vars_ = rng.sample(range(1, nvars + 1), width)
        clauses.append(tuple(v if rng.getrandbits(1) else -v for v in vars_))
    return CNF(nvars, clauses)


def _gate_relation(kind: str, inputs: tuple[int, ...], output: int | None = None, value: int | None = None) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return an exact local truth-table relation for an unlabeled Boolean gate.

    The returned tuple encoding uses bit i for scope[i]. This helper is only
    used by the benchmark generator; no gate labels are exposed to the solver.
    """
    kind = kind.lower()
    if kind in {"and", "or"}:
        if len(inputs) != 2 or output is None:
            raise ValueError(f"{kind} expects two inputs and one output")
        scope = (inputs[0], inputs[1], output)
        allowed: list[int] = []
        for a in (0, 1):
            for b in (0, 1):
                z = (a & b) if kind == "and" else (a | b)
                allowed.append(a | (b << 1) | (z << 2))
        return scope, tuple(sorted(allowed))
    if kind == "not":
        if len(inputs) != 1 or output is None:
            raise ValueError("not expects one input and one output")
        scope = (inputs[0], output)
        return scope, (0b10, 0b01)  # (x,z) in {(0,1),(1,0)}
    if kind == "const":
        if len(inputs) != 1 or value not in (0, 1):
            raise ValueError("const expects one variable and Boolean value")
        scope = (inputs[0],)
        return scope, (int(value),)
    raise ValueError(f"unknown gate kind: {kind}")


def generate_gate_obfuscated_tseitin(
    vertices: int,
    degree: int = 3,
    unsat: bool = True,
    seed: int = 0,
    complement: bool = True,
    encoding: str = "compact",
) -> GeneratedInstance:
    """Generate a Tseitin contradiction hidden behind heterogeneous gate tissue.

    Each degree-3 vertex parity is implemented *only* with exact AND, OR and
    NOT gate relations. The emitted instance is ordinary CNF with globally
    permuted/complemented variables and shuffled clauses. There are no XOR
    clauses, gate annotations, scopes, graph metadata or relation boundaries in
    the solver input. Recovering an affine language requires exact recursive
    existential fusion of heterogeneous local relations.
    """
    if degree != 3:
        raise ValueError("the first gate-tissue generator currently requires degree=3")
    rng = Random(seed)
    graph = _connected_regular_graph(vertices, degree, seed)
    edges = sorted(tuple(sorted(e)) for e in graph.edges())
    edge_var = {e: i + 1 for i, e in enumerate(edges)}
    next_var = len(edges) + 1
    clauses: list[tuple[int, ...]] = []
    gate_count = 0

    def fresh() -> int:
        nonlocal next_var
        out = next_var
        next_var += 1
        return out

    def emit(kind: str, inputs: tuple[int, ...], output: int | None = None, value: int | None = None) -> None:
        nonlocal gate_count
        if encoding == "truth_table":
            scope, allowed = _gate_relation(kind, inputs, output=output, value=value)
            clauses.extend(encode_relation(scope, allowed))
        elif encoding == "compact":
            if kind == "and":
                assert len(inputs) == 2 and output is not None
                a, b = inputs
                clauses.extend([(-a, -b, output), (a, -output), (b, -output)])
            elif kind == "or":
                assert len(inputs) == 2 and output is not None
                a, b = inputs
                clauses.extend([(a, b, -output), (-a, output), (-b, output)])
            elif kind == "not":
                assert len(inputs) == 1 and output is not None
                a = inputs[0]
                clauses.extend([(a, output), (-a, -output)])
            elif kind == "const":
                assert len(inputs) == 1 and value in (0, 1)
                clauses.append((inputs[0] if value else -inputs[0],))
            else:
                raise ValueError(f"unknown gate kind: {kind}")
        else:
            raise ValueError("encoding must be 'compact' or 'truth_table'")
        gate_count += 1

    def emit_xor(a: int, b: int) -> int:
        # Generic heterogeneous realization: (a OR b) AND NOT(a AND b).
        o = fresh()
        q = fresh()
        nq = fresh()
        z = fresh()
        emit("or", (a, b), o)
        emit("and", (a, b), q)
        emit("not", (q,), nq)
        emit("and", (o, nq), z)
        return z

    charges = [rng.getrandbits(1) for _ in range(vertices)]
    desired = 1 if unsat else 0
    if (sum(charges) & 1) != desired:
        charges[-1] ^= 1

    for v in range(vertices):
        incident = sorted(edge_var[tuple(sorted((u, v)))] for u in graph.neighbors(v))
        t = emit_xor(incident[0], incident[1])
        out = emit_xor(t, incident[2])
        emit("const", (out,), value=charges[v])

    raw = CNF(nvars=next_var - 1, clauses=clauses)
    obfuscated = _obfuscate_cnf(raw, rng, complement=complement)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="gate_obfuscated_tseitin",
        seed=seed,
        metadata={
            "vertices": vertices,
            "degree": degree,
            "edges": len(edges),
            "gate_relations": gate_count,
            "hidden_gate_basis": ["and", "or", "not", "const"],
            "target_emergent_language": "affine",
            "charge_parity": sum(charges) & 1,
            "semantic_labels_exposed": False,
            "scope_boundaries_exposed": False,
            "gate_encoding": encoding,
            "complemented_coordinates": complement,
        },
    )


def _append_compact_gate(
    clauses: list[tuple[int, ...]],
    kind: str,
    inputs: tuple[int, ...],
    output: int | None = None,
    value: int | None = None,
) -> None:
    if kind == "and":
        assert len(inputs) == 2 and output is not None
        a, b = inputs
        clauses.extend([(-a, -b, output), (a, -output), (b, -output)])
    elif kind == "or":
        assert len(inputs) == 2 and output is not None
        a, b = inputs
        clauses.extend([(a, b, -output), (-a, output), (-b, output)])
    elif kind == "not":
        assert len(inputs) == 1 and output is not None
        a = inputs[0]
        clauses.extend([(a, output), (-a, -output)])
    elif kind == "const":
        assert len(inputs) == 1 and value in (0, 1)
        clauses.append((inputs[0] if value else -inputs[0],))
    else:
        raise ValueError(kind)


def generate_gate_hidden_2sat_chain(length: int, unsat: bool = True, seed: int = 0) -> GeneratedInstance:
    """Hide a 2-SAT implication chain behind NOT/OR gate tissue."""
    if length < 2:
        raise ValueError("length must be >=2")
    rng = Random(seed)
    clauses: list[tuple[int, ...]] = []
    next_var = length + 1

    def fresh() -> int:
        nonlocal next_var
        out = next_var
        next_var += 1
        return out

    def emit_clause_or(a_var: int, a_neg: bool, b_var: int, b_neg: bool) -> None:
        inputs: list[int] = []
        for var, neg in ((a_var, a_neg), (b_var, b_neg)):
            if neg:
                nv = fresh()
                _append_compact_gate(clauses, "not", (var,), nv)
                inputs.append(nv)
            else:
                inputs.append(var)
        z = fresh()
        _append_compact_gate(clauses, "or", (inputs[0], inputs[1]), z)
        _append_compact_gate(clauses, "const", (z,), value=1)

    _append_compact_gate(clauses, "const", (1,), value=1)
    for i in range(1, length):
        emit_clause_or(i, True, i + 1, False)  # xi -> x{i+1}
    _append_compact_gate(clauses, "const", (length,), value=0 if unsat else 1)

    raw = CNF(next_var - 1, clauses)
    obfuscated = _obfuscate_cnf(raw, rng, complement=True)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="gate_hidden_2sat_chain",
        seed=seed,
        metadata={
            "length": length,
            "hidden_gate_basis": ["not", "or", "const"],
            "target_emergent_language": "bijunctive",
            "semantic_labels_exposed": False,
            "scope_boundaries_exposed": False,
        },
    )


def generate_gate_hidden_horn_cascade(stages: int, unsat: bool = True, seed: int = 0) -> GeneratedInstance:
    """Hide a Horn forward-chaining instance behind NOT/OR gate tissue."""
    if stages < 1:
        raise ValueError("stages must be >=1")
    rng = Random(seed)
    clauses: list[tuple[int, ...]] = []
    original_nvars = stages + 2
    next_var = original_nvars + 1

    def fresh() -> int:
        nonlocal next_var
        out = next_var
        next_var += 1
        return out

    def emit_horn_implication(a: int, b: int, c: int) -> None:
        na, nb = fresh(), fresh()
        _append_compact_gate(clauses, "not", (a,), na)
        _append_compact_gate(clauses, "not", (b,), nb)
        w = fresh()
        _append_compact_gate(clauses, "or", (na, nb), w)
        z = fresh()
        _append_compact_gate(clauses, "or", (w, c), z)
        _append_compact_gate(clauses, "const", (z,), value=1)

    _append_compact_gate(clauses, "const", (1,), value=1)
    _append_compact_gate(clauses, "const", (2,), value=1)
    a, b = 1, 2
    for c in range(3, original_nvars + 1):
        emit_horn_implication(a, b, c)
        a, b = b, c
    _append_compact_gate(clauses, "const", (b,), value=0 if unsat else 1)

    raw = CNF(next_var - 1, clauses)
    # Preserve the Horn orientation while still hiding every variable and clause order.
    obfuscated = _obfuscate_cnf(raw, rng, complement=False)
    return GeneratedInstance(
        cnf=obfuscated,
        expected_status="UNSAT" if unsat else "SAT",
        family="gate_hidden_horn_cascade",
        seed=seed,
        metadata={
            "stages": stages,
            "hidden_gate_basis": ["not", "or", "const"],
            "target_emergent_language": "horn",
            "semantic_labels_exposed": False,
            "scope_boundaries_exposed": False,
        },
    )
