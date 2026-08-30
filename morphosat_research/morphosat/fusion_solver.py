from __future__ import annotations

from time import perf_counter

from .affine import (
    LocalEquation,
    map_equation_to_global,
    solve_affine,
    verify_affine_relation,
    verify_unsat_certificate,
)
from .cnf import CNF
from .fusion import final_relations_hold, fuse_until_tractable, reconstruct_eliminated_assignment
from .relations import all_assignments_satisfying, discover_scope_blocks, map_local_clause
from .schaefer import classify_blocks
from .solver import SolveResult
from .tractable import solve_2sat, solve_horn


class MorphFusionSolver:
    """Exact relation fusion followed by semantic tractable-language compilation."""

    def __init__(
        self,
        initial_max_arity: int = 8,
        max_macro_arity: int = 8,
        adaptive: bool = True,
        tie_seeds: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7),
        extra_arity: int = 2,
    ) -> None:
        self.initial_max_arity = initial_max_arity
        self.max_macro_arity = max_macro_arity
        self.adaptive = adaptive
        self.tie_seeds = tie_seeds if adaptive else (0,)
        self.extra_arity = extra_arity if adaptive else 0

    @staticmethod
    def _verify_representation(rel, kind: str) -> bool:
        if kind == "affine":
            return verify_affine_relation(rel.allowed, rel.arity, list(rel.representations[kind]))
        clauses = list(rel.representations[kind])
        return all_assignments_satisfying(rel.arity, clauses) == rel.allowed

    @staticmethod
    def _reconstruct_and_check(cnf: CNF, fusion, projected: int | None) -> tuple[int | None, bool, bool]:
        projected_ok = projected is not None and final_relations_hold(fusion, projected)
        assignment = (
            reconstruct_eliminated_assignment(fusion, projected, cnf.nvars)
            if projected is not None and projected_ok else None
        )
        verified = bool(assignment is not None and cnf.is_satisfied(assignment))
        return assignment, projected_ok, verified

    def solve(self, cnf: CNF) -> SolveResult:
        start = perf_counter()
        blocks = discover_scope_blocks(cnf, self.initial_max_arity)
        initial_summary = classify_blocks(blocks)
        attempts: list[dict[str, object]] = []
        fusion = None
        arities = [self.max_macro_arity]
        if self.extra_arity > 0:
            arities.append(self.max_macro_arity + self.extra_arity)
        for arity in arities:
            for tie_seed in self.tie_seeds:
                candidate = fuse_until_tractable(
                    blocks, max_macro_arity=arity, tie_seed=tie_seed
                )
                attempts.append({
                    "max_macro_arity": arity,
                    "tie_seed": tie_seed,
                    "steps": len(candidate.steps),
                    "remaining_relations": len(candidate.relations),
                    "common_classes": sorted(candidate.common_classes),
                    "seconds": candidate.elapsed_seconds,
                })
                if fusion is None or len(candidate.relations) < len(fusion.relations):
                    fusion = candidate
                if candidate.common_classes or not candidate.relations or any(not r.allowed for r in candidate.relations):
                    fusion = candidate
                    break
            if fusion is not None and (fusion.common_classes or not fusion.relations or any(not r.allowed for r in fusion.relations)):
                break
        assert fusion is not None
        selected_attempt = attempts[-1] if attempts else {}
        metrics: dict[str, object] = {
            "nvars": cnf.nvars,
            "nclauses": len(cnf.clauses),
            "initial_relation_blocks": len(blocks),
            "initial_common_classes": sorted(initial_summary.common_classes),
            "fusion_steps": len(fusion.steps),
            "fusion_depth": fusion.max_depth,
            "remaining_macro_relations": len(fusion.relations),
            "emergent_common_classes": sorted(fusion.common_classes),
            "fusion_seconds": fusion.elapsed_seconds,
            "fusion_exactly_verified": fusion.exact_steps_verified,
            "fusion_attempt_count": len(attempts),
            "selected_max_macro_arity": selected_attempt.get("max_macro_arity"),
            "selected_tie_seed": selected_attempt.get("tie_seed"),
            "fusion_attempts": attempts,
            "max_relation_arity": max((relation.arity for relation in fusion.all_relations.values()), default=0),
            "relation_table_total_size": sum(len(relation.allowed) for relation in fusion.all_relations.values()),
        }

        if not fusion.relations:
            assignment = reconstruct_eliminated_assignment(fusion, 0, cnf.nvars)
            verified = assignment is not None and cnf.is_satisfied(assignment)
            return SolveResult(
                "SAT" if verified else "UNKNOWN", "MORPH-FUSION-EMPTY", assignment, verified,
                perf_counter() - start, metrics, {"model_satisfies_original_cnf": verified},
            )

        if any(len(r.allowed) == 0 for r in fusion.relations):
            return SolveResult(
                "UNSAT", "MORPH-FUSION-EMPTY-RELATION", None,
                fusion.exact_steps_verified, perf_counter() - start, metrics,
                {"empty_macro_relation": True, "fusion_dag_verified": fusion.exact_steps_verified},
            )

        # Prefer the strongest algebraic structure when several polymorphisms emerge.
        if "affine" in fusion.common_classes:
            equations: list[LocalEquation] = []
            local_ok = True
            for ridx, rel in enumerate(fusion.relations):
                eqs = list(rel.representations["affine"])
                local_ok &= self._verify_representation(rel, "affine")
                for coeff, rhs in eqs:
                    gcoeff, grhs = map_equation_to_global(coeff, rhs, rel.scope)
                    equations.append(LocalEquation(ridx, coeff, grhs, gcoeff, rel.scope))
            result = solve_affine(equations, cnf.nvars)
            metrics.update({
                "polymorphism": "minority/xor",
                "macro_equations": len(equations),
                "equation_births": result.xor_births,
                "equation_depth": result.max_depth,
            })
            certificate: dict[str, object] = {
                "fusion_dag_verified": fusion.exact_steps_verified,
                "macro_relation_equivalence_verified": local_ok,
            }
            if result.status == "UNSAT":
                assert result.contradiction_provenance is not None
                ok, detail = verify_unsat_certificate(equations, result.contradiction_provenance, cnf.nvars)
                certificate.update(detail)
                certificate["macro_xor_certificate_verified"] = ok
                verified = fusion.exact_steps_verified and local_ok and ok
                assignment = None
            else:
                assignment, projected_ok, model_ok = self._reconstruct_and_check(cnf, fusion, result.assignment)
                certificate["projected_model_satisfies_macro_relations"] = projected_ok
                certificate["model_satisfies_original_cnf"] = model_ok
                verified = fusion.exact_steps_verified and local_ok and model_ok
                if not verified:
                    return SolveResult(
                        "UNKNOWN", "MORPH-FUSION-SAT-RECONSTRUCTION-FAILED", None, False,
                        perf_counter() - start, metrics, certificate,
                    )
            return SolveResult(
                result.status, "MORPH-FUSION-AFFINE", assignment, bool(verified),
                perf_counter() - start, metrics, certificate,
            )

        for kind, method in (
            ("bijunctive", "MORPH-FUSION-2SAT"),
            ("horn", "MORPH-FUSION-HORN"),
            ("dual_horn", "MORPH-FUSION-DUAL-HORN"),
        ):
            if kind not in fusion.common_classes:
                continue
            compiled: list[tuple[int, ...]] = []
            local_ok = True
            for rel in fusion.relations:
                local_ok &= self._verify_representation(rel, kind)
                compiled.extend(map_local_clause(c, rel.scope) for c in rel.representations[kind])
            if kind == "bijunctive":
                backend = solve_2sat(cnf.nvars, compiled)
                polymorphism = "majority"
            else:
                backend = solve_horn(cnf.nvars, compiled, dual=(kind == "dual_horn"))
                polymorphism = "and" if kind == "horn" else "or"
            metrics.update({
                "polymorphism": polymorphism,
                "compiled_macro_clauses": len(compiled),
            })
            certificate = {
                "fusion_dag_verified": fusion.exact_steps_verified,
                "macro_relation_equivalence_verified": local_ok,
                "backend_certificate": backend.certificate,
            }
            if backend.status == "SAT":
                assignment, projected_ok, model_ok = self._reconstruct_and_check(cnf, fusion, backend.assignment)
                certificate["projected_model_satisfies_macro_relations"] = projected_ok
                certificate["model_satisfies_original_cnf"] = model_ok
                verified = fusion.exact_steps_verified and local_ok and model_ok
            else:
                assignment = None
                reason = str(backend.certificate.get("reason", ""))
                backend_ok = reason in {
                    "empty_clause", "literal_and_negation_same_scc",
                    "empty_horn_clause", "forward_chain_conflict",
                }
                certificate["backend_unsat_witness_structurally_valid"] = backend_ok
                verified = fusion.exact_steps_verified and local_ok and backend_ok
            return SolveResult(
                backend.status, method, assignment, bool(verified), perf_counter() - start,
                metrics, certificate,
            )

        for kind, bit, method in (
            ("zero_valid", 0, "MORPH-FUSION-ZERO"),
            ("one_valid", 1, "MORPH-FUSION-ONE"),
        ):
            if kind not in fusion.common_classes:
                continue
            projected = 0 if bit == 0 else (1 << cnf.nvars) - 1
            assignment, projected_ok, model_ok = self._reconstruct_and_check(cnf, fusion, projected)
            verified = fusion.exact_steps_verified and projected_ok and model_ok
            return SolveResult(
                "SAT" if verified else "UNKNOWN", method, assignment, bool(verified),
                perf_counter() - start, metrics,
                {
                    "fusion_dag_verified": fusion.exact_steps_verified,
                    "projected_model_satisfies_macro_relations": projected_ok,
                    "model_satisfies_original_cnf": model_ok,
                },
            )

        return SolveResult(
            "UNKNOWN", "MORPH-FUSION-NO-TRACTABLE-EMERGENCE", None, False,
            perf_counter() - start, metrics, {},
        )
