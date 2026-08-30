# MORPH-SAT v0.2 Separation and Falsification Audit

## 最不利于 MORPH 的发现

1. **机制没有与有界变量消元分离。** v0.1 的核心步骤逐字等价于：选择变量，join 全部 incident relations，再 existentially project，并递归使用新关系。这是 truth-table 表示下的 bucket elimination/BVE；“出生”是中间因子/消元子，名称变化不构成新推理规则。
2. **现代基线触发强制否定判据 1：True。** 触发族与求解器：`[{"family": "layer_a_v01_regression", "solver": "cadical", "baseline_median_seconds": 0.006862853973871097, "morph_median_seconds": 0.07372308350750245, "baseline_over_morph": 0.09308962196586225}, {"family": "layer_a_v01_regression", "solver": "cryptominisat5", "baseline_median_seconds": 0.0066651249944698066, "morph_median_seconds": 0.07372308350750245, "baseline_over_morph": 0.09040757219265698}, {"family": "layer_b_heterogeneous_tseitin", "solver": "cadical", "baseline_median_seconds": 0.008791792031843215, "morph_median_seconds": 0.08567937498446554, "baseline_over_morph": 0.10261270035451646}, {"family": "layer_b_heterogeneous_tseitin", "solver": "cryptominisat5", "baseline_median_seconds": 0.00838241699966602, "morph_median_seconds": 0.08567937498446554, "baseline_over_morph": 0.09783471227685578}, {"family": "layer_c_heterogeneous_tseitin", "solver": "cadical", "baseline_median_seconds": 0.007288437511306256, "morph_median_seconds": 0.32672987499972805, "baseline_over_morph": 0.02230722706735135}, {"family": "layer_c_heterogeneous_tseitin", "solver": "cryptominisat5", "baseline_median_seconds": 0.0071761249855626374, "morph_median_seconds": 0.32672987499972805, "baseline_over_morph": 0.021963479726390525}, {"family": "layer_d_random_reordered_parity", "solver": "cadical", "baseline_median_seconds": 0.00764054199680686, "morph_median_seconds": 0.047059395466931164, "baseline_over_morph": 0.16235954416745327}, {"family": "layer_d_random_reordered_parity", "solver": "cryptominisat5", "baseline_median_seconds": 0.007776562531944364, "morph_median_seconds": 0.047059395466931164, "baseline_over_morph": 0.16524994541013574}, {"family": "layer_d_resolution_tseitin_reference", "solver": "cadical", "baseline_median_seconds": 0.008283250004751608, "morph_median_seconds": 0.046153958479408175, "baseline_over_morph": 0.17946997998984685}, {"family": "layer_d_resolution_tseitin_reference", "solver": "cryptominisat5", "baseline_median_seconds": 0.007436000014422461, "morph_median_seconds": 0.046153958479408175, "baseline_over_morph": 0.16111294154194966}]`。因此现有性能结果可由现代门提取、XOR 恢复、Gaussian elimination 或普通 CDCL/BVE 解释，不能作为机制新颖性证据。
3. **关闭 exact-scope recovery 存在宽度 4 的最小失败反例：True。** 这说明在受限轨迹下当前原型可依赖输入分块；C 层虽然强迫多步 join-project，但这仍是标准消元，而不是独立的代数发现规则。
4. 递归出生相对“出生关系不可再参与”形成率增益为 `0.725`，但该消融恰好是在比较递归 BVE 与非递归一次性消去，不能证明超出普通 BVE。提前停止平均减少 `5.26` 次出生，同样只是识别到目标语言后的 stopping rule。

## 审计设计与冻结协议

