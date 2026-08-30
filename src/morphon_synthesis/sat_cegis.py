from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .synthesis import check_morphon, clause_universe


def _z3_binary(root: Path) -> Path:
    configured = os.environ.get("MORPHSAT_Z3_BIN")
    if configured:
        return Path(configured)
    local = root / "morphosat_research" / ".audit_tools" / "bin" / "z3"
    if local.exists():
        return local
    return Path("z3")


def sat_cegis_search(
    root: Path,
    nvars: int,
    clause_count: int,
    target_class: str,
    maximum_candidates: int,
    model: str = "LCA",
) -> tuple[tuple[tuple[int, ...], ...] | None, dict[str, object]]:
    """Use Z3 for candidate-set synthesis and an exact checker as the CEGIS oracle.

    The SMT layer enforces size and variable coverage. Clone-ascent semantics are
    deliberately checked outside Z3; every rejected model is blocked exactly.
    """
    universe = clause_universe(nvars)
    declarations = [f"(declare-fun c{index} () Bool)" for index in range(len(universe))]
    cardinality = "(+ " + " ".join(f"(ite c{index} 1 0)" for index in range(len(universe))) + ")"
    assertions = [f"(assert (= {cardinality} {clause_count}))"]
    for variable in range(1, nvars + 1):
        choices = [f"c{index}" for index, clause in enumerate(universe) if variable in {abs(lit) for lit in clause}]
        assertions.append(f"(assert (or {' '.join(choices)}))")
    blocks: list[str] = []
    z3 = _z3_binary(root)
    for iteration in range(maximum_candidates):
        script = "\n".join(declarations + assertions + blocks + ["(check-sat)", "(get-model)"])
        completed = subprocess.run(
            [str(z3), "-in"], input=script, text=True, capture_output=True, timeout=30
        )
        if not completed.stdout.startswith("sat"):
            return None, {
                "method": "SMT_CEGIS", "checked": iteration, "solver_status": completed.stdout.splitlines()[:1],
            }
        true_indices = {
            int(match.group(1))
            for match in re.finditer(r"\(define-fun c(\d+) \(\) Bool\s+true\)", completed.stdout)
        }
        candidate = tuple(universe[index] for index in sorted(true_indices))
        if len(candidate) != clause_count:
            return None, {"method": "SMT_CEGIS", "checked": iteration, "error": "model parse mismatch"}
        if check_morphon(candidate, target_class, model, robustness=True).valid:
            return candidate, {"method": "SMT_CEGIS", "checked": iteration + 1}
        literals = [f"c{index}" if index not in true_indices else f"(not c{index})" for index in range(len(universe))]
        blocks.append(f"(assert (or {' '.join(literals)}))")
    return None, {"method": "SMT_CEGIS", "checked": maximum_candidates, "exhausted_limit": True}

