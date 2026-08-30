from __future__ import annotations

from dataclasses import dataclass
from collections import deque


@dataclass(slots=True)
class TractableResult:
    status: str
    assignment: int | None
    certificate: dict[str, object]


def literal_true(lit: int, assignment: int) -> bool:
    value = bool((assignment >> (abs(lit) - 1)) & 1)
    return value if lit > 0 else not value


def solve_2sat(nvars: int, clauses: list[tuple[int, ...]]) -> TractableResult:
    n = 2 * nvars
    graph = [[] for _ in range(n)]
    rev = [[] for _ in range(n)]

    def node(lit: int) -> int:
        v = abs(lit) - 1
        return 2 * v + (0 if lit > 0 else 1)

    def neg(idx: int) -> int:
        return idx ^ 1

    def add_edge(a: int, b: int) -> None:
        graph[a].append(b)
        rev[b].append(a)

    normalized: list[tuple[int, int]] = []
    for clause in clauses:
        if len(clause) == 0:
            return TractableResult("UNSAT", None, {"reason": "empty_clause"})
        if len(clause) == 1:
            a = node(clause[0])
            add_edge(neg(a), a)
            normalized.append((clause[0], clause[0]))
        elif len(clause) == 2:
            a, b = map(node, clause)
            add_edge(neg(a), b)
            add_edge(neg(b), a)
            normalized.append((clause[0], clause[1]))
        else:
            raise ValueError("2-SAT solver received a wider clause")

    seen = [False] * n
    order: list[int] = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [(start, 0)]
        seen[start] = True
        while stack:
            v, i = stack[-1]
            if i < len(graph[v]):
                u = graph[v][i]
                stack[-1] = (v, i + 1)
                if not seen[u]:
                    seen[u] = True
                    stack.append((u, 0))
            else:
                order.append(v)
                stack.pop()

    comp = [-1] * n
    cid = 0
    for start in reversed(order):
        if comp[start] != -1:
            continue
        comp[start] = cid
        stack = [start]
        while stack:
            v = stack.pop()
            for u in rev[v]:
                if comp[u] == -1:
                    comp[u] = cid
                    stack.append(u)
        cid += 1

    assignment = 0
    for v in range(nvars):
        pos, negv = 2 * v, 2 * v + 1
        if comp[pos] == comp[negv]:
            return TractableResult(
                "UNSAT", None,
                {"reason": "literal_and_negation_same_scc", "variable": v + 1, "scc": comp[pos]},
            )
        if comp[pos] > comp[negv]:
            assignment |= 1 << v
    return TractableResult("SAT", assignment, {"scc_count": cid, "compiled_clauses": len(normalized)})


def solve_horn(nvars: int, clauses: list[tuple[int, ...]], dual: bool = False) -> TractableResult:
    # Dual-Horn under x -> not x becomes Horn. Transform literals, solve, then
    # complement the returned assignment.
    if dual:
        transformed = [tuple(-lit for lit in c) for c in clauses]
        result = solve_horn(nvars, transformed, dual=False)
        if result.assignment is not None:
            mask = (1 << nvars) - 1
            result.assignment ^= mask
        result.certificate["dual_transform"] = True
        return result

    bodies: list[list[int]] = []
    heads: list[int | None] = []
    occurrence: list[list[int]] = [[] for _ in range(nvars)]
    remaining: list[int] = []

    for ci, clause in enumerate(clauses):
        positives = [lit for lit in clause if lit > 0]
        if len(positives) > 1:
            raise ValueError("Horn solver received a non-Horn clause")
        body = [abs(lit) - 1 for lit in clause if lit < 0]
        head = positives[0] - 1 if positives else None
        bodies.append(body)
        heads.append(head)
        remaining.append(len(body))
        for v in body:
            occurrence[v].append(ci)

    assignment = 0
    queue: deque[int] = deque()
    trace: list[tuple[int, int]] = []
    for ci, rem in enumerate(remaining):
        if rem == 0:
            head = heads[ci]
            if head is None:
                return TractableResult("UNSAT", None, {"reason": "empty_horn_clause", "clause": ci})
            if not ((assignment >> head) & 1):
                assignment |= 1 << head
                queue.append(head)
                trace.append((head, ci))

    while queue:
        v = queue.popleft()
        for ci in occurrence[v]:
            remaining[ci] -= 1
            if remaining[ci] == 0:
                head = heads[ci]
                if head is None:
                    return TractableResult(
                        "UNSAT", None,
                        {"reason": "forward_chain_conflict", "clause": ci, "trace": trace},
                    )
                if not ((assignment >> head) & 1):
                    assignment |= 1 << head
                    queue.append(head)
                    trace.append((head, ci))

    return TractableResult(
        "SAT", assignment,
        {"derived_true_variables": assignment.bit_count(), "trace_length": len(trace)},
    )
