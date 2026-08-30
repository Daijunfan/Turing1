#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from morphosat.bruteforce import solve_bruteforce
from morphosat.certificate import (
    build_affine_unsat_certificate,
    write_certificate,
)
from morphosat.fusion import fuse_until_tractable
from morphosat.fusion_certificate import build_fusion_affine_unsat_certificate
from morphosat.fusion_solver import MorphFusionSolver
from morphosat.generators import (
    generate_gate_hidden_2sat_chain,
    generate_gate_hidden_horn_cascade,
    generate_gate_obfuscated_tseitin,
    generate_obfuscated_tseitin,
    generate_random_small_cnf,
)
from morphosat.relations import discover_scope_blocks
from morphosat.solver import MorphSolver
from morphosat.z3ffi import Z3FFI

RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)


def save_rows(name: str, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(RESULTS / name, index=False)


def z3_version() -> str:
    try:
        return subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", "libz3-4"], text=True
        ).strip()
    except Exception:
        return "unknown"


def run_z3(z3: Z3FFI, cnf, timeout_ms: int, seed: int = 1) -> dict[str, object]:
    r = z3.solve(cnf, timeout_ms=timeout_ms, seed=seed)
    return {
        "z3_status": r.status,
        "z3_seconds": r.elapsed_seconds,
        "z3_timeout_ms": timeout_ms,
        "z3_conflicts": Z3FFI.parse_stat(r.stats_text, "sat-conflicts"),
        "z3_decisions": Z3FFI.parse_stat(r.stats_text, "sat-decisions"),
        "z3_propagations_nary": Z3FFI.parse_stat(r.stats_text, "sat-propagations-nary"),
    }


def correctness_stress() -> dict[str, object]:
    print("[1/7] correctness stress", flush=True)
    summary: dict[str, object] = {}

    solver = MorphSolver(6)
    random_total = 5000
    random_answered = random_correct = random_verified = 0
    for seed in range(random_total):
        cnf = generate_random_small_cnf(
            nvars=6,
            nclauses=7 + (seed % 9),
            max_width=4,
            seed=1_000_000 + seed,
        )
        expected, _ = solve_bruteforce(cnf)
        result = solver.solve(cnf)
        if result.status != "UNKNOWN":
            random_answered += 1
            random_correct += int(result.status == expected)
            random_verified += int(result.verified)
    summary["random_small_cnf"] = {
        "instances": random_total,
        "answered": random_answered,
        "correct": random_correct,
        "verified": random_verified,
        "wrong": random_answered - random_correct,
    }

    families: list[dict[str, object]] = []
    z3 = Z3FFI()

    def check_family(label: str, generator, sizes, repetitions: int, use_fusion: bool) -> None:
        answered = correct = verified = unknown = z3_checked = z3_agree = 0
        for size in sizes:
            for rep in range(repetitions):
                for unsat in (False, True):
                    seed = 2_000_000 + size * 1000 + rep * 10 + int(unsat)
                    if generator is generate_gate_obfuscated_tseitin:
                        inst = generator(size, unsat=unsat, seed=seed, encoding="compact")
                    elif generator is generate_obfuscated_tseitin:
                        inst = generator(size, unsat=unsat, seed=seed, private_per_vertex=2)
                    else:
                        inst = generator(size, unsat=unsat, seed=seed)
                    result = (
                        MorphFusionSolver(8, 8, adaptive=True).solve(inst.cnf)
                        if use_fusion else MorphSolver(8).solve(inst.cnf)
                    )
                    if result.status == "UNKNOWN":
                        unknown += 1
                    else:
                        answered += 1
                        correct += int(result.status == inst.expected_status)
                        verified += int(result.verified)
                    # Independent solver cross-check only on bounded cases to keep
                    # the stress test deterministic and finite.
                    if inst.cnf.nvars <= 400:
                        zr = z3.solve(inst.cnf, timeout_ms=2000, seed=rep + 1)
                        if zr.status in {"SAT", "UNSAT"}:
                            z3_checked += 1
                            z3_agree += int(zr.status == inst.expected_status)
        families.append({
            "family": label,
            "instances": answered + unknown,
            "answered": answered,
            "unknown": unknown,
            "correct": correct,
            "verified": verified,
            "wrong": answered - correct,
            "z3_decisive_crosschecks": z3_checked,
            "z3_agreements": z3_agree,
        })

    check_family("direct_hidden_affine", generate_obfuscated_tseitin, [8, 16, 32, 64], 5, False)
    check_family("gate_fused_affine", generate_gate_obfuscated_tseitin, [4, 6, 8, 12, 16, 24, 32], 3, True)
    check_family("gate_fused_2sat", generate_gate_hidden_2sat_chain, [8, 32, 128], 5, True)
    check_family("gate_fused_horn", generate_gate_hidden_horn_cascade, [4, 16, 64], 5, True)
    save_rows("correctness_families.csv", families)
    summary["generated_families"] = families
    return summary


