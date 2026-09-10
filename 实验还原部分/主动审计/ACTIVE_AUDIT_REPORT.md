# 正弦电阻项目：类似 R10 漏检问题的主动审计

## 结论摘要

之前 SPICE 没有发现 V7 R10=100 kΩ 的 E/S 风险，根本原因不是求解器错误，而是测试模型把关键状态预先设成了“确定 OFF”：多个基线 deck 使用理想电压源把 E/S 固定为 V-+0.6 V，或者用被动 OFF surrogate 代替 OPA548。R10/TLP185/E/S 阈值本身不在被验证系统中，因此该问题不可能被这些 deck 发现。

本次主动审计确认以下同类问题/风险：

1. **CONFIRMED / HIGH — H07/H08 OPA548 供电节点断链。**
   两个 deck 建立了 `PWR_P/PWR_N` 的 J1/PDN，但 OPA548 实例使用 `VPLUS/VMINUS`；原 deck 中没有把这两组节点连接起来，也没有给 VPLUS/VMINUS 独立供电。因此注释声称建模的 J1/OPA548 供电耦合实际上没有进入 OPA548。
2. **CONFIRMED / HIGH — H07/H08 基线 C27 仍为 10 pF。**
   V8 PCB/release 已是 10 nF。105 kHz 下两者容抗约相差 1000 倍，因此旧 H07/H08 不能作为 V8 的高频电源耦合 sign-off。
3. **CONFIRMED / PROCESS — V8 `audit/` 中间制造数据已过时，但最终 release 正确。**
   中间 audit CSV 仍可看到 R10=100 kΩ、C27=10 pF、旧 C16/R12 信息；最终 `release/V8_2026-09-04/assembly` 已正确同步。对最终 73 个 SMT 元件做 PCB↔BOM↔CPL 全量交叉检查，value/footprint/XY/rotation/side 共 0 个不一致。风险是仓库存在多个“看似可下单”的 source of truth。
4. **CONFIRMED / DESIGN-SIGNOFF — R10=6.8 kΩ 的“最坏条件”表述不成立。**
   OPA548 数据表的 E/S LOW 电流 -70 µA 位于 TYP 栏，而非 MAX 栏。6.8 kΩ 是明显优于 100 kΩ 的改进，但不能用 70 µA 声称获得 datasheet worst-case guarantee。还需要同时验证 TLP185 关断漏电和开启 CTR 对 OFF/ON 两边裕量的影响。
5. **KNOWN STATE DEPENDENCY — J5 需要外部跨接。**
   J5 的 1/2/3 脚分别是 VK_MCU/VK/VK_EXT，不内部短接。默认必须 1–2 跨接；否则关键 VK 节点可能浮空。这类问题不会被假设 VK 已驱动的 SPICE 捕获。
6. **KNOWN STATE DEPENDENCY — PB8/BOOT0 依赖 option bytes。**
   V8 没有给 PB8/BOOT0 增加硬件强下拉，release note 要求生产编程并回读 OPTR 0xFBEFF8AA。ERC/DRC/SPICE 都无法证明实际烧录状态正确。
7. **MODEL-LIMITATION — OPA548 官方宏模型不足以代表真实 shutdown 高频动态。**
   宏模型使用阈值开关表达 E/S 状态；数据表则给出典型 1 µs disable、3 µs enable，并明确提示 shutdown 器件在 >20 kHz 信号下可能增加 leakage。因此“官方宏模型 OFF 时稳定”不能单独排除实板 105 kHz 下的 OFF-state 非线性。
8. **PROCESS — 13 个 fault deck/include 把 E/S 硬固定在 V-+0.6 V；11 个用理想 ±5 V J1；14 个使用本机绝对 include 路径。**
   前两项限制了物理覆盖面，后一项降低可复现性。
9. **PROCESS — V8 release gate 的 ERC 条件是“与转换基线 436 项一致”，不是 ERC=0。**
   这是对 EasyEDA 转换噪声的务实处理，但意味着 ERC 目前不是一个干净的新电气错误报警器。

## H07/H08 修正后的复跑

修正内容：
- OPA548 `VMINUS/VPLUS` → `PWR_N/PWR_P`；
- E/S 和 ILIM 引用负轨同步改为 PWR_N；
- C27 10 pF → 10 nF；
- 仅为当前 Linux ngspice 环境修正模型 include 路径。

### H08

- C15=100 nF nominal：TP8_PP=0；OPA548 OUT_PP≈3.16e-4 V。
- C15=10 nF：同样稳定。
- C15≈open：同样稳定。

因此 H08 的定性结论“仅漏掉 U4 正轨局部 C15 不足以复现 105 kHz”在修正后仍成立。

### H07

- nominal RAPS=3.5586 mΩ：TP8_PP=0；OPA548 OUT_PP≈3.16e-4 V，稳定。
- 1 Ω / 10 Ω 高阻 fault：修正后出现 transient OP/timestep convergence 问题，不能沿用原日志作为可信定量结果。

因此 H07 的高阻 fault 结论需要重新设计数值 continuation/启动条件后再验证；当前不能把旧 H07 结果当作“已验证的真实 J1/OPA548 耦合结果”。

## 建议把检查体系改成五道 gate

1. **KiCad electrical source-of-truth**：读取最终 `.kicad_pcb/.kicad_sch`，生成唯一 net/value manifest。
2. **Manufacturing parity**：每次 release 自动比较 PCB↔BOM↔CPL 的 value、footprint、XY、rotation、side；中间 `audit/` 文件不得作为下单入口。
3. **SPICE netlist lint**：检查控制脚是否被硬钳、供电节点是否断链、V8 manifest 与 deck 元件值是否漂移、绝对 include 路径。
4. **State matrix**：E/S OFF/undefined/ON、J5 jumper 缺失/正确、J1 ramp/current-limit、probe loading 等必须单独列成状态维度，不能只做“单元件 fault matrix”。
5. **Model adequacy declaration**：每个 deck 明确列出“真实建模 / surrogate / 固定假设 / 未建模”的物理机制。只有这样，`not reproduced` 才能解释为“在这些机制内被排除”，而不是“硬件问题不存在”。
