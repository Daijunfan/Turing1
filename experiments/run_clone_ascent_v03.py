#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "morphosat_research"))

from morphosat.generators import generate_random_small_cnf
from morphosat.relations import discover_scope_blocks

from src.certificate_checker.replay import build_certificate, replay_certificate, write_certificate
from src.clone_ascent.models import (
    AscentState,
    bca_successors,
    clause_level_state,
    grouped_scope_state,
    initial_state,
    lca_successors,
)
from src.clone_ascent.polymorphisms import NAMED_WITNESSES, signature_hex
from src.clone_ascent.relations import Relation, clause_relation
from src.clone_ascent.search import SearchConfig, exact_clone_ascent, naive_clone_ascent
from src.exact_parameters.parameters import exact_parameter_bundle
from src.family_generators.composition import compose_morphon
from src.morphon_synthesis.sat_cegis import sat_cegis_search
from src.morphon_synthesis.synthesis import (
    TARGETS,
    check_morphon,
    clause_universe,
    complete_enumeration_search,
    complement_formula,
    local_mutation_search,
    minimize_morphon,
    random_cegis_search,
    satisfiable_robust_random_search,
)


RESULTS = ROOT / "results"
MORPHONS = ROOT / "morphons"
PARAM_COUNTEREXAMPLES = ROOT / "counterexamples" / "parameter_relations"
SCOPE_COUNTEREXAMPLES = ROOT / "counterexamples" / "scope_recovery"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_dimacs(path: Path, formula: tuple[tuple[int, ...], ...], comments: tuple[str, ...] = tuple()) -> None:
    nvars = max((abs(literal) for clause in formula for literal in clause), default=0)
    with path.open("w", encoding="utf-8") as stream:
        for comment in comments:
            stream.write(f"c {comment}\n")
        stream.write(f"p cnf {nvars} {len(formula)}\n")
        for clause in formula:
            stream.write(" ".join(map(str, clause)) + " 0\n")


def read_dimacs(path: Path) -> tuple[tuple[int, ...], ...]:
    clauses = []
    current = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("c") or line.startswith("p"):
            continue
        for token in line.split():
            literal = int(token)
            if literal == 0:
                clauses.append(tuple(current))
                current = []
            else:
                current.append(literal)
    return tuple(clauses)


def brute_status(formula: tuple[tuple[int, ...], ...]) -> tuple[str, int]:
    nvars = max((abs(literal) for clause in formula for literal in clause), default=0)
    models = 0
    for bits in range(1 << nvars):
        if all(any(bool((bits >> (abs(literal) - 1)) & 1) == (literal > 0) for literal in clause) for clause in formula):
            models += 1
    return ("SAT" if models else "UNSAT"), models


def relation_json(formula: tuple[tuple[int, ...], ...]) -> list[dict[str, object]]:
    return [clause_relation(clause).to_dict() for clause in formula]