def direct_scaling() -> list[dict[str, object]]:
    print("[2/7] direct semantic-language scaling", flush=True)
    rows: list[dict[str, object]] = []
    morph = MorphSolver(8)
    z3 = Z3FFI()
    sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
    for size in sizes:
        reps = 3
        for rep in range(reps):
            seed = 3_000_000 + size * 10 + rep
            t0 = perf_counter()
            inst = generate_obfuscated_tseitin(
                size, degree=3, private_per_vertex=2, unsat=True, seed=seed
            )
            generation_seconds = perf_counter() - t0
            t0 = perf_counter()
            result = morph.solve(inst.cnf)
            morph_seconds = perf_counter() - t0
            row: dict[str, object] = {
                "vertices": size,
                "rep": rep,
                "seed": seed,
                "nvars": inst.cnf.nvars,
                "nclauses": len(inst.cnf.clauses),
                "generation_seconds": generation_seconds,
                "morph_seconds": morph_seconds,
                "morph_status": result.status,
                "morph_verified": result.verified,
                "concept_births": result.metrics.get("concept_births"),
                "concept_depth": result.metrics.get("concept_depth"),
                "certificate_equations": result.certificate.get("certificate_equations"),
                "initial_common_classes": json.dumps(result.metrics.get("common_classes", [])),
            }
            if size <= 256:
                row.update(run_z3(z3, inst.cnf, timeout_ms=2000, seed=rep + 1))
            rows.append(row)
            save_rows("direct_affine_scaling.csv", rows)
            print(" direct", size, rep, result.status, round(morph_seconds, 4), row.get("z3_status", "-"), flush=True)
    return rows


def fusion_scaling() -> list[dict[str, object]]:
    print("[3/7] gate-tissue fusion scaling", flush=True)
    rows: list[dict[str, object]] = []
    z3 = Z3FFI()
    sizes = [8, 16, 32, 64, 96, 128, 160, 192]
    for size in sizes:
        reps = 3 if size <= 128 else 1
        for rep in range(reps):
            seed = 4_000_000 + size * 10 + rep
            inst = generate_gate_obfuscated_tseitin(
                size, unsat=True, seed=seed, encoding="compact"
            )
            base = MorphSolver(8).solve(inst.cnf)
            t0 = perf_counter()
            result = MorphFusionSolver(8, 8, adaptive=True).solve(inst.cnf)
            morph_seconds = perf_counter() - t0
            row: dict[str, object] = {
                "vertices": size,
                "rep": rep,
                "seed": seed,
                "nvars": inst.cnf.nvars,
                "nclauses": len(inst.cnf.clauses),
                "no_fusion_status": base.status,
                "initial_common_classes": json.dumps(base.metrics.get("common_classes", [])),
                "fusion_status": result.status,
                "fusion_verified": result.verified,
                "fusion_method": result.method,
                "fusion_seconds": morph_seconds,
                "fusion_steps": result.metrics.get("fusion_steps"),
                "fusion_depth": result.metrics.get("fusion_depth"),
                "remaining_macro_relations": result.metrics.get("remaining_macro_relations"),
                "emergent_common_classes": json.dumps(result.metrics.get("emergent_common_classes", [])),
                "attempt_count": result.metrics.get("fusion_attempt_count"),
                "selected_macro_arity": result.metrics.get("selected_max_macro_arity"),
                "selected_tie_seed": result.metrics.get("selected_tie_seed"),
            }
            if size <= 128:
                row.update(run_z3(z3, inst.cnf, timeout_ms=2000, seed=rep + 1))
            rows.append(row)
            save_rows("fusion_affine_scaling.csv", rows)
            print(" fusion", size, rep, result.status, round(morph_seconds, 4), row.get("z3_status", "-"), flush=True)
    return rows


