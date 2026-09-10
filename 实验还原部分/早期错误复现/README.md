# 正弦电阻 V7：早期实验错误的 KiCad/SPICE 复现

日期：2026-09-09

## 结论概览

这套测试区分“设计/测量错误能够复现”和“105 kHz 根因尚不能自然复现”。

| 项目 | 当前结论 | 关键数字 |
|---|---|---|
| V7 R10=100k 的 OPA548 E/S 关断裕量问题 | **定量复现** | 100k -> E/S-V- = 3.4786 V；9.09k -> 0.6140 V；6.8k -> 0.4634 V |
| J1 在约 +/-2.5 V 附近突然增流 | **最小官方模型未复现** | R10=100k 的简单 DC J1 sweep 没出现 70 mA 级突变 |
| OPA ON 后约 70 mA CC | **可复现其电流需求机制，不是 105k 起源** | 给 OPA548 输入 2 Vpk/105k，电源峰值电流约 69 mA |
| 示波器 GND 黑夹误接 TP8 | **等效故障强复现** | TP8 2.020 V -> 4.46 mV；U4B 正轨电流 3.95 mA -> 93.0 mA |
| OPA OFF、TP7 干净、TP8 数伏级 100–110 kHz | **尚未自然复现** | 健康官方模型 late TP8 = 0 Vpp；H12 V7-like 动态模型是约 453 kHz、TP8 55.7 uVpp |

## 1. KiCad 静态复核

`kicad_static_extract.py` 直接读取 V7/V8 的 `project.kicad_pcb`。

V7：

- R10 = 100kR，pad1 = OPA_ES，pad2 = PWR_N；
- R5 = 100R，连接 VCMD -> OPA_IN_P；
- U1 = OPA548F/500，pin7 = OPA_ES；
- U4 = OPA1656IDR，pin5 = MUL_RAW(TP7侧)，pin7 = VCMD(TP8)；
- U7 = TLP185，输出跨 PWR_P / OPA_ES。

V8：

- 唯一与本问题最直接相关的改变之一是 R10 变成 6.8kR；
- R5/U1/U4/U7 的上述网络关系保持不变。

注意：KiCad ERC/DRC 不会因为 `100k` 在 E/S 上“功能裕量不够”而自动报错。这属于器件行为/参数设计问题，需要 SPICE 或手工 datasheet margin check。

## 2. R10/E-S 关断问题：官方 OPA548 宏模型定量复现

文件：`01_r10_es_sweep.cir`

运行结果：

- R10=100k：`V(ES)-V(V-) = 3.478609 V`
- R10=9.0909k（100k || 10k）：`0.614035 V`
- R10=6.8k：`0.463396 V`

9.09k 的结果和实板记录的约 0.55–0.65 V 高度一致。

因此，这一项可以称为“SPICE 对早期实板问题的定量复现”。

## 3. J1 低压附近突增流：简单模型没有复现

文件：`01b_j1_sweep_r10_100k.cir`

用 R10=100k，J1 从 +/-1 V 扫到 +/-5 V。最小 OPA548 官方宏模型没有在 +/-2.5 V 附近出现 70 mA 级的突然电流跃迁。

这意味着实板当时的突然增流不能仅归结为“R10=100k + 一个空载 OPA548 DC 模型”。还需要板级负载、输入异常、E/S 动态、供电状态或其它实际条件。

## 4. OPA ON 后约 70 mA：可以复现“后果机制”

文件：`02_opa_on_105k_amp{1,2,3,4}V.cir`

这里不声称产生 105 kHz，而是把实板后来观测到的高频 VCMD 当作已经存在的条件，检查 OPA548 打开后是否足以产生 CC 电流需求。

| 105k 输入幅值 | OPA548 输出 Vpp | +轨峰值取电 | -轨峰值取电 |
|---:|---:|---:|---:|
| 1 Vpk | 2.073 Vpp | 37.8 mA | 37.2 mA |
| 2 Vpk | 4.111 Vpp | 69.1 mA | 68.7 mA |
| 3 Vpk | 6.140 Vpp | 101.0 mA | >100 mA |
| 4 Vpk | 7.209 Vpp | 132.1 mA | >100 mA |

所以“TP8 已经有数伏级 105 kHz -> OPA ON -> 电源触发约 70 mA 限流”在数量级上完全合理。

这里使用理想电压源，所以不会显示台式电源 UI 的 `CC` 状态；它证明的是负载的电流需求已经达到/超过 70 mA。

## 5. 错误示波器接地：强复现

文件：`03_scope_ground_short.cir`

用 TI 官方 OPA1656、R15=1k、R16=39k，把正常高阻探头与“TP8 被 50 mOhm 接地”做 A/B。

### 正常

- TP8 = 2.0196 V
- U4B +10 V rail 电流约 3.95 mA

### 示波器 GND 黑夹接 TP8 的等效情况

- TP8 = 4.46 mV，几乎被强制接地
- U4B +10 V rail 电流约 93.0 mA

因此实验里“接错探头之后 J2 电流从约 20 mA 上升到约 70 mA”完全符合这种测量人为重载机制。具体数字不要求一模一样，因为实板 J2 还给其它器件供电。

## 6. 核心 100–110 kHz：仍不能诚实地说已经复现

文件：`04_healthy_baseline.cir`

官方 OPA1656 + OPA548，R15=1k、R16=39k、R5=100R、OPA548 E/S 固定 OFF，只有一次 1mV startup kick：

- 10084 transient rows；
- late TP8_PP = 0 V；
- 没有持续 100–110 kHz。

此前 H12 动态 E/S 模型在 V7-like R10=100k、OPA548 实际 ON 条件下能够出现一个 R5 依赖的组合模态，但它是：

- 约 453.3 kHz；
- OPA548 OUT ≈ 0.140 Vpp；
- TP8 ≈ 55.7 uVpp。

它既不是 105 kHz，也不是实板的“OPA OFF、TP8 数伏级”。因此不能把它冒充根因复现。

曾经用 MOhm 级 U4 pin6 接触故障可以把 SPICE 调到约 105 kHz，但实测 pin6 到反馈节点约 20 mOhm，已经把这种模型否定，因此不应作为有效复现。

## 7. 如何运行

需要 ngspice 42，并让当前目录的 `.spiceinit` 生效。进入本目录后可运行单个
deck：

```bash
ngspice -b 01_r10_es_sweep.cir
ngspice -b 03_scope_ground_short.cir
ngspice -b 04_healthy_baseline.cir
```

也可以一次运行全部案例：

```bash
./run_all.sh
```

若 ngspice 不在 `PATH`，可使用 `NGSPICE=/绝对路径/ngspice ./run_all.sh`。
TI 模型放在 `models/`；新日志和 `.dat` 写入被 Git 忽略的 `results/`。

## 8. 当前 KiCad CLI 限制

本轮 V7/V8 KiCad 工程文件可以直接读取和静态审计，但没有重新执行
`kicad-cli ERC/DRC`。项目中已有 KiCad 10.0.4 的 ERC/DRC 结果；本报告涉及的
R10/R5/U1/U4/U7 拓扑是直接从 `project.kicad_pcb` 重新提取的。

## 9. 解释边界

`02_opa_on_105k_amp*.cir` 有意施加 105 kHz，只用于验证已经存在该波形时的
功率级电流后果。只有 `04_healthy_baseline.cir` 用于检查电路能否从一次启动
扰动中自行产生持续振荡；它的结果为阴性。两类 deck 不得混用。
