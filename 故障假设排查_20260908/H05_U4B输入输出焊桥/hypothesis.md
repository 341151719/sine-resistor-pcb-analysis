# H05 — U4B 邻近引脚焊桥候选

## 物理核查与取舍

V8 KiCad PCB 的 U4 是 `OPA1656IDR` SOIC-8，pad net 明确为：pin 5
`MUL_RAW`（非反相输入）、pin 6 `U4B_N`（反相输入）、pin 7 `VCMD`
（输出）。pin 5、6、7 在同一排相邻，中心距 1.27 mm。一个干净的
pin5→pin7 连接需要跨过 pin6，实际焊桥很可能同时短到中间 pad，故不能
把它当作独立、邻近的“正反馈”连接。按用户授权，H05 改为最有物理根据
的相邻 pin6↔pin7 焊桥：这是反相输入到输出的直接负反馈旁路，不冒充
正反馈；pin5→pin7 只保留为未测试的低可信变体。

PCB 来源：
`KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04/project.kicad_pcb`
的 U4 footprint，及 `.codex_stability_audit_tmp/pdn_resonance/pcb_full.json`
的 U4 pad-net 摘录。R16 本身连接 `VCMD`↔`U4B_N`，R15 连接 `U4B_N`↔
`AGND`；H05 只新增一个 pin6↔pin7 短路，不改 R15/R16。

## 事前计算与预测

健康状态为 R16/R15 非反相反馈，噪声增益 40。pin6↔pin7 短路将绕过
39 kΩ，U4B 仍以负反馈工作但趋近单位增益；预期启动响应减小且稳定，
不应产生正反馈振荡。若模型在理想 1 mΩ 桥下出现近轨，是 DC/输入偏置
或宏模型异常，应与持续 100--110 kHz 周期分开。

## 仅改变项与基线

只在 U4N（pin6）与 U4O（pin7）之间加入 1 mΩ 的单一焊桥等效电阻；
R15=1 kΩ、R16=39 kΩ、C39 等 DNP、R5=100 Ω、4.7 Ω+47 nF、J2/U4=
±10 V、J1/OPA548=±5 V、E/S=V−+0.6 V 均保持不变。健康基线副本在
`../baseline_official/`。

## 工具与命令

ngspice-42（`/usr/bin/ngspice`），官方 TI OPA548/OPA1656 模型，
`.spiceinit` 为 `set ngbehavior=ps`。从本目录运行：

```text
timeout 30s ngspice -b -o results/fixed_H05_pin6_pin7_bridge.log fixed_H05_pin6_pin7_bridge.cir
```

瞬态 0.5 ms、最大步长 0.05 µs、单个 1 mV/2 µs kick；晚期窗 0.25--
0.5 ms。需记录 TP8（不是只读 OPA548 OUT）和 U4O。

## 结果与工作点可信度

`fixed_H05_pin6_pin7_bridge.log` 以 EXIT 0 完成（约 10k 数据行），无收敛、
奇异矩阵或步长失败告警。短路旁路 R16 后，TP8 晚段稳定约 0.4893 mV，
`TP8 late Vpp = 0 V`；启动窗口约 0.3474--1.6344 mV。U4O 晚段同样
`0 Vpp`，OPA548 OUT 约 −4.6373 V 常值，晚段没有可测零交叉频率。J1
电流约 −57.18/+57.18 mA、J2 约 −7.801/+7.800 mA；官方 OPA548 OFF IQ
异常，电流只作模型工作点诊断，不能作实板证据。

## 判断

**本模型未复现。** 最近邻 pin6↔pin7 桥表现为预期的负反馈旁路/近单位增益，
没有 TP8 >10 Vpp 或 100--110 kHz 持续周期。由于 pin5→pin7 正反馈需要
跨过中间 pin6，且可能同时短接三脚，未把该低可信跨脚连接伪装成已验证
故障；实板污染或器件损伤仍未被本 case 排除。

## 下一步

仅在出现 >10 Vpp 周期候选时做更小步长和 R5 对照；否则不测试非邻近的
pin5→pin7 人工跨接，避免人为构造不符合封装几何的 105 kHz 结果。
