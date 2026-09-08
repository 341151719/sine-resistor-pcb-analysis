# Pure vendor 三项修复仿真完成报告

本轮在 `/mnt/data/1SPICE_SPICE_SIM` 中完成并验证三项修复：

1. OPA548 RCL 接法修复：`RCL ILIM N18 __RCL__`。
2. Current-sense offset trim：在 INA149 后、OPA1656 x50 电流检测级前增加 input-referred trim，形式为 `VSENSE_TRIM = VSENSE - VOS_I_TRIM*FIXW(RTARGET)`。
3. 慢速 DC servo：对 `IPORT` 做低通，向 AD633 的 `Z` 端注入限幅校正，形式为 `ZSERVO = limit(Kdc*FIXW(RTARGET)*LPF(IPORT), ±limit)`。

所有验证均使用 `official_pure_rawps_wrapped_models.lib`，即 TI/ADI raw vendor macromodel wrapper，加 `.spiceinit: set ngbehavior=ps`，没有器件级 surrogate fallback。

## 实际已写入工程的核心网表

```spice
RCL ILIM N18 __RCL__
B_VSENSE_TRIM VSENSE_TRIM 0 V = {V(VSENSE)-VOS_I_TRIM*FIXW(V(RTARGET))}
XU_OPA_ISENSE VSENSE_TRIM NFB_A ISIG P15 N15 OPA1656_NG_SURR
R_IPDC IPORT IPDC {DC_SERVO_R}
C_IPDC IPDC 0 {DC_SERVO_C} IC=0
B_ZSERVO ZSERVO 0 V = {limit(DC_SERVO_ENABLE*DC_SERVO_K*FIXW(V(RTARGET))*V(IPDC), -DC_SERVO_LIMIT, DC_SERVO_LIMIT)}
XU_MULT ISIG 0 VK 0 N15 ZSERVO MUL P15 AD633_NG_SURR
```

其中调度权重：

```spice
.func FIXW(r) {FIX_SCHED_ENABLE*min(max((FIX_SCHED_OFF-r)/max(FIX_SCHED_OFF-FIX_SCHED_FULL,1e-9),0),1) + (1-FIX_SCHED_ENABLE)}
```

最终验证参数：

```text
VOS_I_TRIM = -0.496092 mV
DC_SERVO_FC = 2 Hz
DC_SERVO_K = 0.2 V/A
DC_SERVO_LIMIT = 0.5 V
FIX_SCHED_ENABLE = 1
FIX_SCHED_FULL = 7.2 Ω
FIX_SCHED_OFF = 30 Ω
```

注意：`VOS_I_TRIM` 为负号，是因为在本工程连接方向下，等效动作是给 current-sense 非反相输入增加约 0.496 mV。

## 关键结论

- RCL 修复已确认有效，是必须保留的硬修复。
- Current-sense trim 对 `Rtarget≈1Ω` 的 DC 偏置显著有效：`|Iport_dc|` 从约 41.99 mA 降到约 16.84 mA。
- 加入慢速 DC servo 后，`Rtarget≈1Ω` 的 `|Iport_dc|` 进一步降到约 3.64 mA，同时 AC Reff 仍为 1.054Ω，误差约 5.5%。
- `Rtarget≈7.2Ω` 的 DC 偏置从约 12.28 mA 降到约 7.92 mA，AC Reff 仍为 7.25Ω。
- `Rtarget≈100Ω` 不适合强行使用这组 low-R trim/servo，因此加入 `FIXW(RTARGET)` 调度，在高阻区自动淡出；高阻区 AC Reff 保持约 99.07Ω。
- 这三项修复使 fixed-R pure-vendor 链路达到“AC 阻抗有效 + low-R DC 偏置显著降低”的状态，但还不是完整动态 signoff。动态正弦 case 已能跑通，但 `Reff` 简单 LS 指标对时变阻抗不适用，后续应加入 lock-in/frequency-bin 指标。

## 修复前后改善表

|   target_ohm |   baseline_ac_reff_ohm |   final_ac_reff_ohm |   baseline_abs_dc_iport_mA |   final_abs_dc_iport_mA |   dc_iport_reduction_pct |   baseline_abs_vcmd_mV |   final_abs_vcmd_mV |   ac_error_final_ohm | status                                               |
|-------------:|-----------------------:|--------------------:|---------------------------:|------------------------:|-------------------------:|-----------------------:|--------------------:|---------------------:|:-----------------------------------------------------|
|          1   |                1.04765 |             1.05444 |                   41.9889  |                 3.64045 |               91.33      |               304.444  |             23.6609 |            0.0551767 | pass_ac; dc_improved                                 |
|          7.2 |                7.24896 |             7.24996 |                   12.2788  |                 7.92373 |               35.4684    |                85.7337 |             54.5022 |            0.0513817 | pass_ac; dc_improved                                 |
|        100   |               99.0674  |            99.0719  |                    6.87305 |                 6.87814 |               -0.0740885 |                47.4479 |             46.9722 |           -0.916427  | pass_ac; high-R uses scheduled fix-off, dc unchanged |

## 关键 case 数据

