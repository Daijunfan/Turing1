# MORPH-CSP / MORPH-SAT 研究报告

## 0. 结论先行

本轮工作形成了一个可以运行、可以证伪、可以独立检查的算法原型：

> **MORPH-CSP：形态发生式多态编译器**  
> 首个实现：**MORPH-SAT**

输入只有普通 CNF。系统不预先知道其中是否隐藏 XOR、2-SAT、Horn、门电路或其他结构。它先把孤立子句恢复为局部关系，再通过受宽度约束的精确连接—投影反复出生宏关系，持续测量活动关系是否形成共同多态性；一旦某种共同秩序达到 1，系统就在运行中选择并编译出相应的精确算法。

目前已经支持：

- affine / minority → GF(2) 高斯消元；
- bijunctive / majority → 2-SAT 强连通分量；
- Horn / AND → 前向链式推理；
- dual-Horn / OR → 对偶前向链式推理；
- 0-valid / 1-valid → 直接构造模型。

在声明的验证范围内，所有决定性答案均被重新检查；没有证据时返回 `UNKNOWN`。因此这里的“100% 验证成功”具有严格含义：**对本报告列出的有限实验集，所有 SAT 模型逐子句成立，所有 UNSAT 证明可重放到 `0=1`，所有可穷举实例与真值完全一致。** 它不表示已经证明任意 CNF 都可高效求解，也不表示能够保证未来获得图灵奖。

---

## 1. 从原始灵感到可计算对象

### 1.1 孤立

普通 CNF 给出一组子句。对共享完全相同变量域的一组子句，枚举其小范围真值表，得到局部关系：

\[
R_i\subseteq\{0,1\}^{S_i}.
\]

这些关系最初互相孤立，可能分别表现为 AND、OR、NOT、单位约束或完全不同的局部语义。

### 1.2 联系

选择变量 \(x\)，取所有包含 \(x\) 的活动关系：

\[
R_{i_1},\ldots,R_{i_k}.
\]

出生一个新关系：

\[
R'(B)=\exists x\;\bigwedge_{j=1}^{k}R_{i_j}(B_j,x),
\]