- 独立分支：`separation-audit-v0.2`；v0.1 文件、证书与 `run_checks.sh` 保留。
- A/B/C/D 层共生成 `240` 个实例；核心层每个 SAT/UNSAT 方向 10 个独立种子、规模 4/8，B 与 D 另用冻结规模 16/32 做最大规模留出预测。
- B 层逐个 XOR 独立抽取 NAND/NOR/MUX/MAJ/AND-OR-NOT 模板，并随机极性、变量、子句、辅助结构；C 层把每条局部子句改写为两级 existential chain。
- C 层已自动验证每个 exact-scope 初始块最多只有一条子句，不能直接恢复完整门关系；D 层明确标记为 Resolution 困难参考族且 `true_multigeneration_candidate=false`，与 B/C 的多代形态候选分开统计。
- 每个 XOR 模板已穷举验证；所有完整实例由独立 CaDiCaL 结果核对预期。测试集参数在生成前冻结，脚本不含测试后调参路径。

## 基线与证明

- CaDiCaL 3.0.1：default、congruence off/on、BVE off/on、factor off/on、elimdef off/on。
- Kissat 4.0.4：default。
- CryptoMiniSat 5.14.7：default、XOR recovery off/on、Gaussian off/on、两者共同 off/on。
- Z3 5.1.0：default。不是只与 Z3 比较。
- 本机：`Apple M5 Pro`，内存 `51539607552` bytes，限制 `10.0` s / `4096` MiB。Darwin 对降低 `RLIMIT_AS` 可能拒绝执行，因此内存上限记为请求值，同时始终记录实际 RSS；本轮实际 RSS 均远低于上限。
- CaDiCaL/Kissat 的文本 DRAT 由独立 drat-trim 检查；聚合验证证明数 `1080`。CryptoMiniSat 和 Z3 未把内部结论冒充独立证明。

详细版本、commit、编译参数、运行参数见 `results/toolchain.json`；每次运行的参数、conflicts、decisions、propagations、内存、证明大小见 `results/raw_runs.csv`。

### 核心异质编码比较

| 族 | 方法 | 配置 | decisive/runs | median s |
|---|---|---:|---:|---:|
| layer_b_heterogeneous_tseitin | cadical | bve_off | 40/40 | 0.007147 |
| layer_b_heterogeneous_tseitin | cadical | bve_on | 40/40 | 0.006881 |
| layer_b_heterogeneous_tseitin | cadical | congruence_off | 40/40 | 0.007244 |
| layer_b_heterogeneous_tseitin | cadical | congruence_on | 40/40 | 0.007297 |
| layer_b_heterogeneous_tseitin | cadical | default | 60/60 | 0.008792 |
| layer_b_heterogeneous_tseitin | cryptominisat5 | default | 60/60 | 0.008382 |
| layer_b_heterogeneous_tseitin | cryptominisat5 | xor_and_gaussian_off | 40/40 | 0.007050 |
| layer_b_heterogeneous_tseitin | cryptominisat5 | xor_and_gaussian_on | 40/40 | 0.007280 |
| layer_b_heterogeneous_tseitin | kissat | default | 60/60 | 0.008301 |
| layer_b_heterogeneous_tseitin | morph | current_min_scope | 31/60 | 0.085679 |
| layer_b_heterogeneous_tseitin | z3 | default | 60/60 | 0.007737 |
| layer_c_heterogeneous_tseitin | cadical | bve_off | 40/40 | 0.006857 |
| layer_c_heterogeneous_tseitin | cadical | bve_on | 40/40 | 0.007267 |
| layer_c_heterogeneous_tseitin | cadical | congruence_off | 40/40 | 0.007227 |
| layer_c_heterogeneous_tseitin | cadical | congruence_on | 40/40 | 0.007674 |
| layer_c_heterogeneous_tseitin | cadical | default | 40/40 | 0.007288 |
| layer_c_heterogeneous_tseitin | cryptominisat5 | default | 40/40 | 0.007176 |
| layer_c_heterogeneous_tseitin | cryptominisat5 | xor_and_gaussian_off | 40/40 | 0.007001 |
| layer_c_heterogeneous_tseitin | cryptominisat5 | xor_and_gaussian_on | 40/40 | 0.007371 |
| layer_c_heterogeneous_tseitin | kissat | default | 40/40 | 0.006735 |
| layer_c_heterogeneous_tseitin | morph | current_min_scope | 27/40 | 0.326730 |
| layer_c_heterogeneous_tseitin | z3 | default | 40/40 | 0.006926 |

