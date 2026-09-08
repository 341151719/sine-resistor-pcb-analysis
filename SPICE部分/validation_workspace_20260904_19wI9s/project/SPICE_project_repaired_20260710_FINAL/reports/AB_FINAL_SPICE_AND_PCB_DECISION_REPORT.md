# A/B 项 pure-vendor SPICE 测试与改板决策报告

## 总结

A 级核心项目已完成有效性确认：RCL、current-sense trim、ZSERVO/DC servo、U4A/U4B compensation 方向、AD633 Z 注入、输出 Zobel/Riso 预留均有仿真依据。B 级保护/启动项中，servo reset、soft-start、clamp、trim interface 已形成可改板策略；其中 VCMD clamp 和 OPA548 enable/mute 属保护/时序功能，不应被当作正常 tracking 元件。

结论：可以按本报告的 PCB action table 改板，但不要把 dynamic tracking 当作已完全通过。当前三项修复 + fast compensation 只能作为第一版硬件可调试基础；二版仍可能需要 lead-lag 或闭环阻抗伺服。

## 状态表

| priority   | level   | item                                      | status                                                | evidence                                                                                                                                                             | pcb_action                                                                                                          | caveat                                                                                           |
|:-----------|:--------|:------------------------------------------|:------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------|
| A1         | A       | OPA548 RCL reference to N18               | PASS / mandatory                                      | RCL->0: r1 AC Reff=4137.1Ω, r100=213.3Ω; RCL->N18: r1=1.047Ω, r7.2=7.249Ω, r100=99.052Ω.                                                                             | 改板：RCL 下端接 -18V/N18；若已接 GND，割线飞线到 N18；预留 0Ω 选择位。                                             |                                                                                                  |
| A2         | A       | Current-sense offset trim                 | PASS / effective                                      | r1 DC Iport: RCL-only=-41.99mA, VOS trim=-16.84mA, trim+servo=-3.64mA; AC Reff remains 1.054Ω.                                                                       | 预留 current-sense summing node 的 DAC/电位器注入电阻位，建议 100k–1M；加 VSENSE/VSENSE_TRIM/ISIG 测试点。          | 对高阻区需调度淡出，不能全范围固定同一补偿。                                                     |
| A3/B1      | A/B     | Slow DC servo to AD633 Z node             | PASS / partial margin                                 | trim+servo 后 DC Iport: r1=-3.64mA, r7.2=-7.92mA, r100=-6.88mA; AC Reff: r1=1.054Ω, r7.2=7.250Ω, r100=99.072Ω.                                                       | 预留慢速积分器或外接小板：IPORT_DC RC、低失调运放、ZSERVO 注入电阻、reset/disable、限幅。                           | 能显著降 r1 DC 偏置，但未把全范围压到 <1mA；若严苛目标需 AD633 feedthrough trim 或闭环阻抗伺服。 |
| A4         | A       | U4A/U4B feedback compensation capacitance | DIRECTION PASS / final value not frozen               | 100p/220p baseline electrical dynamic pass=1/20; 10p/22p fast-comp pass=6/20. Median rel err dropped on many low/mid cases; high-R/fm300/1000 still fail.            | 反馈电容必须可换：U4A 2.2/4.7/10/22/47/100p，U4B 4.7/10/22/47/100/220p；预留 Rlead-Clead 串联 lead-lag DNP 支路。   | 减小电容有效，但完整 dynamic tracking 未通过；二版需 lead-lag 或闭环阻抗伺服。                   |
| A5         | A       | AD633 Z trim / ZSERVO injection           | PASS for injection; static trim alone insufficient    | AD633 fitted: c0=4.989mV, cx=0.500mV/V, cy=0.500mV/V, cxy=0.09997V/V². ZSERVO injection tested in full-chain.                                                        | AD633 Z pin 必须预留至少两个注入位：静态 trim 和 ZSERVO；最好再预留 VK feedthrough compensation 输入。              | 不要只靠常数 trim 覆盖 1–100Ω；需要随 Rtarget/VK 调度或 DC servo。                               |
| A6         | A       | OPA548 output Riso + Zobel                | PASS with Zobel; Riso-only fail                       | dynamic low-slice A6: ok=3/4. Zobel 10Ω+100nF and strong 5Ω+220nF both converged with ilim≈0.0065, xmax≈0.0022; Riso-only case failed at OPA548 zener initial point. | 预留 Riso，但不要只装 Riso：建议 Riso 0.05–0.2Ω + DNP/可装 Zobel 10Ω+100nF 起步；保留 0Ω 旁路。                     | Zobel不修主 tracking，只改善功放负载稳定/收敛；最终值需实板振铃测试。                            |
| B2         | B       | Servo reset / disable sequencing          | PASS for enable; reset-holdoff increases startup bias | B2_servo_enabled_start_r1_acoustic: dcI=4.42mA, ilim=0.0039, xmax=0.0083; B2_servo_reset_late_r1_acoustic: dcI=10.95mA, ilim=0.0095, xmax=0.0165                     | 预留 servo reset/disable，但 release 应早于 OPA548 enable 或跟随 soft-start；不要让 servo 长时间后启后直接进入 1Ω。 | 未完成所有组合；但已显示 late reset 比正常 enable 更差。                                         |
| B3         | B       | Rtarget minimum clamp                     | PASS as protection concept                            | RMIN clamp prevents entering deepest negative-impedance region; r1 is highest-risk case, 3/5/7.2Ω should be selectable for first bring-up.                           | PCB/固件预留 Rtarget_min clamp，第一版 bring-up 从 7.2Ω→5Ω→3Ω→1Ω 逐步放开。                                         | 需要真实 full-chain long transient 复跑最终保护阈值。                                            |
| B4         | B       | VCMD clamp / limiter                      | CONDITIONAL PASS                                      | VCMD clamp can limit power-stage command, but will distort synthetic impedance when active. It is a protection, not a normal operating element.                      | 预留 VCMD limiter 或 OPA548 input clamp，推荐可调阈值 ±2V/±5V/旁路 DNP；fault 时启用，正常 tracking 不应频繁触发。  | 若阈值过低，会直接破坏 1Ω tracking。                                                             |
| B5         | B       | OPA548 enable/mute + soft-start           | PASS for soft-start; hardware enable not modeled      | All successful full-chain pure-vendor dynamic slices used command/acoustic soft ramp; no-soft-start was not retained as acceptable bring-up path.                    | 必须预留 OPA548 enable/mute 或前级 analog switch；上电流程：mute→trim→servo enable→OPA enable→Rtarget ramp。        | 当前 wrapper 没有真实 OPA548 enable pin 行为；硬件需按 datasheet 实现。                          |
| B6         | B       | DAC trim interface / trim range           | PASS for required range                               | OPA1656 input-referred offset≈0.496mV; r1 trim reduced DC Iport from 41.99mA to 16.84mA before servo, then 3.64mA with servo.                                        | DAC trim range至少 ±1mV input-referred，分辨率建议 <20µV；注入电阻 100k–1M，DNP 可改。                              | DAC噪声会进入 current-sense，需要 RC 限带和模拟地布线。                                          |
| A7         | A/B     | Critical test points                      | REQUIRED                                              | SPICE cannot verify physical probe access; without test points, root-cause isolation will be slow.                                                                   | 必须预留 SPK, DRV, IPORT/RSH两端, VSENSE, VSENSE_TRIM, ISIG, VK, MUL, ZSERVO, IPDC, VCMD, ILIM, supplies.           |                                                                                                  |

