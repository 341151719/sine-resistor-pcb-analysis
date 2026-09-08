# H12 — OPA548 E/S + R5 动态耦合（组合机制）

## 为什么新增 H12

H01–H11 的统一基线把 OPA548 `E/S` 固定在 `V- + 0.6 V`（OFF）。这个前提适合排查单一错料/焊接错误，但不能回答一个不同的问题：

> V7 的 `R10=100 kΩ`、TLP185、OPA548 的有限 enable/disable 动态、R5=100 Ω 与板级寄生共同存在时，是否会打开一条此前 OFF 模型完全看不到的动态耦合路径，并自然产生实板约 100–110 kHz 的 TP8 振荡？

因此 H12 **不是新的“单一加工错误”**，而是对原模型盲区的组合机制审计。它不修改 H01–H11 的历史结论。

## 建模原则

禁止为“得到 105 kHz”而做两件事：

1. 不注入 100–110 kHz 周期源；
2. 不人为给 U4B 增加 105 kHz 极点。

主电路仍使用项目值：

- U4B：OPA1656，R15=1 kΩ，R16=39 kΩ；
- TP8 → OPA548 `+IN`：R5=100 Ω，并保留项目 PCB-aware deck 中的走线 R/L/C；
- OPA548：单位增益跟随器，R7=57.6 kΩ；
- E/S：R10=100 kΩ（V7-like，可扫 6.8 kΩ V8-like）、TLP185、R11=1 kΩ；
- J1：±5 V，470 µF + 100 nF，并显式加入供电线 R/L、ESR/ESL；
- AGND–PGND：5 mΩ + 2 nH 代理；
- 输出：R12=4.7 Ω、C4=47 nF，扬声器端默认开路。

TI OPA1656/OPA548 宏模型直接复用仓库已有副本，不在 H12 重复提交 vendor 文件。

## E/S 动态模型

官方 OPA548 宏模型的 E/S 开关接近瞬时，不适合作为 shutdown transient 的校准模型。因此 H12 在官方 OPA548 模拟核心外增加一个有限状态 wrapper：

- `V(ES)-V- <= 0.8 V`：状态向 OFF 演化；
- `V(ES)-V- >= 2.4 V`：状态向 ON 演化；
- 0.8–2.4 V：保持前一状态；
- 默认 `TON=3 µs`、`TOFF=1 µs`；
- 物理 E/S 节点保留 `R10`、参数化 `IESVAL`、pin capacitance、约 3.5 V 高端钳位代理，以及 TLP185 光电流/CCE。

`IESVAL=70 µA` 在本审计中只是参数扫描点，不应解释成 datasheet 保证最大值。

## Deck 与运行方式

- `es_dynamic_loop.cir`：TI OPA1656 + TI OPA548 的最终确认 deck。
- `es_dynamic_loop_fast.cir`：U4B 使用项目已有 ngspice-compatible surrogate，OPA548 仍为 TI 宏模型，用于 23 组机制扫描。
- `run_sweep.py`：快速扫描 R10、E/S 电流、J1 线缆电感、E/S 时延、地桥电感和一次 optocoupler enable/disable。
- `official_check/`：关键全官方宏对照 deck 和运行日志；`.dat` 波形按仓库规则不提交。
- `official_summary.csv`、`fast_sweep_summary.csv`：本次实跑摘要。

典型命令：

```bash
cd 故障假设排查_20260908/H12_OPA548_ES_R5动态耦合
mkdir -p results_h12
ngspice -b es_dynamic_loop.cir | tee official_run.log
python run_sweep.py
(cd official_check && ./run_cases.sh)
```

ngspice-42 需要本目录 `.spiceinit` 中的 PSpice 兼容设置。

## 23 组机制扫描

快速模型扫过：

- R10 = 100 kΩ / 6.8 kΩ；
- `IESVAL` = 6 / 20 / 40 / 70 µA；
- J1 cable L = 0.2 / 1 / 3 / 10 µH；
- E/S `TON/TOFF` = 1–10 µs 范围；
- AGND–PGND L = 2 / 10 / 50 nH；
- 一次 TLP185 enable/disable pulse。