| case                                     | status   |   rtarget_tail_mean_ohm |   reff_fit_ac_tail_ohm |   reff_fit_ac_err_vs_tail_mean_ohm |   dc_iport_tail_a |   dc_vcmd_tail_v |   dc_vspk_tail_v |   iport_pk_tail_a |   follow_error_rms_tail_v |   ilim_ratio_tail_pk |   xmax_ratio_pk |   vos_i_trim |   dc_servo_fc |   dc_servo_k |   fix_sched_enable |   fix_sched_full |   fix_sched_off |   zservo_mean_tail |
|:-----------------------------------------|:---------|------------------------:|-----------------------:|-----------------------------------:|------------------:|-----------------:|-----------------:|------------------:|--------------------------:|---------------------:|----------------:|-------------:|--------------:|-------------:|-------------------:|-----------------:|----------------:|-------------------:|
| rcl_only_r1p0                            | ok       |                0.999262 |               1.04765  |                          0.0483852 |       -0.0419889  |        0.304444  |        0.306976  |        0.0457285  |                0.00253199 |           0.0300845  |     0.0204006   |  0           |            20 |          0   |                nan |            nan   |             nan |        0           |
| vos_trim_only_r1p0                       | ok       |                0.999262 |               1.05221  |                          0.0529519 |       -0.0168428  |        0.119381  |        0.121923  |        0.0182307  |                0.00254283 |           0.0119939  |     0.00313146  | -0.000496092 |            20 |          0   |                nan |            nan   |             nan |        0           |
| scheduled_slowfc2_k0p2_r1p0              | ok       |                0.999262 |               1.05444  |                          0.0551767 |       -0.00364045 |        0.0236609 |        0.026212  |        0.00466339 |                0.00255115 |           0.00306802 |     0.00777821  | -0.000496092 |             2 |          0.2 |                  1 |              7.2 |              30 |       -0.00072809  |
| rcl_only_r7p2                            | ok       |                7.19858  |               7.24896  |                          0.0503767 |       -0.0122788  |        0.0857337 |        0.0882791 |        0.0129372  |                0.00254532 |           0.00851133 |     0.000390026 |  0           |            20 |          0   |                nan |            nan   |             nan |        0           |
| vos_trim_only_r7p2                       | ok       |                7.19858  |               7.24895  |                          0.0503761 |       -0.012312   |        0.0859728 |        0.0885181 |        0.0129704  |                0.00254531 |           0.00853318 |     0.000390256 | -0.000496092 |            20 |          0   |                nan |            nan   |             nan |        0           |
| scheduled_slowfc2_k0p2_r7p2              | ok       |                7.19858  |               7.24996  |                          0.0513817 |       -0.00792373 |        0.0545022 |        0.0570501 |        0.00859792 |                0.00254793 |           0.00565653 |     0.000358467 | -0.000496092 |             2 |          0.2 |                  1 |              7.2 |              30 |       -0.00158471  |
| rcl_only_r100p0                          | ok       |               99.9883   |              99.0674   |                         -0.92091   |       -0.00687305 |        0.0474479 |        0.0499966 |        0.00696984 |                0.00254871 |           0.00458542 |     0.0053663   |  0           |            20 |          0   |                nan |            nan   |             nan |        0           |
| vos_trim_only_r100p0                     | ok       |               99.9883   |              99.0836   |                         -0.904776  |       -0.0114755  |        0.0803887 |        0.0829346 |        0.011573   |                0.00254589 |           0.00761378 |     0.0013081   | -0.000496092 |            20 |          0   |                nan |            nan   |             nan |        0           |
| scheduled_slowfc2_k0p2_r100p0            | ok       |               99.9883   |              99.0719   |                         -0.916427  |       -0.00687814 |        0.0469722 |        0.0495208 |        0.0069715  |                0.00254862 |           0.00458652 |     0.00143262  | -0.000496092 |             2 |          0.2 |                  1 |              7.2 |              30 |        0           |
| scheduled_slowfc2_k0p2_r20p0             | ok       |               19.9972   |              20.0196   |                          0.0224574 |       -0.00915254 |        0.0633491 |        0.0658963 |        0.00952825 |                0.00254715 |           0.00626859 |     0.00136929  | -0.000496092 |             2 |          0.2 |                  1 |              7.2 |              30 |       -0.00079961  |
| scheduled_slowfc2_k0p2_single_sine_fm100 | ok       |               45.937    |              -0.132699 |                        -46.0697    |       -0.0067779  |        0.0453356 |        0.0478829 |        0.0106736  |                0.00254742 |           0.00702208 |     0.00158056  | -0.000496092 |             2 |          0.2 |                  1 |              7.2 |              30 |       -0.000498096 |

## 仍需注意

1. 这三项修复没有彻底把 DC 偏置压到 <1 mA；要达到这个级别，需要再加入 AD633 `c0/cy` feedthrough trim，或者改成闭环阻抗伺服。
2. 当前 DC servo 用的是 `IPORT` 均值反馈，`fc=2Hz` 已低于 10Hz 最低调制频率，但对长期稳定性仍应跑更长时间窗。
3. 高阻区采用调度淡出是必要的；固定全局 trim 会让 100Ω 区 DC 偏置变差。
4. 动态 `Rtarget(t)` 必须用锁相/分频阻抗指标，不能用 fixed-R 的 `V/I` LS 指标直接判定。

## 生成文件

- `complete_fix_curated_comparison.csv`
- `complete_fix_improvement_table.csv`
- `complete_fix_verification_all.csv`
- `complete_fix_verification_key.csv`
- `cases/*/*.cir`, `*.log`, `*.csv`, `*_summary.json`