def cross_language_emergence() -> list[dict[str, object]]:
    print("[4/7] cross-language emergence", flush=True)
    rows: list[dict[str, object]] = []
    cases = [
        ("gate_hidden_2sat", generate_gate_hidden_2sat_chain, [32, 128, 512]),
        ("gate_hidden_horn", generate_gate_hidden_horn_cascade, [16, 64, 256]),
    ]
    for family, generator, sizes in cases:
        for size in sizes:
            for rep in range(3):
                for unsat in (False, True):
                    seed = 5_000_000 + size * 100 + rep * 10 + int(unsat)
                    inst = generator(size, unsat=unsat, seed=seed)
                    base = MorphSolver(8).solve(inst.cnf)
                    result = MorphFusionSolver(8, 8, adaptive=True).solve(inst.cnf)
                    rows.append({
                        "family": family,
                        "size": size,
                        "rep": rep,
                        "expected": inst.expected_status,
                        "nvars": inst.cnf.nvars,
                        "nclauses": len(inst.cnf.clauses),
                        "no_fusion_status": base.status,
                        "initial_common_classes": json.dumps(base.metrics.get("common_classes", [])),
                        "fusion_status": result.status,
                        "verified": result.verified,
                        "method": result.method,
                        "emergent_common_classes": json.dumps(result.metrics.get("emergent_common_classes", [])),
                        "fusion_steps": result.metrics.get("fusion_steps"),
                        "fusion_depth": result.metrics.get("fusion_depth"),
                        "seconds": result.elapsed_seconds,
                    })
                    save_rows("cross_language_emergence.csv", rows)
    return rows


def order_and_width_experiments() -> dict[str, object]:
    print("[5/7] order parameter and width threshold", flush=True)
    inst = generate_gate_obfuscated_tseitin(64, unsat=True, seed=8064, encoding="compact")
    blocks = discover_scope_blocks(inst.cnf, 8)
    fusion = fuse_until_tractable(blocks, 8, tie_seed=0)
    trace = []
    for item in fusion.order_trace:
        row = dict(item)
        row["common_classes"] = json.dumps(row["common_classes"])
        trace.append(row)
    save_rows("polymorphism_order_trace.csv", trace)

    width_rows: list[dict[str, object]] = []
    small = generate_gate_obfuscated_tseitin(32, unsat=True, seed=8032, encoding="compact")
    small_blocks = discover_scope_blocks(small.cnf, 8)
    for width in range(2, 9):
        f = fuse_until_tractable(
            small_blocks, width, stop_preference=("affine",), tie_seed=0
        )
        width_rows.append({
            "max_macro_arity": width,
            "affine_emerged": "affine" in f.common_classes,
            "steps": len(f.steps),
            "remaining_relations": len(f.relations),
            "max_depth": f.max_depth,
            "final_affine_fraction": f.order_trace[-1]["affine_fraction"] if f.order_trace else 0.0,
        })
    save_rows("width_threshold.csv", width_rows)
    return {
        "trace_instance": {
            "nvars": inst.cnf.nvars,
            "nclauses": len(inst.cnf.clauses),
            "steps": len(fusion.steps),
            "initial": fusion.order_trace[0],
            "final": fusion.order_trace[-1],
        },
        "width_threshold": width_rows,
    }


