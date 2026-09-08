# H04 — R15 漏装（1 TΩ 等效）

## 物理错误与现有证据

R15 是 U4B_N 到 AGND 的 1 kΩ R0805。漏贴/掉件是可发生的 SMT 装配
错误；没有现有实测值证明或反驳。模型将电阻本体设为 1 TΩ，但保持
U4 pin 6、R15 焊盘和 AGND 走线的连接，不假设铜断路。

## 事前计算与预测

R15=1 kΩ 时增益 `1+39k/1k=40`。R15 开路后，R16 仍把 U4 输出连回
反相输入，但没有到地的分流；在理想低输入偏置下，U4B_N≈U4O，闭环
退化为跟随器，增益约 1（1 mV kick 仅约 1 mV 输出）。真实输入偏置/漏电
可能把输出推向某一轨，因而要分开记录 DC 漂移/饱和。该拓扑没有独立
100--110 kHz 能量源，预期是稳定跟随或 DC 漂移，不是持续大振荡。

## 仅改变项与基线

只将 R15 改为 1 TΩ；R16=39 kΩ、DNP、R5=100 Ω、4.7 Ω+47 nF、J2/U4=
±10 V、J1/OPA548=±5 V、E/S=V−+0.6 V 均不变。健康基线副本在
`../baseline_official/`；本目录含独立 common、deck、log、trace。

## 工具与命令

ngspice-42（`/usr/bin/ngspice`），官方 TI OPA548/OPA1656 宏模型，
`.spiceinit` 为 `set ngbehavior=ps`。从本目录运行：

```text
timeout 30s ngspice -b -o results/fixed_H04_R15_1T.log fixed_H04_R15_1T.cir
```

瞬态 0.5 ms、最大步长 0.05 µs、单个 1 mV/2 µs kick；晚期窗 0.25--
0.5 ms。

## 结果与工作点可信度

严格的 1 TΩ deck `fixed_H04_R15_1T.cir` 在 30 s 限时内未完成
（shell EXIT 124）。日志到达初始瞬态工作点，显示 `U4O≈0.4893 mV`
和 `TP8≈0.4893 mV`，但没有完成 0.5 ms transient、没有 late-window
数据，因此 TP8 Vpp 和频率均 **N/A**，不能将 timeout 当作振荡证据。

为区分数值条件，随后以 1 GΩ 作为“仍等效开路”的有限泄漏 proxy，命令为
`timeout 30s ngspice -b -o results/fixed_H04_R15_1G_open_proxy.log fixed_H04_R15_1G_open_proxy.cir`；
该 proxy
`fixed_H04_R15_1G_open_proxy.cir` 也在 30 s 内 timeout，仍只到初始
工作点（约 `U4O=0.4893 mV`）。这说明当前官方宏模型/该开路拓扑的
瞬态数值条件不可在本轮时间界内判定；并非证明电路振荡。官方 OPA548
OFF 静态电流异常仍不能当作实板电流。

按后续复核要求，进一步建立 `fixed_H04_R15_removed.cir`，真正删除
`R15` 元件行，仅保留 U4 pin6→R15 焊盘的铜路、焊盘寄生和 AGND 走线；
该 deck 的 `timeout 30s` 结果仍为 EXIT 124，只到初始工作点，未产生
0.5 ms 数据。因而 timeout 并非振荡或有效晚段证据。

## 判断

**未完成/不适用当前瞬态证据。** 现有结果只支持“初始工作点接近 0 V”，
不支持或反驳 TP8 晚期 >10 Vpp、100--110 kHz。由于严格 case 与数值
proxy 均超时，本项不进入“本模型未复现”计数，不能用来排除实板 R15
漏装。

## 下一步

不再继续 R15 高阻值盲扫。若必须完成该项，应另建经过验证的开路/有限
输入偏置建模或缩短拓扑后再跑；本轮转向 H05 及其余独立机制，并保持
单一错误原则。
