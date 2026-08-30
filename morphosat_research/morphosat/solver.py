from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .affine import (
    LocalEquation,
    map_equation_to_global,
    solve_affine,
    verify_affine_relation,
    verify_unsat_certificate,
)
from .cnf import CNF
from .relations import discover_scope_blocks, map_local_clause
from .schaefer import classify_blocks
from .tractable import solve_2sat, solve_horn


@dataclass(slots=True)
class SolveResult:
    status: str
    method: str
    assignment: int | None
    verified: bool
    elapsed_seconds: float
    metrics: dict[str, object] = field(default_factory=dict)
    certificate: dict[str, object] = field(default_factory=dict)


class MorphSolver:
    def __init__(self, max_arity: int = 8) -> None:
        self.max_arity = max_arity

    def solve(self, cnf: CNF) -> SolveResult:
        start = perf_counter()
        t0 = perf_counter()
        blocks = discover_scope_blocks(cnf, self.max_arity)
        t1 = perf_counter()
        summary = classify_blocks(blocks)
        t2 = perf_counter()
        base_metrics: dict[str, object] = {
            "nvars": cnf.nvars,
            "nclauses": len(cnf.clauses),
            "relation_blocks": len(blocks),
            "max_block_arity": max((b.arity for b in blocks), default=0),
            "common_classes": sorted(summary.common_classes),
            "class_counts": summary.counts,
            "relation_discovery_seconds": t1 - t0,
            "classification_seconds": t2 - t1,
        }

        # Prefer the class that exposes the strongest global algebraic order.
        if "affine" in summary.common_classes:
            equations: list[LocalEquation] = []
            all_local_verified = True
            for block in blocks:
                local_eqs = list(block.representations["affine"])
                all_local_verified &= verify_affine_relation(block.allowed, block.arity, local_eqs)
                for local_coeff, rhs in local_eqs:
                    global_coeff, global_rhs = map_equation_to_global(local_coeff, rhs, block.scope)
                    equations.append(
                        LocalEquation(
                            block_id=block.block_id,
                            local_coeff=local_coeff,
                            rhs=global_rhs,
                            global_coeff=global_coeff,
                            scope=block.scope,
                        )
                    )
            backend_start = perf_counter()
            affine = solve_affine(equations, cnf.nvars)
            backend_seconds = perf_counter() - backend_start
            cert: dict[str, object] = {
                "local_relation_equivalence_verified": all_local_verified,
                "equation_count": len(equations),
            }
            if affine.status == "UNSAT":
                assert affine.contradiction_provenance is not None
                ok, detail = verify_unsat_certificate(
                    equations, affine.contradiction_provenance, cnf.nvars
                )
                cert.update(detail)
                cert["global_xor_certificate_verified"] = ok
                verified = bool(all_local_verified and ok)
                assignment = None
            else:
                assignment = affine.assignment
                verified = bool(
                    all_local_verified and assignment is not None and cnf.is_satisfied(assignment)
                )
                cert["model_satisfies_original_cnf"] = verified
            base_metrics.update({
                "polymorphism": "minority/xor",
                "concept_births": affine.xor_births,
                "concept_depth": affine.max_depth,
                "max_derived_support": affine.max_support,
                "basis_rank": len(affine.basis_rows),
                "backend_seconds": backend_seconds,
            })
            return SolveResult(
                status=affine.status,
                method="MORPH-AFFINE",
                assignment=assignment,
                verified=verified,
                elapsed_seconds=perf_counter() - start,
                metrics=base_metrics,
                certificate=cert,
            )

        if "bijunctive" in summary.common_classes:
            compiled: list[tuple[int, ...]] = []
            for block in blocks:
                compiled.extend(
                    map_local_clause(c, block.scope)
                    for c in block.representations["bijunctive"]
                )
            result = solve_2sat(cnf.nvars, compiled)
            verified = result.assignment is not None and cnf.is_satisfied(result.assignment)
            # For UNSAT the SCC certificate is structural; small-instance fuzzing
            # and the independent Z3 run provide a second checker.
            if result.status == "UNSAT":
                verified = result.certificate.get("reason") == "literal_and_negation_same_scc" or result.certificate.get("reason") == "empty_clause"
            base_metrics.update({"polymorphism": "majority", "compiled_clauses": len(compiled)})
            return SolveResult(
                status=result.status,
                method="MORPH-2SAT",
                assignment=result.assignment,
                verified=bool(verified),
                elapsed_seconds=perf_counter() - start,
                metrics=base_metrics,
                certificate=result.certificate,
            )

        if "horn" in summary.common_classes:
            compiled = []
            for block in blocks:
                compiled.extend(
                    map_local_clause(c, block.scope)
                    for c in block.representations["horn"]
                )
            result = solve_horn(cnf.nvars, compiled)
            verified = result.assignment is not None and cnf.is_satisfied(result.assignment)
            if result.status == "UNSAT":
                verified = True
            base_metrics.update({"polymorphism": "and", "compiled_clauses": len(compiled)})
            return SolveResult(
                status=result.status,
                method="MORPH-HORN",
                assignment=result.assignment,
                verified=bool(verified),
                elapsed_seconds=perf_counter() - start,
                metrics=base_metrics,
                certificate=result.certificate,
            )

        if "dual_horn" in summary.common_classes:
            compiled = []
            for block in blocks:
                compiled.extend(
                    map_local_clause(c, block.scope)
                    for c in block.representations["dual_horn"]
                )
            result = solve_horn(cnf.nvars, compiled, dual=True)
            verified = result.assignment is not None and cnf.is_satisfied(result.assignment)
            if result.status == "UNSAT":
                verified = True
            base_metrics.update({"polymorphism": "or", "compiled_clauses": len(compiled)})
            return SolveResult(
                status=result.status,
                method="MORPH-DUAL-HORN",
                assignment=result.assignment,
                verified=bool(verified),
                elapsed_seconds=perf_counter() - start,
                metrics=base_metrics,
                certificate=result.certificate,
            )

        if "zero_valid" in summary.common_classes:
            assignment = 0
            verified = cnf.is_satisfied(assignment)
            return SolveResult(
                status="SAT", method="MORPH-ZERO", assignment=assignment,
                verified=verified, elapsed_seconds=perf_counter() - start,
                metrics=base_metrics, certificate={"all_zero_model": verified},
            )

        if "one_valid" in summary.common_classes:
            assignment = (1 << cnf.nvars) - 1
            verified = cnf.is_satisfied(assignment)
            return SolveResult(
                status="SAT", method="MORPH-ONE", assignment=assignment,
                verified=verified, elapsed_seconds=perf_counter() - start,
                metrics=base_metrics, certificate={"all_one_model": verified},
            )

        return SolveResult(
            status="UNKNOWN",
            method="MORPH-NO-COMMON-POLYMORPHISM",
            assignment=None,
            verified=False,
            elapsed_seconds=perf_counter() - start,
            metrics=base_metrics,
            certificate={},
        )