其中 \(B\) 是父关系变量并集去掉 \(x\) 后的边界。随后以 \(R'\) 替代这些父关系。

这是精确 join-project，不是统计近似，也不是神经网络猜测。

### 1.3 秩序

对每个布尔运算/多态 \(p\)，定义运行时序参量：

\[
\Omega_p(t)=
\frac{
|\{R\in\mathcal R_t:p\in\operatorname{Pol}(R)\}|
}{|\mathcal R_t|}.
\]

当前实现测量：

- minority / XOR；
- majority；
- AND；
- OR；
- 常数 0；
- 常数 1。

当某个支持多项式算法的 \(p\) 满足：

\[
\Omega_p(t)=1,
\]

当前活动实例获得共同计算语言。

### 1.4 涌现

系统停止继续消元，并按刚刚形成的共同秩序自动生成后端：

\[
\text{关系组织}
\Longrightarrow
\text{算法选择}
\Longrightarrow
\text{全局求解能力}.
\]

因此，涌现对象不是一幅图案，而是**原始异质关系集合不具备、经过局部出生后才获得的全局算法可解性**。

---

## 2. 新理论对象

### 2.1 形态宽度

给定实例 \(I\) 和支持的可解多态集合 \(\mathcal P\)，定义：

\[
\operatorname{MW}_{\mathcal P}(I)
=
\min_{\tau}
\max_{R\text{ born in }\tau}\operatorname{arity}(R),
\]

其中 \(\tau\) 遍历所有精确局部融合轨迹，并要求轨迹在某个时刻使某个 \(p\in\mathcal P\) 成为所有剩余关系的共同多态性。

它与树宽不同：树宽型消元要求一直消元到问题被完全动态规划解决；形态宽度允许在中途发现新的代数秩序，然后切换算法。

当前实验只给出了轨迹相关的上界和阈值证据，尚未对大型实例精确计算全局最小 \(\operatorname{MW}\)。

### 2.2 涌现可解前沿

定义：

\[
\mathfrak T(I)=
\operatorname{ParetoMin}
\{(w,b,d,c,s)\},
\]

其中：

- \(w\)：最大宏关系元数；
- \(b\)：关系出生次数；
- \(d\)：最大出生深度；
- \(c\)：发现与分类工作量；
- \(s\)：最终后端求解工作量。

这把“发明表示”从一句哲学描述变成资源向量。

### 2.3 计算语言相变

对固定局部规则和宽度预算 \(w\)，考察：

\[
\Omega_p(t;w).
\]

若 \(w<w_c\) 时任何支持类都无法达到 1，而 \(w\ge w_c\) 时某个序参量跃迁到 1，则形成轨迹上的**形态宽度阈值**。

本轮已观察到一个明确实例：宏元数上限 2–5 时 affine 没有形成；上限从 5 增至 6 后，最终 affine 序参量从 0.1935 变为 1.0。

---

## 3. 算法

### 3.1 无标签关系恢复

对于元数不超过 \(a_0\) 的同域子句块：

1. 枚举 \(2^{|S|}\) 个局部赋值；
2. 保留满足块中全部子句的赋值；
3. 得到精确关系 \(R\)；
4. 通过闭包测试判定其 Schaefer 类；
5. 生成与真值表精确等价的后端表示。

分类是语义的，不依赖变量名、子句顺序、文字顺序或生成器标签。

### 3.2 精确关系出生

候选变量必须满足：

\[
\left|\bigcup_{R\ni x}\operatorname{scope}(R)\setminus\{x\}\right|
\le w.
\]

系统连接所有邻接关系并投影 \(x\)。每次出生记录：

- 父关系 ID；
- 被消除变量；
- 新边界；
- 完整允许元组；
- 深度；
- 原始关系祖先集合。

### 3.3 自适应轨迹

同一个实例可能存在多种合法出生顺序。当前原型采用：

1. 优先最小新边界；
2. 再按父关系数量、父关系总元数排序；
3. 对同分变量使用多个确定性散列顺序；
4. 若没有形成秩序，可尝试略大的宽度预算；
5. 首个获得共同可解类的精确轨迹被采用。

这不是随机正确性算法。不同轨迹只影响是否在预算内发现秩序，不影响每一步语义。

### 3.4 后端编译

#### affine

对每个关系恢复等价线性方程：

\[
A_i x=b_i\pmod 2.
\]

全局增量 GF(2) 消元记录每次 XOR 的父节点、深度和来源。UNSAT 时输出若干局部方程的 XOR 组合，最终得到：

\[
0=1.
\]

#### bijunctive

为每个关系生成与其真值表完全等价的单位/二元子句，构造蕴含图并运行 SCC。

#### Horn / dual-Horn

生成等价 Horn 表示，运行最小模型前向链；dual-Horn 使用对偶变换。

### 3.5 反向模型重建

若残余后端给出边界赋值，则逆序遍历出生 DAG。每一步根据：

\[
R'(B)=\exists x\bigwedge_iR_i(B_i,x)
\]

枚举 \(x\in\{0,1\}\)，选取满足所有父关系的见证。最终模型必须再次逐子句通过原始 CNF。

---

## 4. 正确性

### 命题 1：单步等可满足性

将所有包含 \(x\) 的关系替换为：

\[
R'(B)=\exists x\bigwedge_iR_i(B_i,x)
\]

后，新实例与原实例在剩余变量上具有相同投影解集，因此二者等可满足。

### 命题 2：轨迹正确性

由命题 1 归纳，任意有限精确出生轨迹保持可满足性；逆序见证选择能够恢复原实例模型。

### 命题 3：后端正确性

若所有残余关系共享：

- minority，则它们是 affine 关系，可用 GF(2) 线性代数；
- majority，则它们是 bijunctive，可编译为 2-CNF；
- AND，则它们是 Horn；
- OR，则它们是 dual-Horn。

每个局部编译结果在代码中重新枚举并与原关系真值表比较。

### 命题 4：端到端证书

UNSAT 检查器不信任求解器内部状态。它：

1. 校验 CNF 哈希；
2. 从原始子句重新恢复初始关系；
3. 重放每次 join-project；
4. 检查最终线性方程确由宏关系蕴含；
5. 重放方程 XOR，验证最终系数为 0、右端为 1。

---

## 5. 实验设置

环境记录在 `results/validation_summary.json`：

- Python 3.13.5；
- Linux 6.18.35 x86-64；
- 5 个可见 CPU；
- Z3 动态库 4.13.3-1；
- 主求解器为纯 Python，GF(2) 行使用 Python 整数位集。

所有随机过程使用固定种子。原始逐实例结果保存在 CSV，不只保留汇总数据。

隐藏处理包括：

- 全局变量置换；
- 变量坐标随机取反；
- 子句顺序打乱；
- 子句中文字顺序打乱；
- 删除 XOR、图、门类别、关系边界等元数据。

门组织基准只输出普通 AND、OR、NOT、常量门的紧凑 CNF；目标 affine 关系必须通过递归融合形成。

---

## 6. 正确性结果

### 6.1 穷举对拍

| 项目 | 数量 |
|---|---:|
| 随机 6 变量 CNF | 5,000 |
| MORPH-SAT 给出决定性答案 | 760 |
| 与完全穷举一致 | 760/760 |
| 内部验证通过 | 760/760 |
| 错误答案 | 0 |
| 安全返回 UNKNOWN | 4,240 |

### 6.2 四个隐藏语言家族

| 家族 | 实例 | 正确 | 验证 | Z3 决定性对拍一致 |
|---|---:|---:|---:|---:|
| 直接隐藏 affine | 40 | 40 | 40 | 40/40 |
| 门融合 affine | 42 | 42 | 42 | 42/42 |
| 门融合 2-SAT | 30 | 30 | 30 | 30/30 |
| 门融合 Horn | 30 | 30 | 30 | 30/30 |
| **合计** | **142** | **142** | **142** | **142/142** |

另有 36 个独立跨规模 SAT/UNSAT 实例，覆盖 2-SAT 与 Horn，两侧均为 36/36 正确并验证。

### 6.3 负对照

构造 200 个随机精确 3-CNF，规模为 50/100 变量、密度约 4.26：

- 直接语言识别：200/200 `UNKNOWN`；
- 受宽度融合：200/200 `UNKNOWN`；
- 没有错误决定性答案；
- Z3 在给定上限内对 200/200 给出 SAT/UNSAT。

这证明原型不会因为“必须成功”而伪造一个支持语言。

---

## 7. 非玩具规模结果

### 7.1 直接隐藏 affine

每个局部器官由普通全宽 CNF 子句编码，所有语义标签删除。

| 器官数 | 变量 | 子句 | MORPH 中位秒，3 个种子 | Z3，2 秒上限 |
|---:|---:|---:|---:|---:|
| 16 | 56 | 448 | 0.0124 | 3/3 完成 |
| 32 | 112 | 896 | 0.0244 | 3/3 完成 |
| 64 | 224 | 1,792 | 0.0488 | 1/3 完成 |
| 128 | 448 | 3,584 | 0.0953 | 0/3 完成 |
| 256 | 896 | 7,168 | 0.1909 | 0/3 完成 |
| 512 | 1,792 | 14,336 | 0.3876 | 未运行 |
| 1,024 | 3,584 | 28,672 | 0.7726 | 未运行 |
| 2,048 | 7,168 | 57,344 | 1.6036 | 未运行 |
| 4,096 | 14,336 | 114,688 | 3.2039 | 未运行 |
| 8,192 | 28,672 | 229,376 | **6.7443** | 未运行 |

对测试尺度中位数拟合：

\[
T(n)\propto n^{1.0080},\qquad R^2=0.999862.
\]

这是经验缩放，不是渐近复杂性证明。

最大 SAT 旗舰同样包含 28,672 变量、229,376 子句，7.2469 秒得到模型，独立检查器验证全部子句。

### 7.2 异质 AND/OR/NOT 组织

| 器官数 | 变量 | 子句 | 融合中位秒 | 中位出生数 | Z3，2 秒上限 |
|---:|---:|---:|---:|---:|---:|
| 8 | 76 | 184 | 0.0371 | 71 | 3/3 完成 |
| 16 | 152 | 368 | 0.1043 | 139 | 3/3 完成 |
| 32 | 304 | 736 | 0.3562 | 280 | 3/3 完成 |
| 64 | 608 | 1,472 | 1.1868 | 558 | 2/3 完成 |
| 96 | 912 | 2,208 | 2.6353 | 837 | 0/3 完成 |
| 128 | 1,216 | 2,944 | 4.4972 | 1,112 | 0/3 完成 |
| 160 | 1,520 | 3,680 | 7.7058 | 1,390 | 未运行 |
| 192 | 1,824 | 4,416 | **9.6948** | **1,679** | 未运行 |

拟合：

\[
T(n)\propto n^{1.7831},\qquad R^2=0.998005.
\]

最大 SAT 门组织实例也在 9.6712 秒得到模型，并通过原始 4,416 个子句检查。

这里不能把 2 秒超时解释成对所有工业求解器的胜利。Z3 只是本环境可用的独立基线；CaDiCaL、CryptoMiniSat、xMapleLCM 等现代专用求解器尚未在同一机器上完成对照。

---

## 8. 秩序涌现证据

### 8.1 初态没有共同支持语言

608 变量、1,472 子句实例：

| 时刻 | 关系数 | affine 比例 | bijunctive 比例 | Horn 比例 | dual-Horn 比例 | 共同类 |
|---|---:|---:|---:|---:|---:|---|
| 初始 | 1,344 | 0.142857 | 0.714286 | 0.654762 | 0.675595 | 空集 |
| 558 次融合后 | 18 | **1.0** | 0 | 0 | 0 | affine |

因此算法不是从一开始就检测到现成 XOR；它从异质门关系的局部连接中形成了新的实例级 affine 表示。

### 8.2 宽度阈值

固定 304 变量、736 子句实例和固定轨迹规则：

| 最大宏元数 | affine 是否形成 | 最终 affine 序参量 | 出生数 | 剩余关系 |
|---:|---:|---:|---:|---:|
| 2 | 否 | 0.0827 | 64 | 544 |
| 3 | 否 | 0 | 192 | 232 |
| 4 | 否 | 0.0902 | 234 | 122 |
| 5 | 否 | 0.1935 | 272 | 31 |
| 6 | **是** | **1.0** | 282 | 9 |
| 7 | 是 | 1.0 | 282 | 9 |
| 8 | 是 | 1.0 | 282 | 9 |

它证明了当前局部策略存在一个可重复的计算能力阈值；尚未证明宽度 6 是所有可能轨迹中的全局最小值。

### 8.3 轨迹消融

40 个 16 器官实例：

- 单一确定性顺序：37/40 成功；
- 四条确定性候选轨迹：39/40 成功；
- 对剩余实例启用完整八轨迹策略后也成功；
- 初始无融合版本全部没有共同 affine 语言。

这表明“联系形成顺序”会决定是否在固定宽度中形成秩序，也说明下一阶段需要把轨迹搜索本身理论化。

---

## 9. 独立证书

### 9.1 最大直接 UNSAT 旗舰

- 28,672 变量；
- 229,376 子句；
- 重新验证 13,286 条局部方程；
- CNF SHA-256 匹配；
- 最终系数权重 0；
- 最终右端 1；
- `verified=true`。

### 9.2 最大融合 UNSAT 旗舰

- 1,824 变量；
- 4,416 子句；
- 从原始 CNF 重新恢复 4,032 个初始关系；
- 精确重放 1,679 次融合；
- 验证 50 条最终蕴含方程；
- 最终得到 \(0=1\)；
- `verified=true`。

测试套件还包含证书篡改检测：修改融合证明后检查器拒绝接受。

---

## 10. 与最近邻工作的精确关系

### Schaefer 与 CSP 多态理论

Schaefer 定理按固定布尔约束语言给出 P/NP-complete 二分；通用代数理论用多态性刻画 CSP 复杂性。MORPH-CSP 不提出新的固定语言分类，而是研究：**一个具体异质实例能否在执行过程中通过精确投影变换为拥有共同多态性的残余实例。**

### Bucket / variable elimination

join-project 是经典变量消元。差异不在单步算子，而在停止准则和资源对象：传统消元通常受树宽控制并持续到完全求解；MORPH-CSP 在中途测量代数序参量，并在形成共同语言时改用与树宽不同的专用算法。

因此，本原型应被描述为一个新闭环：

\[
\text{bounded exact elimination}
+\text{online semantic polymorphism detection}
+\text{runtime backend synthesis}
+\text{replayable certificates}.
\]

不能宣称首次使用变量消元或首次检测 XOR。

### SAT backdoor

Backdoor 通过给少量变量赋值，使每个或某个残余公式落入 Horn、2-CNF 等基础类。MORPH-CSP 不分支赋值，而是通过存在量化和关系出生改变表示；它寻找的是低宽融合轨迹，而不是变量赋值集合。

### BVA、扩展变量与 ERCL

BVA/Extended Resolution 通过新变量压缩或增强证明；ERCL 根据单次冲突图中的 Dual Implication Points 动态引入扩展变量。MORPH-CSP 当前主要出生的是精确宏关系，并发现其共同代数语言；它不是基于冲突图的扩展子句学习。

### 工业语义检测

现代 CaDiCaL 已包含 AND/XOR/ITE gate extraction、BVA 和局部语义定义检测；CryptoMiniSat 会检测/接收 XOR 并运行 Gauss-Jordan 消元。它们说明“隐藏结构自动恢复”本身不是新命题。

当前候选原创点必须严格限定为：

> 把**共同多态性的形成过程**作为运行时状态和序参量；允许异质关系通过多代精确 pp 风格融合形成新的实例级可解语言；随后由该语言自动生成后端，并为整个形成轨迹给出证书。

本轮检索没有找到同时实现这四点的系统，但这不是法律意义或数学意义上的绝对新颖性证明。

---

## 11. 是否已经达到“图灵奖级别”

### 已经成立

1. 新的、可命名的计算对象：多态序参量、形态宽度、涌现可解前沿。
2. 一个非玩具算法原型：约 2,248 行核心 Python，带多个精确后端、模型重建和双层证书。
3. 明确的机制证据：初始无共同语言，局部融合后共同 affine/2-SAT/Horn 出现。
4. 决定性正确性证据：穷举、独立 Z3、原 CNF 模型检查、证明重放。
5. 非玩具规模：最高 28,672 变量、229,376 子句。
6. 可证伪负结果：普通随机 3-SAT 返回 UNKNOWN；轨迹和宽度不足会失败。

### 尚未成立

1. 尚无自然问题族上的严格指数—多项式分离定理。
2. 尚未证明形态宽度与 treewidth、backdoor size、proof width 等参数严格不可约。
3. 当前局部轨迹策略并非完备：存在低宽成功轨迹时，它不保证必然找到。
4. 尚未在 SAT Competition 全套基准和最新专用求解器上比较。
5. 当前只覆盖布尔 Schaefer 类，没有扩展到有限域、整数线性、图半环、程序不变量等更广语言。

因此，诚实结论是：

> **已经成功做出一个可独立验证、具有基础研究潜力的非玩具算法原型；尚未完成足以称为图灵奖级成果的理论分离。**

---

## 12. 真正的“图灵门”

下一篇理论主论文必须完成下列结果之一。

### 门 1：参数分离

构造自然实例族 \(I_n\)，证明：

\[
\operatorname{MW}(I_n)=O(1),
\]

但：

\[
\operatorname{tw}(I_n)=\Omega(n),
\qquad
\operatorname{Backdoor}(I_n)=\Omega(n),
\]

并证明一个统一局部策略在多项式时间内找到该轨迹。

### 门 2：证明复杂性分离

证明固定词汇 CDCL/Resolution 对自然 \(F_n\) 需要：

\[
2^{\Omega(n)}
\]

资源，而 MORPH-CSP 在常数形态宽度和多项式出生数内自动形成 affine 或其他语言并输出多项式证书。

### 门 3：跨领域统一

同一“多态发现—后端生成”机制，不加人工领域标签地覆盖至少：

- 布尔 SAT；
- 有限域线性约束；
- 差分约束/最短路；
- 图可达性或流；
- 程序验证不变量。

若这些成立，贡献将不再是一个 SAT 技巧，而是：

> **计算机在执行中发现问题所服从的代数，并由此生成算法。**

---

## 13. 论文定位

当前原型适合形成一篇算法与系统论文，标题可为：

> **MORPH-CSP: Compiling Emergent Polymorphisms from Heterogeneous Constraints**

如果完成严格参数/证明复杂性分离，理论主论文可为：

> **Emergent Tractability as a Computational Resource**

核心三条贡献应是：

1. 提出形态宽度和涌现可解前沿；
2. 给出局部关系出生到共同多态性的构造性算法与正确性证书；
3. 证明它相对固定表示或经典结构参数的严格复杂性分离。

---

## 14. 参考研究

1. T. J. Schaefer, *The Complexity of Satisfiability Problems*, STOC 1978, DOI 10.1145/800133.804350.
2. M. Bodirsky et al., *Complexity Classification Transfer for CSPs via Algebraic Products*, arXiv:2211.03340.
3. M. Chen and M. Larose, *Asking the Metaquestions in Constraint Tractability*, arXiv:1604.00932.
4. S. Gaspers and S. Szeider, *Backdoors to Satisfaction*, arXiv:1110.6387.
5. M. C. Cooper et al., *Variable Elimination in Binary CSPs*, JAIR 2019.
6. S. Buss, J. Chung, V. Ganesh, A. Oliveras, *Extended Resolution Clause Learning via Dual Implication Points*, arXiv:2406.14190; LMCS 2026.
7. R. E. Bryant et al., *Generating Extended Resolution Proofs with a BDD-Based SAT Solver*, arXiv:2105.00885.
8. CaDiCaL release notes, versions 2.2–3.0.1, semantic gate extraction and BVA.
9. CryptoMiniSat documentation, XOR recovery and Gauss-Jordan elimination.
10. L. Chew et al., *Hardness of Random Reordered Encodings of Parity for Resolution and CDCL*, arXiv:2402.00542.

---

## 15. 可复现文件

核心结果：

- `results/validation_summary.json`
- `results/direct_affine_scaling.csv`
- `results/fusion_affine_scaling.csv`
- `results/cross_language_emergence.csv`
- `results/polymorphism_order_trace.csv`
- `results/width_threshold.csv`
- `results/random_3sat_negative_control.csv`
- `results/adaptive_trajectory_ablation.csv`

最大 UNSAT：

- `results/flagship_direct_8192.cnf`
- `results/flagship_direct_8192.cert.json`
- `results/flagship_gate_fusion_192.cnf`
- `results/flagship_gate_fusion_192.cert.json`

最大 SAT：

- `results/flagship_direct_8192_sat.cnf`
- `results/flagship_direct_8192_sat.model.json`
- `results/flagship_gate_fusion_192_sat.cnf`
- `results/flagship_gate_fusion_192_sat.model.json`

检查器：

- `verify_certificate.py`
- `verify_fusion_certificate.py`
- `verify_model.py`
