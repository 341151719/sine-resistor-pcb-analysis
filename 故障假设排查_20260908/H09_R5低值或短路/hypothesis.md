# H09 — R5 错小/短路（单一故障）

## 事前推导

PCB 提取网表把 R5 放在 VCMD/TP8 与 OPA548 `+IN` 之间，标值 100Ω（`实际遇到的问题/PCB_AWARE_full_extracted_loop.cir:897-905`；简化官方 deck 也明确 TP8 在 R5 前、R5=100Ω，`稳定性原因分析CODEX/.codex_stability_audit_tmp/fault_injection_round1/fault_fixed_common.inc:51-59`）。R5 若贴错低值或焊锡短路，OPA548 输入 rail clamp、输入电容与 U4 输出反馈的负载会改变；官方宏已显示输入钳位存在，因此这是可证伪的单故障。测试 100Ω（健康）、10Ω（错小）和 1mΩ（短路的数值近似），只改 R5，R16=39k、C39 均维持基线。

J2=±10V、J1=±5V、E/S=V−+0.6V（OFF），输出保留 4.7Ω+47nF 负载；只有 1mV/2µs 一次启动脉冲，不注入 105kHz。

## 模型限制

使用官方 TI OPA1656/OPA548 宏模型和既有 `fault_fixed_common.inc`。官方 OPA548 OFF 供电电流/输出静态点已知不具备实物校准意义，故不以其电流排除 R5。这个 deck 没有把 R5 与输入焊桥叠加；H05 另行测试 U4 输入/输出桥。1mΩ 仅是 SPICE 避免零欧奇异的短路表示。

## Deck、命令与完整日志

- Deck：[H09_R5.cir](H09_R5.cir)
- PSpice 兼容设置：[.spiceinit](.spiceinit)
- 命令：`timeout 30s ngspice -b -o H09_R5_local.log H09_R5.cir`
- 复核日志：[H09_R5_local.log](H09_R5_local.log)（旧绝对 include 版本
  `H09_R5.log` 也保留作原始记录；复核版改为子目录内同一 common）。

## 指标与判断

每例 `tran 0.05µs 0.5ms`，晚期窗 0.25–0.5ms；目标 TP8 为持续 100–110kHz 且 >10Vpp。

| R5 | TP8 late Vpp | OUT late Vpp | OPA548 +IN late Vpp | TP8/IN 终值 | 判断 |
|---:|---:|---:|---:|---:|---|
| 100Ω（健康） | 0 | 0 | 0 | 19.5701mV / 19.5701mV | 无振荡 |
| 10Ω（错小） | 0 | 0 | 0 | 19.5701mV / 19.5701mV | 无振荡 |
| 1mΩ（近似短路） | 0 | 0 | 0 | 19.5701mV / 19.5701mV | 无振荡 |

三例均跑满 0.5ms；在此 OFF 宏模型中降低 R5 没有改变 TP8、输入或 OUT 的晚期波形，完全不匹配目标。不能据此证明实物 R5 一定无故障：实物 OPA548 OFF 输入保护/损伤、瞬态电源阻抗或与其他故障组合未由本模型覆盖。
