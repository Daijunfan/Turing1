# Turing1 v0.3 多态克隆上升参数证伪与 Morphon 合成报告

## 最不利的发现

1. 自动合成得到 3 个满足 clause-level、无 scope grouping、两代递归出生和扰动鲁棒性条件的 Morphon，但它们全部是局部 `UNSAT`。因此任何组合族都含常数大小反证，不能承载渐近分离。
2. bijunctive Morphon 在禁止递归出生时仍成功；全部三个 Morphon 的随机轨迹都能稳定成功，其中多个种子达到最优两次出生。必要因果条件不成立。
3. path/tree/grid/expander/Tseitin-core 的 15 个组合公式都有 107–517 byte 的独立验证 DRAT，外部骨架被局部矛盾完全短路。
4. 找到的 `12` 个参数反序仍只是有限证据。没有 joinwidth、backdoor-treewidth 或 recursive-backdoor-depth 的符号无界下界。

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

`results/parameter_relations.csv` 对 `35` 个小实例保存 primal/incidence treewidth、induced width、linear/general joinwidth、五类 strong backdoor、backdoor-treewidth、depth 和 recursive depth，所有值带 EXACT/UNKNOWN 状态。有限反例位于 `counterexamples/parameter_relations/`。相同图不同语义对：`True`。

## 无限族与 lifting

当前组合族被局部矛盾否定。`theory/LIFTING_FEASIBILITY.md` 明确记录功能性、可满足性保持和无局部反证条件均失败。没有从有限 DRAT 数据宣称指数下界。

## 决策

**NO_SEPARATION_FOUND**

这不是 `REDUCE_TO_EXISTING_PARAMETER`：C3 仅否定字面等价，尚未证明 CAF 严格归约到 joinwidth/backdoor 参数。也绝不满足 `PASS_TO_SEPARATION_THEOREM`：没有有效无限族、无界下界或可信 lifting gadget。
