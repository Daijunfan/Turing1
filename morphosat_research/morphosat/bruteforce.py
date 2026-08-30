from __future__ import annotations

from .cnf import CNF


def solve_bruteforce(cnf: CNF) -> tuple[str, int | None]:
    for assignment in range(1 << cnf.nvars):
        if cnf.is_satisfied(assignment):
            return "SAT", assignment
    return "UNSAT", None
