"""MORPH-SAT: endogenous Boolean constraint-language discovery."""

from .cnf import CNF
from .solver import MorphSolver, SolveResult

__all__ = ["CNF", "MorphSolver", "SolveResult"]
