# H11 — U4B pin5↔pin6 输入差分焊桥

## 物理错误与现有证据

U4 的 SOIC-8 pad-net 来自 V8 PCB：pin5=`MUL_RAW`（U4B 非反相输入）、
pin6=`U4B_N`（反相输入）、pin7=`VCMD`（输出）。pin5 与 pin6 中心距
1.27 mm、相邻，故 pin5↔pin6 的锡桥/污染比跨中间脚的 pin5↔pin7
更符合封装几何。没有现有实测值确认或反驳该桥；用户已确认的 pin6→
U4B_N 20 mΩ 连续性不涉及该短路。

## 事前计算与预测

健康 U4B 反馈为 R16=39 kΩ、R15=1 kΩ，噪声增益约40。pin5 与 pin6
直接短接后，差分输入电压被强制为近零；该错误不是正反馈，输出只能由
输入失调/偏置和宏模型保护状态决定，预期是接近某个DC值、饱和或启动
瞬态，而不是凭空形成100--110 kHz。只有晚段 TP8出现稳定周期且>10 Vpp
才支持目标；饱和必须单独报告。

## 仅改变项与基线

只在 U4P（pin5）与 U4N（pin6）之间加入 1 mΩ 的单一焊桥等效电阻；
R15/R16、DNP 电容、R5=100 Ω、4.7 Ω+47 nF、J2/U4=±10 V、J1/OPA548=
±5 V、E/S=V−+0.6 V 均保持不变。健康基线副本在
`../baseline_official/`，common 与 deck 在本目录独立保存。

## 工具与命令

ngspice-42（`/usr/bin/ngspice`），官方 TI OPA1656/OPA548 宏模型，
`.spiceinit` 为 `set ngbehavior=ps`。从本目录运行：

```text
timeout 30s ngspice -b -o results/fixed_H11_pin5_pin6_bridge.log fixed_H11_pin5_pin6_bridge.cir
```

瞬态0.5 ms、最大步长0.05 µs、单个1 mV/2 µs启动kick；TP8为R5前节点，
晚段窗0.25--0.5 ms。

## 结果与工作点可信度

`fixed_H11_pin5_pin6_bridge.log` 以 EXIT 0 完成（约10k数据行），无收敛、
奇异矩阵或步长失败告警。TP8 晚段稳定约 `8.897189 V`，`TP8 late Vpp =
0 V`；启动窗口约 8.897189--8.897190 V。U4O 晚段同样为0 Vpp，OPA548
OUT 晚段约 −0.2953 V，未出现可测零交叉频率。U4 输出因此是近正轨的
DC状态，而非持续振荡。

最终宏模型电流约 `i(VJ1P)=+27.85 mA`、`i(VJ1N)=+4.16 mA`、
`i(VJ2P)=−40.04 mA`、`i(VJ2N)=+7.80 mA`。OPA548 OFF IQ 已知异常，
这些电流仅作工作点诊断，不作实板电流证据。

## 判断

**本模型未复现目标。** 与H05的pin6↔pin7（负反馈旁路）不同，本项相邻
输入差分短路导致U4近+10V平坦DC；没有TP8 >10Vpp或100--110kHz持续周期。
这只约束当前官方宏模型/拓扑，不能排除实板桥接后器件损伤或其他组合。

## 下一步

除非出现>10 Vpp候选，否则不再组合多个焊桥或人为跨脚；必要时只做更小
步长复核该单一连接。