def make_flagships() -> dict[str, object]:
    print("[6/7] standalone proof artifacts", flush=True)
    out: dict[str, object] = {}

    direct = generate_obfuscated_tseitin(
        4096, private_per_vertex=2, unsat=True, seed=6_004_096
    )
    direct_cnf = RESULTS / "flagship_direct_4096.cnf"
    direct_cert = RESULTS / "flagship_direct_4096.cert.json"
    direct.cnf.to_dimacs(direct_cnf, comments=["MORPH-SAT hidden affine flagship"])
    write_certificate(direct_cert, build_affine_unsat_certificate(direct.cnf, 8))
    out["direct"] = {
        "nvars": direct.cnf.nvars,
        "nclauses": len(direct.cnf.clauses),
        "cnf_bytes": direct_cnf.stat().st_size,
        "certificate_bytes": direct_cert.stat().st_size,
    }

    gate = generate_gate_obfuscated_tseitin(
        64, unsat=True, seed=8064, encoding="compact"
    )
    gate_cnf = RESULTS / "flagship_gate_fusion_64.cnf"
    gate_cert = RESULTS / "flagship_gate_fusion_64.cert.json"
    gate.cnf.to_dimacs(gate_cnf, comments=["MORPH-SAT unlabeled compact AND/OR/NOT tissue flagship"])
    write_certificate(gate_cert, build_fusion_affine_unsat_certificate(gate.cnf, 8, 8))
    out["gate_fusion"] = {
        "nvars": gate.cnf.nvars,
        "nclauses": len(gate.cnf.clauses),
        "cnf_bytes": gate_cnf.stat().st_size,
        "certificate_bytes": gate_cert.stat().st_size,
    }
    return out


def power_fit(frame: pd.DataFrame, x: str, y: str) -> dict[str, float]:
    grouped = frame.groupby(x, as_index=False)[y].median()
    xv = np.log(grouped[x].to_numpy(dtype=float))
    yv = np.log(grouped[y].to_numpy(dtype=float))
    coeff = np.polyfit(xv, yv, 1)
    pred = np.polyval(coeff, xv)
    ss_res = float(np.sum((yv - pred) ** 2))
    ss_tot = float(np.sum((yv - np.mean(yv)) ** 2))
    return {
        "exponent": float(coeff[0]),
        "log_intercept": float(coeff[1]),
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0,
        "points": int(len(grouped)),
    }


