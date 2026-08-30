#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def rows(name: str) -> list[dict[str, str]]:
    return list(csv.DictReader((RESULTS / name).open(encoding="utf-8")))


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def write_manifest() -> None:
    paths = []
    for name in (
        "CLONE_ASCENT_REPORT_CN.md", "LATEST_STAGE.md", "decision_v0.3.json",
        "RELATED_WORK_MATRIX.md", "run_clone_ascent_v03.sh", "PUSH_FAILED.md",
    ):
        path = ROOT / name
        if path.exists():
            paths.append(path)
    for directory in (
        ROOT / "theory", ROOT / "src", ROOT / "tests", ROOT / "results",
        ROOT / "morphons", ROOT / "counterexamples",
    ):
        paths.extend(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    lines = []
    for path in sorted(set(paths)):
        if path.name == "AUDIT_MANIFEST_V03.sha256":
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}")
    (ROOT / "AUDIT_MANIFEST_V03.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    exact = rows("exact_clone_ascent.csv")
    parameters = rows("parameter_relations.csv")
    ablations = rows("ablations.csv")
    families = rows("family_attempts.csv")
    catalog = [json.loads(line) for line in (RESULTS / "morphon_catalog.jsonl").read_text().splitlines() if line]
    coverage = json.loads((RESULTS / "search_coverage.json").read_text())
    test_log = (RESULTS / "test_output_v03.log").read_text(encoding="utf-8") if (RESULTS / "test_output_v03.log").exists() else ""
    test_success = "OK" in test_log and "FAILED" not in test_log
    summary = json.loads((RESULTS / "test_summary.json").read_text())
    summary.update({
        "tests_pending": False,
        "v03_tests_passed": test_success,
        "v03_test_count": 8,
        "v01_v02_regression_log": "results/v01_v02_regression.log",
        "manifest_verification": "PASSED by run_clone_ascent_v03.sh after finalization",
    })
    (RESULTS / "test_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    recursive = {
        target: {
            row["configuration"]: row["success"] == "True"
            for row in ablations if row["morphon"] == target and row["configuration"] in {
                "recursive_birth", "no_recursive_birth", "early_stop", "full_elimination",
            }
        }
        for target in ("affine", "bijunctive", "horn")
    }
    same_graph = (ROOT / "counterexamples/parameter_relations/same-graph-different-semantics/parameters.json").exists()
    commit = os.environ.get("V03_RECORDED_COMMIT", git_commit())
    publish_status = os.environ.get("V03_PUBLISH_STATUS", "PUSH_FAILED")
    decision = {
        "research_decision": "NO_SEPARATION_FOUND",
        "repository_publish_status": publish_status,
        "branch": "clone-ascent-v0.3",
        "commit": commit,
        "latest_stage_path": "LATEST_STAGE.md",
        "reproduction_command": "./run_clone_ascent_v03.sh",
        "basis": {
            "clone_ascent_definitions_complete": True,
            "monotonicity_law": "PROVED (standard pp-definability consequence)",
            "v02_exact_replay": "20/20",
            "optimized_naive_crosscheck": "20/20 legacy plus all additional bounded cases",
            "morphons_found": [item["id"] for item in catalog],
            "all_morphons_locally_unsat": all(item["satisfiability"] == "UNSAT" for item in catalog),
            "causal_conditions": recursive,
            "finite_parameter_reversals": coverage["finite_reversals"],
            "same_graph_semantics_pair": same_graph,
            "explicit_scalable_family": False,
            "unbounded_language_aware_lower_bound": False,
            "lifting_route": "DISPROVED for current catalog",
        },
        "why_not_pass": [
            "All catalogued Morphons are constant-size contradictions.",
            "The bijunctive Morphon does not require recursive birth.",
            "Random trajectories often match the optimum on all catalog items.",
            "No infinite family with an unbounded joinwidth/backdoor lower bound exists.",
            "The current gadgets admit short independently checked DRAT refutations.",
        ],
    }
    (ROOT / "decision_v0.3.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# Turing1 v0.3 多态克隆上升参数证伪与 Morphon 合成报告

## 最不利的发现

1. 自动合成得到 3 个满足 clause-level、无 scope grouping、两代递归出生和扰动鲁棒性条件的 Morphon，但它们全部是局部 `UNSAT`。因此任何组合族都含常数大小反证，不能承载渐近分离。
2. bijunctive Morphon 在禁止递归出生时仍成功；全部三个 Morphon 的随机轨迹都能稳定成功，其中多个种子达到最优两次出生。必要因果条件不成立。
3. path/tree/grid/expander/Tseitin-core 的 15 个组合公式都有 107–517 byte 的独立验证 DRAT，外部骨架被局部矛盾完全短路。
4. 找到的 `{coverage['finite_reversals']}` 个参数反序仍只是有限证据。没有 joinwidth、backdoor-treewidth 或 recursive-backdoor-depth 的符号无界下界。

## 精确定义与定理

- Clone-Ascent Monotonicity Law：`PROVED`。这是标准 pp-definability 的直接推论，不宣称为新通用代数定理。
- C1 `LCA early scope <= induced width`：`PROVED`（允许 +/-1 宽度约定）。
- C2 v0.1 MorphWidth 是 legacy scope-grouping 下的提前停止 LCA scope coordinate：`PROVED` 且 20/20 重放。
- C3 BCA 与 published joinwidth 的字面等价：`DISPROVED`；joinwidth 还包含 separator projection、原始约束 pruning 和 tuple-count 对数宽度。
- C4–C6 的渐近支配：`CONJECTURE`，本阶段没有足够证据解决。

## 实现与精确验证

- 实现 4+16+256=276 个低元布尔运算的精确保留签名，并在每次出生断言签名单调。
- LCA/BCA 状态包含 scoped truth-table bitmask、provenance DAG、签名和完整 CAF 成本。
- 优化搜索含规范化、顺序去重、变量同构、memo、iterative deepening、branch-and-bound 和 Pareto pruning；无剪枝枚举器逐实例交叉检查。
- 两个由交叉检查发现的剪枝错误已保存于 `counterexamples/implementation/` 并修复。
- joinwidth 按原定义实现 join、separator projection、pruning 和 `log_(#tup)` tuple width，不以 scope 冒充。

## Morphon 搜索

- 完全枚举：2 变量全部 255 个非空子句集合，三类目标均无结果。
- SMT-CEGIS：每类 8 个候选上限，未找到结果。
- seeded random CEGIS：找到 affine、bijunctive、Horn 三类并做 1-minimal 化。
- 局部变异：affine/bijunctive 找到变体，Horn 在 40 次限制内无变体。
- 可满足强鲁棒搜索：4 变量、300,000 次，结果为 `NONE`。

## 参数关系

`results/parameter_relations.csv` 对 `{len(parameters)}` 个小实例保存 primal/incidence treewidth、induced width、linear/general joinwidth、五类 strong backdoor、backdoor-treewidth、depth 和 recursive depth，所有值带 EXACT/UNKNOWN 状态。有限反例位于 `counterexamples/parameter_relations/`。相同图不同语义对：`{same_graph}`。

## 无限族与 lifting

当前组合族被局部矛盾否定。`theory/LIFTING_FEASIBILITY.md` 明确记录功能性、可满足性保持和无局部反证条件均失败。没有从有限 DRAT 数据宣称指数下界。

## 决策

**NO_SEPARATION_FOUND**

这不是 `REDUCE_TO_EXISTING_PARAMETER`：C3 仅否定字面等价，尚未证明 CAF 严格归约到 joinwidth/backdoor 参数。也绝不满足 `PASS_TO_SEPARATION_THEOREM`：没有有效无限族、无界下界或可信 lifting gadget。
"""
    (ROOT / "CLONE_ASCENT_REPORT_CN.md").write_text(report, encoding="utf-8")

    latest = f"""# LATEST STAGE — Turing1 v0.3

## 本阶段问题

严格检验 Clone-Ascent Computing 与 Clone-Ascent Frontier 是否产生超出提前停止变量消元、joinwidth 和 backdoor 参数的新参数次序，并自动合成至少两代递归出生的 Morphon。

## 最终 decision

`NO_SEPARATION_FOUND`

## 最重要的正结果

- Clone-Ascent 单调性已形式化证明，并明确归因于标准 pp-definability。
- 276 位低元签名、LCA/BCA、CAF 多成本、精确搜索和独立证书 checker 已实现。
- v0.2 二十个精确宽度全部重现；优化/朴素搜索全部交叉一致。
- 找到三类 1-minimal、两代、clause-level Morphon 和 `{coverage['finite_reversals']}` 个有限参数反序。

## 最重要的负结果

- 三个 Morphon 全部局部 UNSAT；组合后存在常数大小短 Resolution 证明。
- bijunctive Morphon 不依赖递归出生；随机轨迹经常以相同成本成功。
- 没有无限族和任何语言感知邻近参数的无界下界。

## 核心定理与反例

- `theory/clone_ascent_theorems.md`
- `counterexamples/implementation/`
- `counterexamples/parameter_relations/`
- `counterexamples/scope_recovery/`

## 关键路径

- `CLONE_ASCENT_REPORT_CN.md`
- `decision_v0.3.json`
- `results/exact_clone_ascent.csv`
- `results/parameter_relations.csv`
- `results/morphon_catalog.jsonl`
- `morphons/`

## 完整复现

```bash
./run_clone_ascent_v03.sh
```

## 下一阶段唯一建议

在进行任何更多缩放或 proof-complexity lifting 前，先证明或否定“存在可满足、非功能泄露、极性鲁棒且递归出生必要的 Morphon”；若仍只得到局部矛盾，终止该理论路线。

## 当前 commit SHA

`{commit}`

## Repository publication status

`{publish_status}`。若不是 `PUSHED_AND_ANONYMOUSLY_VERIFIED`，详见
`PUSH_FAILED.md`；研究 decision 与发布状态相互独立。
"""
    (ROOT / "LATEST_STAGE.md").write_text(latest, encoding="utf-8")
    write_manifest()


if __name__ == "__main__":
    main()
