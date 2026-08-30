from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from .cnf import CNF


@dataclass(slots=True)
class Z3Result:
    status: str
    elapsed_seconds: float
    stats_text: str
    timeout_ms: int


class Z3FFI:
    """Minimal, dependency-free wrapper around the system libz3 C API."""

    def __init__(self, library: str | None = None) -> None:
        candidates = [
            library,
            os.environ.get("MORPHSAT_Z3_LIBRARY"),
            str(Path(__file__).resolve().parents[1] / ".audit_tools" / "bin" / "libz3.dylib"),
            str(Path(__file__).resolve().parents[1] / ".audit_tools" / "bin" / "libz3.so"),
            ctypes.util.find_library("z3"),
            "/lib/x86_64-linux-gnu/libz3.so.4",
        ]
        errors: list[str] = []
        for candidate in candidates:
            if not candidate:
                continue
            try:
                self.lib = ctypes.CDLL(candidate)
                break
            except OSError as error:
                errors.append(str(error))
        else:
            raise OSError("libz3 was not found; set MORPHSAT_Z3_LIBRARY: " + "; ".join(errors))
        V = ctypes.c_void_p
        C = ctypes.c_char_p
        U = ctypes.c_uint
        I = ctypes.c_int

        self.lib.Z3_mk_config.restype = V
        self.lib.Z3_del_config.argtypes = [V]
        self.lib.Z3_mk_context_rc.argtypes = [V]
        self.lib.Z3_mk_context_rc.restype = V
        self.lib.Z3_del_context.argtypes = [V]
        self.lib.Z3_mk_solver.argtypes = [V]
        self.lib.Z3_mk_solver.restype = V
        self.lib.Z3_solver_inc_ref.argtypes = [V, V]
        self.lib.Z3_solver_dec_ref.argtypes = [V, V]
        self.lib.Z3_solver_from_string.argtypes = [V, V, C]
        self.lib.Z3_solver_check.argtypes = [V, V]
        self.lib.Z3_solver_check.restype = I
        self.lib.Z3_mk_params.argtypes = [V]
        self.lib.Z3_mk_params.restype = V
        self.lib.Z3_params_inc_ref.argtypes = [V, V]
        self.lib.Z3_params_dec_ref.argtypes = [V, V]
        self.lib.Z3_mk_string_symbol.argtypes = [V, C]
        self.lib.Z3_mk_string_symbol.restype = V
        self.lib.Z3_params_set_uint.argtypes = [V, V, V, U]
        self.lib.Z3_params_set_bool.argtypes = [V, V, V, ctypes.c_bool]
        self.lib.Z3_solver_set_params.argtypes = [V, V, V]
        self.lib.Z3_solver_get_statistics.argtypes = [V, V]
        self.lib.Z3_solver_get_statistics.restype = V
        self.lib.Z3_stats_to_string.argtypes = [V, V]
        self.lib.Z3_stats_to_string.restype = C
        self.lib.Z3_solver_get_reason_unknown.argtypes = [V, V]
        self.lib.Z3_solver_get_reason_unknown.restype = C

    @staticmethod
    def _to_smt2(cnf: CNF) -> bytes:
        lines = [f"(declare-fun x{i} () Bool)" for i in range(1, cnf.nvars + 1)]
        for clause in cnf.clauses:
            if not clause:
                lines.append("(assert false)")
                continue
            atoms = [f"x{lit}" if lit > 0 else f"(not x{-lit})" for lit in clause]
            if len(atoms) == 1:
                lines.append(f"(assert {atoms[0]})")
            else:
                lines.append(f"(assert (or {' '.join(atoms)}))")
        return ("\n".join(lines) + "\n").encode("ascii")

    def solve(self, cnf: CNF, timeout_ms: int = 10_000, seed: int = 0) -> Z3Result:
        lib = self.lib
        cfg = lib.Z3_mk_config()
        ctx = lib.Z3_mk_context_rc(cfg)
        lib.Z3_del_config(cfg)
        solver = lib.Z3_mk_solver(ctx)
        lib.Z3_solver_inc_ref(ctx, solver)
        params = lib.Z3_mk_params(ctx)
        lib.Z3_params_inc_ref(ctx, params)
        for name, value in ((b"timeout", timeout_ms), (b"random_seed", seed)):
            sym = lib.Z3_mk_string_symbol(ctx, name)
            lib.Z3_params_set_uint(ctx, params, sym, int(value))
        lib.Z3_solver_set_params(ctx, solver, params)

        script = self._to_smt2(cnf)
        start = perf_counter()
        lib.Z3_solver_from_string(ctx, solver, script)
        raw = lib.Z3_solver_check(ctx, solver)
        elapsed = perf_counter() - start
        if raw == 1:
            status = "SAT"
        elif raw == -1:
            status = "UNSAT"
        else:
            reason = lib.Z3_solver_get_reason_unknown(ctx, solver)
            text = reason.decode("utf-8", errors="replace") if reason else "unknown"
            status = "TIMEOUT" if "timeout" in text.lower() else "UNKNOWN"
        stats = lib.Z3_solver_get_statistics(ctx, solver)
        stats_text = lib.Z3_stats_to_string(ctx, stats).decode("utf-8", errors="replace")

        lib.Z3_params_dec_ref(ctx, params)
        lib.Z3_solver_dec_ref(ctx, solver)
        lib.Z3_del_context(ctx)
        return Z3Result(status, elapsed, stats_text, timeout_ms)

    @staticmethod
    def parse_stat(stats_text: str, key: str) -> float | None:
        pattern = re.compile(rf":{re.escape(key)}\s+([0-9.eE+-]+)")
        match = pattern.search(stats_text)
        return float(match.group(1)) if match else None