MORPH 在全部 `240` 次中给出 `198` 次 SAT/UNSAT，剩余为显式 `UNKNOWN`，没有把未知计为正确。关闭门/XOR相关机制后的现代求解器仍普遍完成，说明负结论并不依赖挑选最强配置。

## 精确 MorphWidth 与最近邻参数

小实例使用 iterative deepening、穷尽分支、memoization 和宽度/出生次数/深度的 branch-and-bound；失败宽度全部来自耗尽状态空间，并用不共享 memo 的暴力枚举交叉检查。共 `20` 个精确实例。MorphWidth 与 induced width 在全部实例恒等：`False`；全部样本满足 `MorphWidth <= induced width`，这是当前必须保留的简单上界猜想。严格不同序覆盖参数：`["induced_width", "affine_strong_backdoor_size", "horn_strong_backdoor_size", "2cnf_strong_backdoor_size", "scattered_strong_backdoor_size", "affine_backdoor_depth", "horn_backdoor_depth", "2cnf_backdoor_depth", "scattered_backdoor_depth", "affine_backdoor_treewidth", "horn_backdoor_treewidth", "2cnf_backdoor_treewidth", "scattered_backdoor_treewidth"]`；首个反例：`{"kind": "parameter_order_reversal", "parameter": "induced_width", "left": "random_exact.n4.s0", "right": "random_exact.n5.s6", "left_morph_width": 3, "right_morph_width": 0, "left_parameter": 3, "right_parameter": 4}`。

因此，严格反序反驳了“与 induced width 或 backdoor 参数恒等/单调等价”，但统一上界又不足以证明参数独立性；只支持“研究 stopping-width 的等价或分离定理”的 **PIVOT**，不支持把它直接声明为新参数。primal/incidence treewidth、完整 induced width、strong backdoor size、backdoor depth 和可行的 torso backdoor-treewidth 均在 `results/exact_parameters.csv` 中标注 exact/bounds/unavailable。

## 消融与缩放

已执行：精确最优见证、当前 min-scope、随机顺序、仅原始关系、递归出生、形成即停、完整消元、关闭 scope recovery、外来顺序、候选评分打乱。图见 `figures/ablation.png` 与 `figures/exact_vs_heuristic_width.png`。

配对 bootstrap（2,000 次）中，递归出生相对只允许原始关系的形成率差为 `0.725`，95% CI `[0.625, 0.813]`；完整消元相对提前停止的出生数差为 `5.263`，95% CI `[4.825, 5.725]`。两者可重复，但前者就是递归 bucket elimination，后者就是 stopping rule，均未与普通 BVE 分离。

缩放同时拟合 `log T = a log n + b` 与 `log T = c n + d`，最大规模留出，300 次 bootstrap 置信区间，AIC 与留出误差联合判别，并保存 PAR-2/PAR-10。`UNKNOWN` 的实际终止时间保留在运行时拟合中，同时另列 decisive-status 数，绝不把 `UNKNOWN` 当求解成功。模型组数 `10`；没有用 log-log R² 宣称多项式复杂度。

## 判定

**PIVOT_PARAMETER**

逐条机器可读依据见 `decision.json`。负结果、超时、失败证明检查和全部种子均保留。

## 最后三个问题

**A. 当前 MORPH-SAT 是否只是“有界变量消元 + 已知约束语言识别”？**  是。现有实现与证据尚未给出超出该组合的独立推理机制。

**B. 当前 MorphWidth 是否提供了已有参数无法表达的新次序？**  在本次精确小实例上找到了至少一个不同序实例对，但只足以支持 PIVOT_PARAMETER，尚不足以证明不可由已有参数表达。

**C. 是否已经存在值得进入严格复杂性定理阶段的显式候选实例族？**  否。异质 B/C 族只有部分种子形成目标结构，现代 SAT/XOR 基线达到同等或更低资源，且递归收益可由普通递归 BVE 解释。