结果：

**没有任何一组自然形成持续 100–110 kHz。**

快速模型中约 425 kHz 的 FFT 最大点只对应 TP8 约 `1e-9 V` 的数值残差，不能视为物理振荡。

E/S 状态对 R10/IES 很敏感：

| 条件 | `V(ES)-V-` | 状态 |
|---|---:|---|
| R10=100 kΩ, IES=70 µA | ≈3.50 V | ON |
| R10=100 kΩ, IES≈20 µA | ≈2.10 V | 未定义区/保持 |
| R10=100 kΩ, IES=6 µA（另有 dark-current proxy） | ≈0.70 V | OFF |
| R10=6.8 kΩ, IES=70 µA | ≈0.483 V | OFF |

所以不能把 `R10=100 kΩ` 简化成“必然 OFF”或“必然 ON”；它对实际 E/S 电流非常敏感。

## 全官方宏关键对照

`official_summary.csv` 的关键结果：

| case | OPA548 OUT late Vpp | 主频 | TP8 late Vpp | 解释 |
|---|---:|---:|---:|---|
| V7-like, R10=100 kΩ, E/S=ON | ≈0.140 V | ≈453.3 kHz | ≈55.7 µV | 出现组合高频模态，但不是实板 105 kHz |
| 同上，J1 近似理想 | ≈0.140 V | ≈453.3 kHz | ≈60 µV | 模态不依赖普通 J1 被动源阻抗 |
| 同上，R5≈1 MΩ（近似拆除） | 0 | 无 | 0 | 模态消失 |
| R10=100 kΩ, IES≈20 µA, E/S 未进入 ON | 0 | 无 | 0 | 无组合模态 |
| V8-like, R10=6.8 kΩ, E/S=OFF | 0 | 无 | 0 | 无组合模态 |
| OPA548 单独 ON | ≈18 µV | 数值残余 | N/A | 不是 OPA548 宏模型单独自激 |
| V7-like ON + C39=220 pF | ≈79 µV | ≈420 kHz 残余 | ≈1 nV | C39=220 pF 抑制而非拉低到 105 kHz |

这里最重要的拓扑判据是：

> 在当前全官方模型中，OPA548 必须进入 ON，并且 R5 必须连接，453 kHz 组合模态才存在。

这与 H09 不矛盾：H09 固定 OPA548 OFF，因此降低 R5 不产生变化；H12 检查的是 OFF 假设被解除后的组合路径。

## 当前判断

### 已支持

1. H01–H11 的固定 OFF 基线确实无法检验 E/S 状态切换。
2. `R10=100 kΩ` 的 E/S 工作状态对真实引脚电流高度敏感。
3. OPA548 进入 ON 后，U4B–R5–OPA548 之间存在一个需要 R5 才成立的高频组合模态。
4. 普通 J1 被动 R/L、E/S 有限时延、TLP185 动态本身没有自然生成 100–110 kHz。
5. 本模型复现的全官方组合模态约 453 kHz，不能冒充实板 105 kHz 根因。

### 尚未支持

不能据此声称“OPA548 E/S 已经解释实板 105 kHz”。如果实板 105 kHz 确实依赖 R5，还需要额外的、被实测支持的动态才能把模型频率从约 453 kHz 改到 100–110 kHz，例如器件损伤、未提取寄生、E/S 快速阈值跨越、外部周期源或真实电源主动控制环。

## 下一步实板判别

优先级高于继续盲扫 SPICE 参数：

1. 同步测 TP8 与 `TP9-TP14`（E/S 相对 V-），确认振荡时 E/S 是否跨过阈值；
2. R5 做 A-B-A：100 Ω → 拆除 → 恢复 100 Ω；
3. 若拆 R5 后 105 kHz 消失，优先继续 U1/E/S/输入回灌路径；
4. 若拆 R5 后完全不变，优先回到 U4B 本体、供电或局部焊接/损伤。
