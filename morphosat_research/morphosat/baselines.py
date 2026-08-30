from __future__ import annotations

import os
import re
import resource
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


@dataclass(frozen=True, slots=True)
class BaselineConfig:
    solver: str
    configuration: str
    arguments: tuple[str, ...]


BASELINE_CONFIGS = (
    BaselineConfig("cadical", "default", tuple()),
    BaselineConfig("cadical", "congruence_off", ("--congruence=false",)),
    BaselineConfig("cadical", "congruence_on", ("--congruence=true",)),
    BaselineConfig("cadical", "bve_off", ("--elim=false",)),
    BaselineConfig("cadical", "bve_on", ("--elim=true",)),
    BaselineConfig("cadical", "factor_off", ("--factor=false",)),
    BaselineConfig("cadical", "factor_on", ("--factor=true",)),
    BaselineConfig("cadical", "elimdef_off", ("--elimdef=false",)),
    BaselineConfig("cadical", "elimdef_on", ("--elimdef=true",)),
    BaselineConfig("kissat", "default", tuple()),
    BaselineConfig("cryptominisat5", "default", ("--verb=1", "--printsol=0")),
    BaselineConfig("cryptominisat5", "xor_recovery_off", ("--xor=0", "--verb=1", "--printsol=0")),
    BaselineConfig("cryptominisat5", "xor_recovery_on", ("--xor=1", "--verb=1", "--printsol=0")),
    BaselineConfig("cryptominisat5", "gaussian_off", ("--maxnummatrices=0", "--verb=1", "--printsol=0")),
    BaselineConfig("cryptominisat5", "gaussian_on", ("--maxnummatrices=5", "--verb=1", "--printsol=0")),
    BaselineConfig(
        "cryptominisat5", "xor_and_gaussian_off",
        ("--xor=0", "--maxnummatrices=0", "--verb=1", "--printsol=0"),
    ),
    BaselineConfig(
        "cryptominisat5", "xor_and_gaussian_on",
        ("--xor=1", "--maxnummatrices=5", "--verb=1", "--printsol=0"),
    ),
    BaselineConfig("z3", "default", ("-st",)),
)


def binary_path(root: Path, solver: str) -> Path:
    env_name = f"MORPHSAT_{solver.upper()}_BIN"
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured)
    local = root / ".audit_tools" / "bin" / solver
    if local.exists():
        return local
    found = shutil_which(solver)
    if found:
        return Path(found)
    raise FileNotFoundError(f"{solver} not found; run scripts/bootstrap_baselines.sh")


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def solver_version(binary: Path) -> str:
    flag = "--version"
    completed = subprocess.run([str(binary), flag], capture_output=True, text=True, timeout=15)
    return (completed.stdout + completed.stderr).strip()


def _limit_memory(memory_mb: int):
    def apply() -> None:
        limit = memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (OSError, ValueError):
            # Darwin does not reliably support lowering RLIMIT_AS for a process
            # before dyld has mapped its shared libraries. RSS is still recorded.
            pass

    return apply


def _stat(text: str, names: tuple[str, ...]) -> int | float | None:
    for name in names:
        patterns = (
            rf"(?im)^c\s+{re.escape(name)}\s*[: ]\s*([0-9][0-9,.eE+-]*)",
            rf"(?im)^\s*:{re.escape(name)}\s+([0-9][0-9,.eE+-]*)",
            rf"(?im)^\s*{re.escape(name)}\s+([0-9][0-9,.eE+-]*)",
            rf"(?im)^\s*([0-9][0-9,.eE+-]*)\s+{re.escape(name)}\s*$",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).replace(",", "")
                try:
                    number = float(value)
                    return int(number) if number.is_integer() else number
                except ValueError:
                    pass
    return None


def run_baseline(
    root: Path,
    config: BaselineConfig,
    cnf_path: Path,
    run_id: str,
    timeout_seconds: float,
    memory_mb: int,
    proofs_dir: Path,
) -> dict[str, object]:
    binary = binary_path(root, config.solver)
    proof_path: Path | None = None
    command = [str(binary), *config.arguments]
    proof_capable = config.solver in {"cadical", "kissat"}
    if proof_capable:
        proof_path = proofs_dir / f"{run_id}.{config.solver}.{config.configuration}.drat"
        command.extend(["--binary=false", str(cnf_path), str(proof_path)])
    else:
        command.append(str(cnf_path))
    timed_command = ["/usr/bin/time", "-l", *command]
    start = perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            timed_command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            preexec_fn=_limit_memory(memory_mb),
        )
        returncode = completed.returncode
        output = completed.stdout + "\n" + completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = 124
        stdout = error.stdout.decode("utf-8", errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode("utf-8", errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        output = stdout + "\n" + stderr
    elapsed = perf_counter() - start
    if timed_out:
        status = "TIMEOUT"
    elif re.search(r"(?im)^s\s+UNSATISFIABLE|^unsat$", output):
        status = "UNSAT"
    elif re.search(r"(?im)^s\s+SATISFIABLE|^sat$", output):
        status = "SAT"
    else:
        status = "UNKNOWN"
    max_rss = _stat(output, ("maximum resident set size",))
    proof_size = proof_path.stat().st_size if proof_path and proof_path.exists() else 0
    checker_status = "not_applicable"
    checker_log = ""
    if status == "UNSAT" and proof_path and proof_size:
        checker = binary_path(root, "drat-trim")
        check = subprocess.run(
            [str(checker), str(cnf_path), str(proof_path)],
            capture_output=True,
            text=True,
            timeout=max(30.0, timeout_seconds),
        )
        checker_log = check.stdout + check.stderr
        checker_status = "verified" if check.returncode == 0 and "VERIFIED" in checker_log else "failed"
        (proofs_dir / f"{run_id}.{config.solver}.{config.configuration}.check.log").write_text(
            checker_log, encoding="utf-8"
        )
    elif status == "UNSAT":
        checker_status = "unavailable_for_solver"
    log_path = root / "results" / "run_logs" / f"{run_id}.{config.solver}.{config.configuration}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    return {
        "solver": config.solver,
        "configuration": config.configuration,
        "arguments": " ".join(config.arguments),
        "status": status,
        "seconds": elapsed,
        "timeout": timed_out,
        "returncode": returncode,
        "memory_mb": (float(max_rss) / (1024 * 1024)) if max_rss is not None else None,
        "conflicts": _stat(output, ("conflicts", "sat-conflicts")) or 0,
        "decisions": _stat(output, ("decisions", "sat-decisions")) or 0,
        "propagations": (
            (_stat(output, ("propagations",)) or 0)
            + (_stat(output, ("sat-propagations-2ary",)) or 0)
            + (_stat(output, ("sat-propagations-nary",)) or 0)
        ),
        "proof_size_bytes": proof_size,
        "proof_checker": checker_status,
        "log": str(log_path.relative_to(root)),
    }