def make_plots_and_summary(
    correctness: dict[str, object],
    direct_rows: list[dict[str, object]],
    fusion_rows: list[dict[str, object]],
    cross_rows: list[dict[str, object]],
    order: dict[str, object],
    flagships: dict[str, object],
) -> dict[str, object]:
    print("[7/7] plots and final summary", flush=True)
    direct = pd.DataFrame(direct_rows)
    fusion = pd.DataFrame(fusion_rows)
    trace = pd.read_csv(RESULTS / "polymorphism_order_trace.csv")
    width = pd.read_csv(RESULTS / "width_threshold.csv")

    dmed = direct.groupby("vertices", as_index=False)["morph_seconds"].median()
    plt.figure(figsize=(7.2, 4.8))
    plt.loglog(dmed["vertices"], dmed["morph_seconds"], marker="o", label="MORPH semantic compiler")
    if "z3_seconds" in direct.columns:
        zmed = direct.dropna(subset=["z3_seconds"]).groupby("vertices", as_index=False)["z3_seconds"].median()
        plt.loglog(zmed["vertices"], zmed["z3_seconds"], marker="s", label="Z3 4.13.3 (2 s cap)")
    plt.xlabel("Tseitin organs")
    plt.ylabel("Median seconds")
    plt.title("Direct hidden-language scaling")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "direct_scaling.pdf")
    plt.savefig(FIGURES / "direct_scaling.png", dpi=180)
    plt.close()

    fmed = fusion.groupby("vertices", as_index=False)["fusion_seconds"].median()
    plt.figure(figsize=(7.2, 4.8))
    plt.loglog(fmed["vertices"], fmed["fusion_seconds"], marker="o", label="MORPH recursive fusion")
    if "z3_seconds" in fusion.columns:
        zmed = fusion.dropna(subset=["z3_seconds"]).groupby("vertices", as_index=False)["z3_seconds"].median()
        plt.loglog(zmed["vertices"], zmed["z3_seconds"], marker="s", label="Z3 4.13.3 (2 s cap)")
    plt.xlabel("Tseitin organs")
    plt.ylabel("Median seconds")
    plt.title("Unlabeled AND/OR/NOT tissue scaling")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "fusion_scaling.pdf")
    plt.savefig(FIGURES / "fusion_scaling.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7.2, 4.8))
    plt.plot(trace["step"], trace["affine_fraction"], label="Affine-preserved fraction")
    plt.plot(trace["step"], trace["bijunctive_fraction"], label="Bijunctive-preserved fraction")
    plt.plot(trace["step"], trace["horn_fraction"], label="Horn-preserved fraction")
    plt.plot(trace["step"], trace["dual_horn_fraction"], label="Dual-Horn-preserved fraction")
    plt.xlabel("Exact local fusion births")
    plt.ylabel("Order parameter")
    plt.ylim(-0.02, 1.02)
    plt.title("Polymorphism order emergence")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "polymorphism_emergence.pdf")
    plt.savefig(FIGURES / "polymorphism_emergence.png", dpi=180)
    plt.close()

    plt.figure(figsize=(7.2, 4.8))
    plt.plot(width["max_macro_arity"], width["final_affine_fraction"], marker="o")
    plt.xlabel("Maximum macro-relation arity")
    plt.ylabel("Final affine order parameter")
    plt.ylim(-0.02, 1.02)
    plt.title("Morphological-width threshold")
    plt.tight_layout()
    plt.savefig(FIGURES / "width_threshold.pdf")
    plt.savefig(FIGURES / "width_threshold.png", dpi=180)
    plt.close()

    direct_fit = power_fit(direct, "vertices", "morph_seconds")
    fusion_fit = power_fit(fusion, "vertices", "fusion_seconds")
    direct_z3_timeouts = int((direct.get("z3_status") == "TIMEOUT").sum()) if "z3_status" in direct else 0
    fusion_z3_timeouts = int((fusion.get("z3_status") == "TIMEOUT").sum()) if "z3_status" in fusion else 0

    summary = {
        "timestamp_utc": pd.Timestamp.utcnow().isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "z3_package_version": z3_version(),
        },
        "correctness": correctness,
        "direct_scaling_power_fit": direct_fit,
        "fusion_scaling_power_fit": fusion_fit,
        "direct_z3_timeouts": direct_z3_timeouts,
        "fusion_z3_timeouts": fusion_z3_timeouts,
        "cross_language_instances": len(cross_rows),
        "cross_language_all_correct_verified": all(
            r["fusion_status"] == r["expected"] and bool(r["verified"]) for r in cross_rows
        ),
        "order_experiment": order,
        "flagships": flagships,
    }
    (RESULTS / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def main() -> None:
    correctness = correctness_stress()
    direct = direct_scaling()
    fusion = fusion_scaling()
    cross = cross_language_emergence()
    order = order_and_width_experiments()
    flagships = make_flagships()
    summary = make_plots_and_summary(correctness, direct, fusion, cross, order, flagships)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
