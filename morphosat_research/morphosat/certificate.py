from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .affine import (
    LocalEquation,
    affine_relation_equations,
    map_equation_to_global,
    parity,
    solve_affine,
)
from .cnf import CNF
from .relations import discover_scope_blocks


def canonical_cnf_bytes(cnf: CNF) -> bytes:
    lines = [f"p cnf {cnf.nvars} {len(cnf.clauses)}\n"]
    lines.extend(" ".join(map(str, c)) + " 0\n" for c in cnf.clauses)
    return "".join(lines).encode("ascii")


def cnf_sha256(cnf: CNF) -> str:
    return hashlib.sha256(canonical_cnf_bytes(cnf)).hexdigest()


def build_affine_unsat_certificate(cnf: CNF, max_arity: int = 8) -> dict[str, object]:
    blocks = discover_scope_blocks(cnf, max_arity=max_arity)
    equations: list[LocalEquation] = []
    local_equations: list[tuple[int, int, int]] = []
    for block in blocks:
        ok, eqs = affine_relation_equations(block.allowed, block.arity)
        if not ok:
            raise ValueError(f"block {block.block_id} is not affine")
        for coeff, rhs in eqs:
            gcoeff, grhs = map_equation_to_global(coeff, rhs, block.scope)
            equations.append(LocalEquation(block.block_id, coeff, grhs, gcoeff, block.scope))
            local_equations.append((block.block_id, coeff, rhs))
    result = solve_affine(equations, cnf.nvars)
    if result.status != "UNSAT" or result.contradiction_provenance is None:
        raise ValueError("formula is not certified affine-UNSAT")
    selected: list[dict[str, int]] = []
    p = result.contradiction_provenance
    idx = 0
    while p:
        if p & 1:
            block_id, coeff, rhs = local_equations[idx]
            selected.append({"block_id": block_id, "local_coeff": coeff, "rhs": rhs})
        idx += 1
        p >>= 1
    return {
        "format": "MORPH-AFFINE-UNSAT-v1",
        "cnf_sha256": cnf_sha256(cnf),
        "nvars": cnf.nvars,
        "nclauses": len(cnf.clauses),
        "max_arity": max_arity,
        "selected_equations": selected,
    }


def verify_affine_unsat_certificate(cnf: CNF, certificate: dict[str, object]) -> tuple[bool, dict[str, object]]:
    if certificate.get("format") != "MORPH-AFFINE-UNSAT-v1":
        return False, {"error": "unsupported format"}
    if certificate.get("cnf_sha256") != cnf_sha256(cnf):
        return False, {"error": "CNF hash mismatch"}
    max_arity = int(certificate.get("max_arity", 8))
    blocks = discover_scope_blocks(cnf, max_arity=max_arity)
    coeff_xor = 0
    rhs_xor = 0
    verified_local = 0
    for item in certificate.get("selected_equations", []):
        if not isinstance(item, dict):
            return False, {"error": "malformed equation entry"}
        bid = int(item["block_id"])
        coeff = int(item["local_coeff"])
        rhs = int(item["rhs"])
        if bid < 0 or bid >= len(blocks):
            return False, {"error": f"invalid block id {bid}"}
        block = blocks[bid]
        # Independent semantic check: every tuple satisfying the original CNF
        # block must satisfy the claimed parity equation.
        if any(parity(coeff & t) != rhs for t in block.allowed):
            return False, {"error": f"invalid local equation in block {bid}"}
        global_coeff, global_rhs = map_equation_to_global(coeff, rhs, block.scope)
        coeff_xor ^= global_coeff
        rhs_xor ^= global_rhs
        verified_local += 1
    ok = coeff_xor == 0 and rhs_xor == 1
    return ok, {
        "verified_local_equations": verified_local,
        "final_coefficient_weight": coeff_xor.bit_count(),
        "final_rhs": rhs_xor,
        "cnf_hash_verified": True,
    }


def write_certificate(path: str | Path, certificate: dict[str, object]) -> None:
    Path(path).write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")


def read_certificate(path: str | Path) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