## 推荐改板优先级

1. 必改：RCL 接 N18。
2. 必留：current-sense trim 注入点、AD633 Z/ZSERVO 注入点、servo reset/disable、关键测试点。
3. 必须可换：U4A/U4B 反馈电容，且预留 Rlead-Clead lead-lag DNP。
4. 输出端：Riso 位 + Zobel 位；不要只装 Riso 不装 Zobel。
5. 保护项：Rtarget_min clamp、VCMD clamp、OPA548 mute/enable、soft-start 状态机。


## 推荐第一版装配值

- RCL：按 OPA548 目标限流计算，当前仿真 33.2kΩ，参考 N18。
- VOS_I_TRIM：初值 -0.496 mV input-referred，硬件用 DAC/电位器微调。
- DC servo：fc 0.5–2 Hz 起步，K 0.2 V/A 起步，ZSERVO 限幅 ±0.5V。
- U4A/U4B：不要装 100p/220p 固定死；先试 10p/22p，并预留 4.7p/10p、22p/47p。
- 输出：Riso 默认 0Ω或0.05Ω，Zobel 默认 DNP；若振铃/收敛问题，试 10Ω+100nF。


## 还未签核通过的边界

- 完整 pure-vendor dynamic tracking 未通过：fast-comp 从 1/20 提升到 6/20，但 high-R 和 fm=300/1000Hz 仍失败。
- DC 偏置未全范围 <1mA：r1 明显改善，但 r7.2/r100 仍需进一步 trim/feedthrough/servo。
- OPA548 enable/mute 需要真实硬件 pin/开关级验证；当前 SPICE主要验证 soft-start 行为。
