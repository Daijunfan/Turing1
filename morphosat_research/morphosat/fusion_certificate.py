from __future__ import annotations

from .affine import LocalEquation, affine_relation_equations, map_equation_to_global, parity, solve_affine
from .certificate import cnf_sha256
from .cnf import CNF
from .fusion import MacroRelation, _project_join, fuse_until_tractable
from .relations import discover_scope_blocks


def build_fusion_affine_unsat_certificate(
    cnf: CNF,
    initial_max_arity: int = 8,
    max_macro_arity: int = 8,
) -> dict[str, object]:
    blocks = discover_scope_blocks(cnf, initial_max_arity)
    fusion = fuse_until_tractable(
        blocks, max_macro_arity=max_macro_arity, stop_preference=("affine",)
    )
    if "affine" not in fusion.common_classes:
        raise ValueError("fusion did not expose a common affine language")

    equations: list[LocalEquation] = []
    descriptors: list[tuple[int, int, int]] = []
    for rel in fusion.relations:
        ok, local_eqs = affine_relation_equations(rel.allowed, rel.arity)
        if not ok:
            raise ValueError(f"final relation {rel.relation_id} is not affine")
        for coeff, rhs in local_eqs:
            gcoeff, grhs = map_equation_to_global(coeff, rhs, rel.scope)
            equations.append(LocalEquation(rel.relation_id, coeff, grhs, gcoeff, rel.scope))
            descriptors.append((rel.relation_id, coeff, rhs))

    solved = solve_affine(equations, cnf.nvars)
    if solved.status != "UNSAT" or solved.contradiction_provenance is None:
        raise ValueError("projected affine formula is not UNSAT")

    selected: list[dict[str, int]] = []
    p = solved.contradiction_provenance
    idx = 0
    while p:
        if p & 1:
            rid, coeff, rhs = descriptors[idx]
            selected.append({"relation_id": rid, "local_coeff": coeff, "rhs": rhs})
        idx += 1
        p >>= 1

    return {
        "format": "MORPH-FUSION-AFFINE-UNSAT-v1",
        "cnf_sha256": cnf_sha256(cnf),
        "nvars": cnf.nvars,
        "nclauses": len(cnf.clauses),
        "initial_max_arity": initial_max_arity,
        "max_macro_arity": max_macro_arity,
        "initial_relation_count": len(blocks),
        "fusion_steps": [
            {
                "new_relation_id": s.new_relation_id,
                "parent_ids": list(s.parent_ids),
                "eliminated_variable": s.eliminated_variable,
                "new_scope": list(s.new_scope),
                "new_allowed": list(s.new_allowed),
                "depth": s.depth,
            }
            for s in fusion.steps
        ],
        "final_relation_ids": sorted(rel.relation_id for rel in fusion.relations),
        "selected_equations": selected,
        "metadata": {
            "fusion_depth": fusion.max_depth,
            "selected_equation_count": len(selected),
            "exact_steps_verified_during_generation": fusion.exact_steps_verified,
        },
    }


def verify_fusion_affine_unsat_certificate(
    cnf: CNF,
    certificate: dict[str, object],
) -> tuple[bool, dict[str, object]]:
    if certificate.get("format") != "MORPH-FUSION-AFFINE-UNSAT-v1":
        return False, {"error": "unsupported format"}
    if certificate.get("cnf_sha256") != cnf_sha256(cnf):
        return False, {"error": "CNF hash mismatch"}

    initial_max_arity = int(certificate.get("initial_max_arity", 8))
    blocks = discover_scope_blocks(cnf, initial_max_arity)
    if int(certificate.get("initial_relation_count", -1)) != len(blocks):
        return False, {"error": "initial relation count mismatch"}

    active: dict[int, MacroRelation] = {}
    history: dict[int, MacroRelation] = {}
    for rid, block in enumerate(blocks):
        rel = MacroRelation(
            relation_id=rid,
            scope=block.scope,
            allowed=block.allowed,
            parents=tuple(),
            eliminated_variable=None,
            depth=0,
            original_blocks=frozenset({block.block_id}),
        )
        active[rid] = rel
        history[rid] = rel

    verified_steps = 0
    raw_steps = certificate.get("fusion_steps", [])
    if not isinstance(raw_steps, list):
        return False, {"error": "malformed fusion_steps"}
    for raw in raw_steps:
        if not isinstance(raw, dict):
            return False, {"error": "malformed fusion step"}
        rid = int(raw["new_relation_id"])
        parent_ids = tuple(int(x) for x in raw["parent_ids"])
        eliminate = int(raw["eliminated_variable"])
        if rid in history:
            return False, {"error": f"duplicate relation id {rid}"}
        if not parent_ids or any(pid not in active for pid in parent_ids):
            return False, {"error": f"inactive or missing parent at relation {rid}"}
        parents = [active[pid] for pid in parent_ids]
        scope, allowed = _project_join(parents, eliminate)
        claimed_scope = tuple(int(x) for x in raw["new_scope"])
        claimed_allowed = tuple(int(x) for x in raw["new_allowed"])
        if scope != claimed_scope or allowed != claimed_allowed:
            return False, {"error": f"invalid exact fusion at relation {rid}"}
        depth = max(p.depth for p in parents) + 1
        if int(raw.get("depth", depth)) != depth:
            return False, {"error": f"invalid fusion depth at relation {rid}"}
        rel = MacroRelation(
            relation_id=rid,
            scope=scope,
            allowed=allowed,
            parents=parent_ids,
            eliminated_variable=eliminate,
            depth=depth,
            original_blocks=frozenset().union(*(p.original_blocks for p in parents)),
        )
        for pid in parent_ids:
            del active[pid]
        if len(allowed) != (1 << len(scope)) or not allowed:
            active[rid] = rel
        history[rid] = rel
        verified_steps += 1

    claimed_final = sorted(int(x) for x in certificate.get("final_relation_ids", []))
    if sorted(active) != claimed_final:
        return False, {"error": "final active relation set mismatch"}

    coeff_xor = 0
    rhs_xor = 0
    verified_equations = 0
    selected = certificate.get("selected_equations", [])
    if not isinstance(selected, list) or not selected:
        return False, {"error": "missing selected equations"}
    for raw in selected:
        if not isinstance(raw, dict):
            return False, {"error": "malformed selected equation"}
        rid = int(raw["relation_id"])
        coeff = int(raw["local_coeff"])
        rhs = int(raw["rhs"])
        if rid not in active:
            return False, {"error": f"equation relation {rid} is not final-active"}
        rel = active[rid]
        if coeff < 0 or coeff >= (1 << rel.arity) or rhs not in (0, 1):
            return False, {"error": f"malformed equation for relation {rid}"}
        # Independent semantic entailment check over the full bounded truth table.
        if any(parity(coeff & t) != rhs for t in rel.allowed):
            return False, {"error": f"non-entailed equation for relation {rid}"}
        gcoeff, grhs = map_equation_to_global(coeff, rhs, rel.scope)
        coeff_xor ^= gcoeff
        rhs_xor ^= grhs
        verified_equations += 1

    ok = coeff_xor == 0 and rhs_xor == 1
    return ok, {
        "cnf_hash_verified": True,
        "initial_relations_rederived": len(blocks),
        "exact_fusion_steps_replayed": verified_steps,
        "final_relations": len(active),
        "entailed_equations_verified": verified_equations,
        "final_coefficient_weight": coeff_xor.bit_count(),
        "final_rhs": rhs_xor,
    }
