# LATEST STAGE — Turing1 v0.3

## 本阶段问题

严格检验 Clone-Ascent Computing 与 Clone-Ascent Frontier 是否产生超出提前停止变量消元、joinwidth 和 backdoor 参数的新参数次序，并自动合成至少两代递归出生的 Morphon。

## 最终 decision

`NO_SEPARATION_FOUND`

## 最重要的正结果

- Clone-Ascent 单调性已形式化证明，并明确归因于标准 pp-definability。
- 276 位低元签名、LCA/BCA、CAF 多成本、精确搜索和独立证书 checker 已实现。
- v0.2 二十个精确宽度全部重现；优化/朴素搜索全部交叉一致。
- 找到三类 1-minimal、两代、clause-level Morphon 和 `12` 个有限参数反序。

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

`23bd6fc589ba90d65b390f1a47ad4d057ea97d95`

## Repository publication status

`PUSHED_BUT_NOT_PUBLIC`。若不是 `PUSHED_AND_ANONYMOUSLY_VERIFIED`，详见
`PUSH_FAILED.md`；研究 decision 与发布状态相互独立。