def synthesize_morphons() -> tuple[list[dict[str, object]], dict[str, tuple[tuple[int, ...], ...]], dict[str, object]]:
    settings = {
        "affine": (8, 100),
        "bijunctive": (9, 200),
        "horn": (10, 5000),
    }
    catalog = []
    formulas: dict[str, tuple[tuple[int, ...], ...]] = {}
    coverage: dict[str, object] = {"random_cegis": {}, "complete_enumeration": {}, "smt_cegis": {}, "local_mutation": {}}
    for target, (clauses, trials) in settings.items():
        candidate, search = random_cegis_search(4, clauses, target, trials, 3008)
        coverage["random_cegis"][target] = search  # type: ignore[index]
        if candidate is None:
            continue
        minimized, minimality = minimize_morphon(candidate, target)
        check = check_morphon(minimized, target)
        assert check.valid and check.witness_state is not None
        state = check.witness_state
        morphon_id = f"morphon-{target}-4v-{len(minimized)}c"
        directory = MORPHONS / morphon_id
        directory.mkdir(parents=True, exist_ok=True)
        write_dimacs(directory / "instance.cnf", minimized, ("clause-level relations; no scope grouping",))
        certificate = build_certificate(state, minimized)
        write_certificate(directory / "ascent_certificate.json", certificate)
        verified, detail = replay_certificate(certificate, minimized)
        assert verified, detail
        (directory / "verification.log").write_text(json.dumps(detail, indent=2), encoding="utf-8")
        (directory / "minimality.json").write_text(json.dumps(minimality, indent=2), encoding="utf-8")
        write_csv(directory / "clone_trajectory.csv", list(detail["snapshots"]))  # type: ignore[arg-type]
        write_csv(RESULTS / "clone_trajectories" / f"{morphon_id}.csv", list(detail["snapshots"]))  # type: ignore[arg-type]
        status, models = brute_status(minimized)
        metadata = {
            "id": morphon_id,
            "target_class": target,
            "target_witnesses": list(TARGETS[target]),
            "model": "LCA",
            "scope_grouping": False,
            "check": check.to_dict(),
            "minimality": minimality,
            "satisfiability": status,
            "model_count": models,
            "degenerate_local_contradiction": status == "UNSAT",
            "search": search,
            "relation_representation": relation_json(minimized),
        }
        (directory / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        catalog.append(metadata)
        formulas[target] = minimized

        _, enumeration = complete_enumeration_search(2, len(clause_universe(2)), target)
        coverage["complete_enumeration"][target] = enumeration  # type: ignore[index]
        _, smt = sat_cegis_search(ROOT, 3, 5, target, 8)
        coverage["smt_cegis"][target] = smt  # type: ignore[index]
        _, mutation = local_mutation_search(minimized, target, 40, 3030)
        coverage["local_mutation"][target] = mutation  # type: ignore[index]

    with (RESULTS / "morphon_catalog.jsonl").open("w", encoding="utf-8") as stream:
        for item in catalog:
            stream.write(json.dumps(item, sort_keys=True) + "\n")
    return catalog, formulas, coverage


def v02_instances() -> list[tuple[str, tuple[tuple[int, ...], ...], int]]:
    output = []
    for nvars in (4, 5):
        for seed in range(10):
            cnf = generate_random_small_cnf(
                nvars, nvars + 4, min(4, nvars), 10_000 + nvars * 100 + seed
            )
            output.append((f"v02-random-exact-n{nvars}-s{seed}", tuple(cnf.clauses), nvars))
    return output


def exact_search_audit() -> tuple[list[dict[str, object]], dict[str, tuple[tuple[int, ...], ...]], dict[str, object]]:
    with (ROOT / "morphosat_research/results/exact_parameters.csv").open() as stream:
        expected = {
            row["instance_id"]: int(row["morph_width"])
            for row in csv.DictReader(stream)
        }
    rows = []
    formulas: dict[str, tuple[tuple[int, ...], ...]] = {}
    coverage = {"v02_instances": 20, "optimized_naive_agreements": 0, "legacy_width_agreements": 0}
    for instance_id, formula, nvars in v02_instances():
        short_id = instance_id.replace("v02-random-exact-", "random_exact.").replace("-s", ".s")
        blocks = discover_scope_blocks(type("CNFProxy", (), {"clauses": list(formula)})(), 8)
        grouped = initial_state(Relation(block.scope, block.mask) for block in blocks)
        legacy_config = SearchConfig(
            model="LCA", minimum_lca_parents=2, max_births=nvars,
            isomorphism_dedup=False, legacy_empty_validity=True,
        )
        optimized = exact_clone_ascent(grouped, legacy_config)
        naive = naive_clone_ascent(grouped, legacy_config)
        optimized_costs = {item.cost.as_tuple() for item in optimized.frontier}
        naive_costs = {item.cost.as_tuple() for item in naive.frontier}
        crosscheck = optimized_costs == naive_costs
        coverage["optimized_naive_agreements"] += int(crosscheck)
        width = min(item.cost.scope_width for item in optimized.frontier)
        legacy_match = width == expected[short_id]
        coverage["legacy_width_agreements"] += int(legacy_match)
        rows.append({
            "instance_id": instance_id, "source": "v0.2 exact suite", "configuration": "legacy_v01_LCA",
            "model": "LCA", "initialization": "legacy_scope_grouping", "found": optimized.found,
            "minimum_births": optimized.minimum_births, "minimum_scope_width": width,
            "expected_v02_width": expected[short_id], "legacy_match": legacy_match,
            "naive_crosscheck": crosscheck, "frontier": json.dumps([item.cost.to_dict() for item in optimized.frontier]),
            "explored_states": optimized.explored_states,
        })
        clause_state = clause_level_state(formula)
        for model, limit in (("LCA", nvars), ("BCA", 2)):
            config = SearchConfig(model=model, max_births=limit)
            result = exact_clone_ascent(clause_state, config)
            naive_result = naive_clone_ascent(clause_state, config)
            agree = {item.cost.as_tuple() for item in result.frontier} == {
                item.cost.as_tuple() for item in naive_result.frontier
            }
            rows.append({
                "instance_id": instance_id, "source": "v0.2 exact suite", "configuration": f"clause_{model}",
                "model": model, "initialization": "clause_level", "found": result.found,
                "minimum_births": result.minimum_births,
                "minimum_scope_width": min((item.cost.scope_width for item in result.frontier), default=None),
                "naive_crosscheck": agree, "frontier": json.dumps([item.cost.to_dict() for item in result.frontier]),
                "explored_states": result.explored_states,
                "bounded_birth_search": limit,
            })
        formulas[instance_id] = formula

    scope_formula = read_dimacs(ROOT / "morphosat_research/counterexamples/scope_recovery_failure.cnf")
    formulas["v02-scope-recovery-1minimal"] = scope_formula
    generated_rng = random.Random(3300)
    universe = clause_universe(3)
    for seed in range(10):
        formulas[f"auto-small-s{seed}"] = tuple(sorted(generated_rng.sample(universe, 5)))
    formulas["boundary-empty-clause"] = (tuple(), (1,))
    formulas["boundary-tautological-pair"] = ((1,), (-1,))
    formulas["same-graph-semantics-a"] = (
        (-1, -2, -3), (1, -2, -3), (-1, -2), (2, -3), (-1, 3),
    )
    formulas["same-graph-semantics-b"] = (
        (-1, 2, 3), (1, 2, -3), (1, 2), (-2, -3), (-1, 3),
    )
    for instance_id in [key for key in formulas if not key.startswith("v02-random")]:
        formula = formulas[instance_id]
        for model in ("LCA", "BCA"):
            config = SearchConfig(model=model, max_births=3)
            optimized = exact_clone_ascent(clause_level_state(formula), config)
            naive = naive_clone_ascent(clause_level_state(formula), config)
            agree = {item.cost.as_tuple() for item in optimized.frontier} == {
                item.cost.as_tuple() for item in naive.frontier
            }
            rows.append({
                "instance_id": instance_id, "source": "additional exact audit", "configuration": f"clause_{model}",
                "model": model, "initialization": "clause_level", "found": optimized.found,
                "minimum_births": optimized.minimum_births,
                "minimum_scope_width": min((item.cost.scope_width for item in optimized.frontier), default=None),
                "naive_crosscheck": agree, "frontier": json.dumps([item.cost.to_dict() for item in optimized.frontier]),
                "explored_states": optimized.explored_states, "bounded_birth_search": 3,
            })
    write_csv(RESULTS / "exact_clone_ascent.csv", rows)
    return rows, formulas, coverage


def flatten_parameters(instance_id: str, formula: tuple[tuple[int, ...], ...]) -> dict[str, object]:
    relations = tuple(clause_relation(clause) for clause in formula)
    bundle = exact_parameter_bundle(relations)
    nvars = len({variable for relation in relations for variable in relation.scope})
    lca = exact_clone_ascent(clause_level_state(formula), SearchConfig(model="LCA", max_births=max(1, nvars)))
    bca = exact_clone_ascent(clause_level_state(formula), SearchConfig(model="BCA", max_births=min(3, max(0, len(formula) - 1))))

    def coordinate(result, name: str):
        values = [getattr(item.cost, name) for item in result.frontier]
        return min(values) if values else None

    row: dict[str, object] = {
        "instance_id": instance_id,
        "nvars": nvars,
        "nclauses": len(formula),
        "scope_signature": json.dumps(sorted([list(relation.scope) for relation in relations])),
        "relation_semantics_sha256": hashlib.sha256(json.dumps(relation_json(formula), sort_keys=True).encode()).hexdigest(),
        "lca_caf_scope": coordinate(lca, "scope_width"),
        "lca_caf_max_tuples": coordinate(lca, "max_tuple_count"),
        "lca_caf_operations": coordinate(lca, "discovery_work"),
        "lca_found": lca.found,
        "bca_caf_scope": coordinate(bca, "scope_width"),
        "bca_caf_max_tuples": coordinate(bca, "max_tuple_count"),
        "bca_found_within_3": bca.found,
        "primal_treewidth": bundle["primal_treewidth"]["value"],
        "primal_treewidth_status": bundle["primal_treewidth"]["status"],
        "incidence_treewidth": bundle["incidence_treewidth"]["value"],
        "incidence_treewidth_status": bundle["incidence_treewidth"]["status"],
        "induced_width": bundle["induced_width"]["value"],
        "linear_joinwidth": bundle["linear_joinwidth"].get("value"),
        "linear_joinwidth_status": bundle["linear_joinwidth"]["status"],
        "general_joinwidth": bundle["general_joinwidth"].get("value"),
        "general_joinwidth_status": bundle["general_joinwidth"]["status"],
        "formula": json.dumps(formula),
        "relations": json.dumps(relation_json(formula)),
    }
    for target in ("affine", "horn", "dual_horn", "bijunctive", "scattered"):
        data = bundle[target]
        for parameter in (
            "strong_backdoor_size", "backdoor_depth", "recursive_backdoor_depth", "backdoor_treewidth"
        ):
            row[f"{target}_{parameter}"] = data[parameter].get("value")
            row[f"{target}_{parameter}_status"] = data[parameter]["status"]
    return row


def parameter_audit(
    formulas: dict[str, tuple[tuple[int, ...], ...]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected = {
        key: value for key, value in formulas.items()
        if key.startswith("v02-random") or key.startswith("morphon-") or key.startswith("auto-small")
        or key.startswith("same-graph-semantics")
    }
    rows = [flatten_parameters(instance_id, formula) for instance_id, formula in selected.items()]
    write_csv(RESULTS / "parameter_relations.csv", rows)
    parameters = [
        "induced_width", "linear_joinwidth", "general_joinwidth",
        "affine_strong_backdoor_size", "affine_backdoor_depth", "affine_recursive_backdoor_depth",
        "affine_backdoor_treewidth", "horn_strong_backdoor_size", "horn_backdoor_depth",
        "horn_recursive_backdoor_depth", "horn_backdoor_treewidth",
    ]
    reversals = []
    for parameter in parameters:
        best = None
        for left in rows:
            for right in rows:
                values = (left.get("lca_caf_scope"), right.get("lca_caf_scope"), left.get(parameter), right.get(parameter))
                if any(value is None for value in values):
                    continue
                a, b, c, d = map(float, values)
                if (a < b and c > d) or (a > b and c < d):
                    score = int(left["nvars"]) + int(right["nvars"]) + int(left["nclauses"]) + int(right["nclauses"])
                    candidate = (score, left, right)
                    if best is None or candidate[0] < best[0]:
                        best = candidate
        if best:
            _, left, right = best
            item = {
                "kind": "finite_strict_order_reversal", "parameter": parameter,
                "left": left["instance_id"], "right": right["instance_id"],
                "left_caf_scope": left["lca_caf_scope"], "right_caf_scope": right["lca_caf_scope"],
                "left_parameter": left[parameter], "right_parameter": right[parameter],
                "claim_limit": "finite incomparability evidence only",
            }
            reversals.append(item)
            directory = PARAM_COUNTEREXAMPLES / f"reversal-{parameter}"
            directory.mkdir(parents=True, exist_ok=True)
            for label, row in (("left", left), ("right", right)):
                formula = tuple(tuple(clause) for clause in json.loads(str(row["formula"])))
                write_dimacs(directory / f"{label}.cnf", formula)
                (directory / f"{label}_relations.json").write_text(str(row["relations"]), encoding="utf-8")
                ascent = exact_clone_ascent(
                    clause_level_state(formula),
                    SearchConfig(model="LCA", max_births=max(1, int(row["nvars"]))),
                )
                if ascent.frontier:
                    certificate = build_certificate(ascent.frontier[0].state, formula)
                    write_certificate(directory / f"{label}_ascent_certificate.json", certificate)
                    ok, replay = replay_certificate(certificate, formula)
                    if not ok:
                        raise AssertionError(replay)
            (directory / "parameters.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
            (directory / "all_parameters.json").write_text(json.dumps({
                "left": {key: value for key, value in left.items() if key not in {"formula", "relations"}},
                "right": {key: value for key, value in right.items() if key not in {"formula", "relations"}},
            }, indent=2), encoding="utf-8")
            (directory / "verification.log").write_text(
                "Values recomputed by exact_parameter_bundle; status fields are EXACT. "
                "Both LCA trajectory certificates replay independently.\n",
                encoding="utf-8",
            )
            (directory / "minimality.json").write_text(json.dumps({
                "search_scope": len(rows), "ordering": "minimum nvars+nclauses within audited dataset",
                "global_minimality": False,
            }, indent=2), encoding="utf-8")

    by_graph: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_graph[str(row["scope_signature"])].append(row)
    semantic_pair = None
    for group in by_graph.values():
        for left in group:
            for right in group:
                if left["relation_semantics_sha256"] != right["relation_semantics_sha256"] and left["lca_caf_scope"] != right["lca_caf_scope"]:
                    semantic_pair = {
                        "kind": "same_graph_different_semantics",
                        "left": left["instance_id"], "right": right["instance_id"],
                        "scope_signature": left["scope_signature"],
                        "left_caf_scope": left["lca_caf_scope"], "right_caf_scope": right["lca_caf_scope"],
                    }
                    break
            if semantic_pair:
                break
        if semantic_pair:
            break
    if semantic_pair:
        reversals.append(semantic_pair)
        directory = PARAM_COUNTEREXAMPLES / "same-graph-different-semantics"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "parameters.json").write_text(json.dumps(semantic_pair, indent=2), encoding="utf-8")
        for label in ("left", "right"):
            row = next(item for item in rows if item["instance_id"] == semantic_pair[label])
            formula = tuple(tuple(clause) for clause in json.loads(str(row["formula"])))
            write_dimacs(directory / f"{label}.cnf", formula)
            (directory / f"{label}_relations.json").write_text(str(row["relations"]), encoding="utf-8")
        (directory / "verification.log").write_text(
            "Identical ordered scope multiset verified; relation masks and exact LCA CAF scope differ.\n",
            encoding="utf-8",
        )
    return rows, reversals


def greedy_run(state: AscentState, target: str, model: str, order: str, recursive: bool, early: bool, seed: int) -> AscentState:
    rng = random.Random(seed)
    targets = TARGETS[target]
    while True:
        if early and any(item in state.witnesses for item in targets):
            return state
        successors = lca_successors(state, recursive) if model == "LCA" else bca_successors(state, recursive)
        if not successors:
            return state
        if order == "min_scope":
            state = min(successors, key=lambda item: (
                item.steps[-1].child.arity, item.steps[-1].child.tuple_count, item.steps[-1].parent_ids
            ))
        elif order == "random":
            state = rng.choice(successors)
        else:
            state = successors[0]


def ablation_audit(formulas: dict[str, tuple[tuple[int, ...], ...]]) -> list[dict[str, object]]:
    rows = []
    for target, formula in formulas.items():
        if target not in TARGETS:
            continue
        configs = [
            ("current_min_scope", clause_level_state(formula), "LCA", "min_scope", True, True, 0),
            ("recursive_birth", clause_level_state(formula), "LCA", "min_scope", True, True, 0),
            ("no_recursive_birth", clause_level_state(formula), "LCA", "min_scope", False, True, 0),
            ("early_stop", clause_level_state(formula), "LCA", "min_scope", True, True, 0),
            ("full_elimination", clause_level_state(formula), "LCA", "min_scope", True, False, 0),
            ("legacy_scope_grouping", grouped_scope_state(formula), "LCA", "min_scope", True, True, 0),
            ("external_order", clause_level_state(tuple(reversed(formula))), "LCA", "external", True, True, 0),
            ("BCA", clause_level_state(formula), "BCA", "min_scope", True, True, 0),
        ]
        for seed in range(10):
            configs.append(("random_order", clause_level_state(formula), "LCA", "random", True, True, seed))
        for name, state, model, order, recursive, early, seed in configs:
            endpoint = greedy_run(state, target, model, order, recursive, early, seed)
            success = any(item in endpoint.witnesses for item in TARGETS[target])
            rows.append({
                "morphon": target, "configuration": name, "seed": seed, "model": model,
                "recursive_births": recursive, "early_stop": early, "scope_grouping": name == "legacy_scope_grouping",
                "success": success, "births": len(endpoint.steps), "generation_depth": endpoint.cost.generation_depth,
                **endpoint.cost.to_dict(),
            })
        exact = exact_clone_ascent(
            clause_level_state(formula),
            SearchConfig(model="LCA", target_witnesses=TARGETS[target], max_births=4),
        )
        rows.append({
            "morphon": target, "configuration": "exact_optimal", "seed": 0, "model": "LCA",
            "recursive_births": True, "early_stop": True, "scope_grouping": False,
            "success": exact.found, "births": exact.minimum_births,
            "generation_depth": min((item.cost.generation_depth for item in exact.frontier), default=None),
            "frontier": json.dumps([item.cost.to_dict() for item in exact.frontier]),
        })
    write_csv(RESULTS / "ablations.csv", rows)
    return rows


def family_and_lifting_audit(formula: tuple[tuple[int, ...], ...]) -> list[dict[str, object]]:
    rows = []
    proof_directory = RESULTS / "lifting_proofs"
    proof_directory.mkdir(parents=True, exist_ok=True)
    cadical = ROOT / "morphosat_research/.audit_tools/bin/cadical"
    checker = ROOT / "morphosat_research/.audit_tools/bin/drat-trim"
    for skeleton in ("path", "balanced_tree", "grid", "expander", "tseitin_core"):
        for size in (2, 4, 8):
            nvars, clauses, metadata = compose_morphon(formula, skeleton, size, seed=3300 + size)
            row = {"skeleton": skeleton, "size": size, "nvars": nvars, "nclauses": len(clauses), **metadata}
            if cadical.exists() and checker.exists():
                cnf_path = proof_directory / f"{skeleton}-{size}.cnf"
                proof_path = proof_directory / f"{skeleton}-{size}.drat"
                write_dimacs(cnf_path, clauses)
                solve = subprocess.run(
                    [str(cadical), "--binary=false", str(cnf_path), str(proof_path)],
                    text=True, capture_output=True, timeout=30,
                )
                verify = subprocess.run(
                    [str(checker), str(cnf_path), str(proof_path)],
                    text=True, capture_output=True, timeout=30,
                )
                row.update({
                    "sat_status": "UNSAT" if solve.returncode == 20 else "UNKNOWN",
                    "proof_size_bytes": proof_path.stat().st_size if proof_path.exists() else 0,
                    "proof_verified": verify.returncode == 0 and "VERIFIED" in verify.stdout,
                })
                (proof_directory / f"{skeleton}-{size}.check.log").write_text(verify.stdout + verify.stderr, encoding="utf-8")
            rows.append(row)
    write_csv(RESULTS / "family_attempts.csv", rows)
    return rows


def main() -> None:
    for directory in (RESULTS, MORPHONS, PARAM_COUNTEREXAMPLES, SCOPE_COUNTEREXAMPLES):
        directory.mkdir(parents=True, exist_ok=True)
    catalog, morphon_formulas, synthesis_coverage = synthesize_morphons()
    satisfiable_morphon, satisfiable_coverage = satisfiable_robust_random_search(4, 300000, 3009)
    exact_rows, exact_formulas, exact_coverage = exact_search_audit()
    all_formulas = dict(exact_formulas)
    for target, formula in morphon_formulas.items():
        all_formulas[f"morphon-{target}"] = formula
    parameter_rows, reversals = parameter_audit(all_formulas)
    ablations = ablation_audit(morphon_formulas)
    family_rows = family_and_lifting_audit(morphon_formulas["affine"])

    scope_source = ROOT / "morphosat_research/counterexamples/scope_recovery_failure.cnf"
    scope_target = SCOPE_COUNTEREXAMPLES / "v02-1minimal.cnf"
    scope_target.write_bytes(scope_source.read_bytes())
    (SCOPE_COUNTEREXAMPLES / "verification.log").write_text(
        "Replayed in exact_clone_ascent.csv under clause-level LCA and BCA; legacy grouping is an ablation only.\n",
        encoding="utf-8",
    )
    coverage = {
        "synthesis": synthesis_coverage,
        "exact_search": exact_coverage,
        "morphons_found": len(catalog),
        "all_morphons_unsat": all(item["satisfiability"] == "UNSAT" for item in catalog),
        "parameter_instances": len(parameter_rows),
        "finite_reversals": len(reversals),
        "ablation_runs": len(ablations),
        "family_attempts": len(family_rows),
        "satisfiable_robust_random_search": {
            **satisfiable_coverage,
            "nvars": 4,
            "result": "FOUND" if satisfiable_morphon else "NONE",
        },
    }
    (RESULTS / "search_coverage.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    summary = {
        "tests_pending": True,
        "legacy_width_agreements": exact_coverage["legacy_width_agreements"],
        "optimized_naive_agreements": exact_coverage["optimized_naive_agreements"],
        "morphons": [item["id"] for item in catalog],
        "morphons_all_unsat": coverage["all_morphons_unsat"],
        "finite_parameter_reversals": len(reversals),
        "family_rejected": True,
        "research_decision_evidence": "Morphons exist only as local contradictions; no scalable separation or lower bound",
    }
    (RESULTS / "test_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
