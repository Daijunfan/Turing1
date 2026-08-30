from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable

from .cnf import CNF


@dataclass(slots=True)
class RelationBlock:
    block_id: int
    scope: tuple[int, ...]
    clause_ids: tuple[int, ...]
    clauses: tuple[tuple[int, ...], ...]
    allowed: tuple[int, ...]
    classes: frozenset[str] = field(default_factory=frozenset)
    representations: dict[str, object] = field(default_factory=dict)

    @property
    def arity(self) -> int:
        return len(self.scope)

    @property
    def mask(self) -> int:
        out = 0
        for t in self.allowed:
            out |= 1 << t
        return out

    def contains(self, tuple_bits: int) -> bool:
        return tuple_bits in self.allowed


def _literal_value(lit: int, scope_pos: dict[int, int], tuple_bits: int) -> bool:
    bit = bool((tuple_bits >> scope_pos[abs(lit)]) & 1)
    return bit if lit > 0 else not bit


def enumerate_relation(scope: tuple[int, ...], clauses: Iterable[tuple[int, ...]]) -> tuple[int, ...]:
    pos = {v: i for i, v in enumerate(scope)}
    local_clauses = tuple(clauses)
    allowed: list[int] = []
    for t in range(1 << len(scope)):
        ok = True
        for clause in local_clauses:
            if not any(_literal_value(lit, pos, t) for lit in clause):
                ok = False
                break
        if ok:
            allowed.append(t)
    return tuple(allowed)


def discover_scope_blocks(cnf: CNF, max_arity: int = 8) -> list[RelationBlock]:
    """Partition a CNF exactly by clause variable scope.

    The transformation is lossless: every clause belongs to one block, and each
    block is represented by its exact truth-table relation. Blocks wider than
    max_arity are rejected rather than approximated.
    """
    grouped: dict[tuple[int, ...], list[tuple[int, tuple[int, ...]]]] = {}
    for cid, clause in enumerate(cnf.clauses):
        scope = tuple(sorted({abs(lit) for lit in clause}))
        if len(scope) > max_arity:
            raise ValueError(
                f"clause scope of arity {len(scope)} exceeds max_arity={max_arity}; "
                "no approximation is permitted"
            )
        grouped.setdefault(scope, []).append((cid, clause))

    blocks: list[RelationBlock] = []
    for bid, (scope, entries) in enumerate(sorted(grouped.items())):
        clauses = tuple(c for _, c in entries)
        allowed = enumerate_relation(scope, clauses)
        blocks.append(
            RelationBlock(
                block_id=bid,
                scope=scope,
                clause_ids=tuple(cid for cid, _ in entries),
                clauses=clauses,
                allowed=allowed,
            )
        )
    return blocks


def relation_satisfies_clause(tuple_bits: int, clause: tuple[int, ...], arity: int) -> bool:
    del arity
    for lit in clause:
        idx = abs(lit) - 1
        value = bool((tuple_bits >> idx) & 1)
        if value == (lit > 0):
            return True
    return False


def all_assignments_satisfying(arity: int, clauses: Iterable[tuple[int, ...]]) -> tuple[int, ...]:
    clauses = tuple(clauses)
    return tuple(
        t for t in range(1 << arity)
        if all(relation_satisfies_clause(t, c, arity) for c in clauses)
    )


def entailed_unit_binary_clauses(allowed: tuple[int, ...], arity: int) -> list[tuple[int, ...]]:
    clauses: list[tuple[int, ...]] = []
    literals = [s * (i + 1) for i in range(arity) for s in (1, -1)]
    for lit in literals:
        c = (lit,)
        if all(relation_satisfies_clause(t, c, arity) for t in allowed):
            clauses.append(c)
    for a, b in combinations(literals, 2):
        if abs(a) == abs(b):
            continue
        c = (a, b)
        if all(relation_satisfies_clause(t, c, arity) for t in allowed):
            clauses.append(c)
    return clauses


def entailed_horn_clauses(allowed: tuple[int, ...], arity: int, dual: bool = False) -> list[tuple[int, ...]]:
    clauses: list[tuple[int, ...]] = []
    # Enumerate every clause with at most one positive literal (Horn). For
    # dual-Horn, complement all literals after generation.
    for neg_mask in range(1 << arity):
        base = tuple(-(i + 1) for i in range(arity) if (neg_mask >> i) & 1)
        candidates = [base]
        for p in range(arity):
            if not ((neg_mask >> p) & 1):
                candidates.append(base + (p + 1,))
        for clause in candidates:
            if not clause:
                continue
            out = tuple(-lit for lit in clause) if dual else clause
            if all(relation_satisfies_clause(t, out, arity) for t in allowed):
                clauses.append(out)
    return clauses


def map_local_clause(clause: tuple[int, ...], scope: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(scope[abs(lit) - 1] if lit > 0 else -scope[abs(lit) - 1] for lit in clause)
