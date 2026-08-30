from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True, frozen=True)
class LocalEquation:
    block_id: int
    local_coeff: int
    rhs: int
    global_coeff: int
    scope: tuple[int, ...]


@dataclass(slots=True)
class DerivedRow:
    bits: int  # coefficients in [0,nvars), RHS at nvars
    provenance: int
    depth: int
    births: int


@dataclass(slots=True)
class AffineSolveResult:
    status: str
    assignment: int | None
    contradiction_provenance: int | None
    basis_rows: dict[int, DerivedRow]
    xor_births: int
    max_depth: int
    max_support: int


def parity(x: int) -> int:
    return x.bit_count() & 1


def gf2_insert_basis(basis: dict[int, int], value: int) -> bool:
    x = value
    while x:
        p = x.bit_length() - 1
        if p in basis:
            x ^= basis[p]
        else:
            basis[p] = x
            return True
    return False


def gf2_rank(values: Iterable[int]) -> int:
    basis: dict[int, int] = {}
    for value in values:
        gf2_insert_basis(basis, value)
    return len(basis)


def affine_relation_equations(allowed: tuple[int, ...], arity: int) -> tuple[bool, list[tuple[int, int]]]:
    """Recognize an affine Boolean relation and return a basis of equations.

    The method is semantic, not syntax specific. A nonempty relation R is affine
    iff R-r0 is a vector space. We build its span and compare cardinalities,
    then derive an orthogonal-complement basis by exhaustive search over the
    bounded local arity.
    """
    if not allowed:
        return True, [(0, 1)]
    r0 = allowed[0]
    differences = [t ^ r0 for t in allowed]
    span_basis: dict[int, int] = {}
    for d in differences:
        gf2_insert_basis(span_basis, d)
    if len(allowed) != (1 << len(span_basis)):
        return False, []

    orth_basis: dict[int, int] = {}
    equations: list[tuple[int, int]] = []
    for a in range(1, 1 << arity):
        if all(parity(a & v) == 0 for v in span_basis.values()):
            before = len(orth_basis)
            if gf2_insert_basis(orth_basis, a):
                equations.append((a, parity(a & r0)))
            if len(orth_basis) == arity - len(span_basis):
                break
    return True, equations


def map_equation_to_global(local_coeff: int, rhs: int, scope: tuple[int, ...]) -> int:
    global_coeff = 0
    for i, var in enumerate(scope):
        if (local_coeff >> i) & 1:
            global_coeff |= 1 << (var - 1)
    return global_coeff, rhs


def solve_affine(equations: list[LocalEquation], nvars: int) -> AffineSolveResult:
    rhs_bit = 1 << nvars
    basis: dict[int, DerivedRow] = {}
    xor_births = 0
    max_depth = 0
    max_support = 0

    for eq_id, eq in enumerate(equations):
        row = DerivedRow(
            bits=eq.global_coeff | (rhs_bit if eq.rhs else 0),
            provenance=1 << eq_id,
            depth=0,
            births=0,
        )
        while True:
            coeff = row.bits & (rhs_bit - 1)
            max_support = max(max_support, coeff.bit_count())
            if coeff == 0:
                if row.bits & rhs_bit:
                    return AffineSolveResult(
                        status="UNSAT",
                        assignment=None,
                        contradiction_provenance=row.provenance,
                        basis_rows=basis,
                        xor_births=xor_births,
                        max_depth=max_depth,
                        max_support=max_support,
                    )
                break
            pivot = coeff.bit_length() - 1
            other = basis.get(pivot)
            if other is None:
                basis[pivot] = row
                max_depth = max(max_depth, row.depth)
                break
            row = DerivedRow(
                bits=row.bits ^ other.bits,
                provenance=row.provenance ^ other.provenance,
                depth=max(row.depth, other.depth) + 1,
                births=row.births + other.births + 1,
            )
            xor_births += 1
            max_depth = max(max_depth, row.depth)

    assignment = 0
    # Each pivot is the highest coefficient in its row. Solving from low to
    # high means every lower-index variable on the row is already assigned.
    for pivot in sorted(basis):
        row = basis[pivot].bits
        coeff = row & (rhs_bit - 1)
        rhs = 1 if (row & rhs_bit) else 0
        lower = coeff & ~(1 << pivot)
        value = rhs ^ parity(lower & assignment)
        if value:
            assignment |= 1 << pivot

    return AffineSolveResult(
        status="SAT",
        assignment=assignment,
        contradiction_provenance=None,
        basis_rows=basis,
        xor_births=xor_births,
        max_depth=max_depth,
        max_support=max_support,
    )


def verify_affine_relation(allowed: tuple[int, ...], arity: int, equations: list[tuple[int, int]]) -> bool:
    predicted = []
    for t in range(1 << arity):
        if all(parity(a & t) == b for a, b in equations):
            predicted.append(t)
    return tuple(predicted) == tuple(allowed)


def verify_unsat_certificate(
    equations: list[LocalEquation], provenance: int, nvars: int
) -> tuple[bool, dict[str, int]]:
    coeff = 0
    rhs = 0
    count = 0
    p = provenance
    idx = 0
    while p:
        if p & 1:
            eq = equations[idx]
            coeff ^= eq.global_coeff
            rhs ^= eq.rhs
            count += 1
        idx += 1
        p >>= 1
    return coeff == 0 and rhs == 1, {
        "certificate_equations": count,
        "residual_coeff_weight": coeff.bit_count(),
        "residual_rhs": rhs,
        "nvars": nvars,
    }
