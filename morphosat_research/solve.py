#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from morphosat.cnf import CNF
from morphosat.fusion_solver import MorphFusionSolver
from morphosat.solver import MorphSolver, SolveResult


def solve(cnf: CNF, args: argparse.Namespace) -> SolveResult:
    if args.mode == "direct":
        return MorphSolver(max_arity=args.max_arity).solve(cnf)
    if args.mode == "fusion":
        return MorphFusionSolver(
            initial_max_arity=args.max_arity,
            max_macro_arity=args.max_macro_arity,
            adaptive=not args.no_adaptive,
        ).solve(cnf)

    direct = MorphSolver(max_arity=args.max_arity).solve(cnf)
    if direct.status != "UNKNOWN":
        return direct
    return MorphFusionSolver(
        initial_max_arity=args.max_arity,
        max_macro_arity=args.max_macro_arity,
        adaptive=not args.no_adaptive,
    ).solve(cnf)


def write_model(path: Path, assignment: int, nvars: int) -> None:
    true_vars = [v for v in range(1, nvars + 1) if (assignment >> (v - 1)) & 1]
    payload = {
        "format": "MORPH-SAT-MODEL-v1",
        "nvars": nvars,
        "true_variables": true_vars,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MORPH-SAT endogenous constraint-language compiler"
    )
    parser.add_argument("cnf", type=Path)
    parser.add_argument(
        "--mode", choices=("auto", "direct", "fusion"), default="auto",
        help="auto tries direct language discovery, then exact recursive fusion",
    )
    parser.add_argument("--max-arity", type=int, default=8)
    parser.add_argument("--max-macro-arity", type=int, default=8)
    parser.add_argument("--no-adaptive", action="store_true")
    parser.add_argument("--model-out", type=Path)
    args = parser.parse_args()

    cnf = CNF.from_dimacs(args.cnf)
    result = solve(cnf, args)
    if args.model_out is not None:
        if result.status != "SAT" or result.assignment is None:
            raise SystemExit("--model-out requires a verified SAT result")
        write_model(args.model_out, result.assignment, cnf.nvars)

    print(json.dumps({
        "status": result.status,
        "method": result.method,
        "verified": result.verified,
        "elapsed_seconds": result.elapsed_seconds,
        "metrics": result.metrics,
        "certificate": result.certificate,
        "model_file": str(args.model_out) if args.model_out is not None else None,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
