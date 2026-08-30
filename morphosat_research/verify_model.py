#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from morphosat.cnf import CNF


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently check a MORPH-SAT model")
    parser.add_argument("cnf", type=Path)
    parser.add_argument("model", type=Path)
    args = parser.parse_args()

    cnf = CNF.from_dimacs(args.cnf)
    payload = json.loads(args.model.read_text(encoding="utf-8"))
    if payload.get("format") != "MORPH-SAT-MODEL-v1":
        raise SystemExit("unsupported model format")
    if int(payload.get("nvars", -1)) != cnf.nvars:
        raise SystemExit("model variable count does not match CNF")

    assignment = 0
    seen: set[int] = set()
    for raw in payload.get("true_variables", []):
        var = int(raw)
        if not 1 <= var <= cnf.nvars or var in seen:
            raise SystemExit("invalid or duplicate model variable")
        seen.add(var)
        assignment |= 1 << (var - 1)

    bad = cnf.first_unsatisfied_clause(assignment)
    result = {
        "verified": bad is None,
        "cnf_sha256": sha256(args.cnf),
        "nvars": cnf.nvars,
        "nclauses": len(cnf.clauses),
        "true_variables": len(seen),
        "first_unsatisfied_clause": bad,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if bad is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
