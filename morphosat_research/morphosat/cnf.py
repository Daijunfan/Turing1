from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(slots=True)
class CNF:
    nvars: int
    clauses: list[tuple[int, ...]]

    def __post_init__(self) -> None:
        normalized: list[tuple[int, ...]] = []
        for clause in self.clauses:
            lits = tuple(int(x) for x in clause)
            if not lits:
                normalized.append(lits)
                continue
            if any(x == 0 or abs(x) > self.nvars for x in lits):
                raise ValueError(f"invalid literal in clause {lits}")
            normalized.append(lits)
        self.clauses = normalized

    @classmethod
    def from_dimacs(cls, path: str | Path) -> "CNF":
        nvars = 0
        expected = None
        clauses: list[tuple[int, ...]] = []
        current: list[int] = []
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("c"):
                    continue
                if line.startswith("p"):
                    parts = line.split()
                    if len(parts) != 4 or parts[1].lower() != "cnf":
                        raise ValueError(f"bad DIMACS header: {line}")
                    nvars = int(parts[2])
                    expected = int(parts[3])
                    continue
                for token in line.split():
                    lit = int(token)
                    if lit == 0:
                        clauses.append(tuple(current))
                        current.clear()
                    else:
                        current.append(lit)
        if current:
            raise ValueError("unterminated DIMACS clause")
        if expected is not None and expected != len(clauses):
            raise ValueError(f"header says {expected} clauses, parsed {len(clauses)}")
        if nvars == 0 and clauses:
            nvars = max(abs(lit) for c in clauses for lit in c)
        return cls(nvars=nvars, clauses=clauses)

    def to_dimacs(self, path: str | Path, comments: Iterable[str] = ()) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for comment in comments:
                f.write(f"c {comment}\n")
            f.write(f"p cnf {self.nvars} {len(self.clauses)}\n")
            for clause in self.clauses:
                f.write(" ".join(map(str, clause)) + " 0\n")

    def is_satisfied(self, assignment: Sequence[bool] | int) -> bool:
        if isinstance(assignment, int):
            def value(var: int) -> bool:
                return bool((assignment >> (var - 1)) & 1)
        else:
            if len(assignment) <= self.nvars:
                raise ValueError("assignment must be 1-indexed or include nvars values")
            def value(var: int) -> bool:
                return bool(assignment[var])
        for clause in self.clauses:
            if not any(value(abs(lit)) == (lit > 0) for lit in clause):
                return False
        return True

    def first_unsatisfied_clause(self, assignment: Sequence[bool] | int) -> int | None:
        if isinstance(assignment, int):
            def value(var: int) -> bool:
                return bool((assignment >> (var - 1)) & 1)
        else:
            def value(var: int) -> bool:
                return bool(assignment[var])
        for i, clause in enumerate(self.clauses):
            if not any(value(abs(lit)) == (lit > 0) for lit in clause):
                return i
        return None

    def stats(self) -> dict[str, float | int]:
        widths = [len(c) for c in self.clauses]
        return {
            "nvars": self.nvars,
            "nclauses": len(self.clauses),
            "min_width": min(widths, default=0),
            "max_width": max(widths, default=0),
            "mean_width": (sum(widths) / len(widths)) if widths else 0.0,
        }
