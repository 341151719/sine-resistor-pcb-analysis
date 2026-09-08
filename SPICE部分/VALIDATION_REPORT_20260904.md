# SPICE_project_repaired_20260710_FINAL.zip 可运行性验证报告

验证日期：2026-09-04（Asia/Shanghai）

## 结论

**原 ZIP 不能原样执行源码所定义的 `complete` 完整套件，因此不能判定为“完整可跑”。**

- 快速冒烟工况可以运行并通过。
- 固定阻值和动态正式签核入口均可完整执行，但工程指标不通过。
- `complete` 原样启动时立刻因缺少两个电路模板而退出。
- 从用户指出的 v4.5 目录补齐模板后，`complete` 的 57 个工况均被调度；39 个数值完成，18 个 ngspice 失败；完成的工况中 33 个验收通过、6 个验收失败。
- MCU 固件源码不在包中，固件行为只能判为 `not_auditable`。

因此应区分：

1. Linux/ngspice/Python 运行环境可用；
2. 主仿真链路可启动；
3. 原 ZIP 的完整回归打包不完整；
4. 当前设计尚未达到 1–100 Ω、10–1000 Hz 的动态签核目标。

## 输入文件与完整性

| 文件 | SHA-256 | ZIP 检查 |
|---|---|---|
| `SPICE_project_repaired_20260710_FINAL.zip` | `90608bf979f47885d40b6cf487b2687b21ee009db6870aefc025ae112de19dda` | 无压缩错误 |
| `环境/SPICE_project_repaired_20260710_FINAL.zip` | 同上 | 与工作区 ZIP 字节一致 |
| `环境/ngspice_runtime_linux_x86_64.zip` | `80cbc990e212c56c660a8e83001bded94a56db167b9cb6545a7d442049d5aea1` | 无压缩错误 |
| `环境/spice_python_cp313_linux.zip` | `40de8d391eaf9cca35156e0cd18757af1d2ca60b62498a30b4211de192de3bf8` | 无压缩错误 |

项目清单声明的 56 个文件在全新解压副本中全部存在，大小与 SHA-256 全部匹配。问题不是 ZIP 损坏，而是清单和包本身没有收入完整套件所引用的两个模板。

## Linux 环境

- 系统：Linux/WSL x86-64。
- ngspice：环境包自带 ngspice 42，可启动，`ldd` 未发现缺失动态库。
- Python：系统 CPython 3.12.3。
- 已用依赖：NumPy 2.4.6、Pandas 3.0.5、Matplotlib 3.11.1，满足项目的 `numpy>=2.0`、`pandas>=2.0`、`matplotlib>=3.8`。
- `spice_python_cp313_linux.zip` 中包含 CPython 3.13 ABI 轮子，不能直接安装到当前 Python 3.12；本机已有满足要求的兼容版本，因此无需联网下载或修改系统 Python。

运行时通过 `NGSPICE_BIN=<解压后的绝对路径>/bin/ngspice` 指定 ngspice，没有进行永久系统级修改。

## 原包原样测试

### 结构、自检和冒烟

| 项目 | 结果 |
|---|---|
| `scripts/check_project.py` | pass |
| `tests/test_validation_metrics.py` | pass |
| firmware audit | `not_auditable`，源码数 0 |
| 7.2 Ω / 1 kHz quick smoke | 数值完成，验收 pass，退出码 0 |

注意：`check_project.py` 只检查 `full_component_template.cir`，没有检查完整套件还会引用的 ideal/behavioral 模板，所以结构自检出现假阴性。

### `complete` 原样启动

原包在第一个工况 `ideal_single_sine` 立即退出：

```text
FileNotFoundError: spice/circuits/ideal_reference_template.cir
```

同时缺少：

- `spice/circuits/ideal_reference_template.cir`
- `spice/circuits/behavioral_chain_template.cir`

`scripts/run_sweeps.py` 明确引用这两个文件，但它们没有进入 FINAL ZIP。

## 补齐模板后的完整运行

两个缺失模板可在以下位置找到：

`C:\Users\Administrator\Downloads\active_acoustic_impedance_v4_5_auditable_ngspice_launch_path_fix\spice\circuits`

它们也存在于 `需求背景与SPICE.zip` 内嵌 v3.3 项目中；两处文件逐字节一致：

| 模板 | SHA-256 |
|---|---|
| `ideal_reference_template.cir` | `3fe9f06ddd96b567ec9be27f45467f163296e7fc191cc0fe520934facd8c1f83` |
| `behavioral_chain_template.cir` | `c3ac5ab868d820d0da46c700945c3a65f96afeb3be29e067ba35549e488cca86` |

仅在验证副本补齐文件后执行：

```bash
python3 scripts/run_sweeps.py \
  --clean \
  --results-dir results_complete_runtime_patched \
  --suite complete \
  --model-lib official-pure \
  --no-plots \
  --no-case-csv
```

结果：

| 指标 | 数量 |
|---|---:|
| 总工况 | 57 |
| ngspice 数值完成 | 39 |
| ngspice 失败 | 18 |
| 验收通过 | 33 |
| 验收失败 | 6 |
| 因仿真失败未评估 | 18 |
| 进程退出码 | 2 |

18 个数值失败的分类：

- 16/16 个寄生参数工况全部在初始工作点失败，典型日志为 `Transient op failed, timestep too small`，问题节点位于纯厂商宏模型的 OPA548/AD633 内部。
- `full_single_sine_ilim2a` 在初始工作点失败，OPA548 宏模型内部二极管出现 `timestep too small`。
- `fault_speaker_open_r1` 在约 8.007 ms 处步长缩小至 `1.25e-18` 后失败。

完成后仍验收失败的主要工况：

- 1 Ω / 1 kHz：实部约 1.05369 Ω，但虚部 0.341832 Ω，大于 0.1 Ω 限值。
- 100 Ω / 1 kHz：实部约 98.8159 Ω，虚部 -5.60541 Ω，超过约 4.99942 Ω 限值。
- 1 Ω / 5 kHz：实部误差约 0.434583 Ω，虚部约 1.76349 Ω，均超限。
- 1 kHz 载波下的单正弦动态电流注入：p95 实部相对误差约 1.08996，虚部相对值约 0.613279，均高于 0.1。
- 扬声器短路故障：DC 端口电流约 1.55098 A，限流比约 1.02038，未满足安全判据。
- RSH 开路故障：饱和裕量违规约 1.71487 V。

## 正式固定阻值签核

5 个 ngspice 工况全部数值完成；3 个通过，2 个失败，汇总/脚本退出码 3。

| 目标 | 实部 Ω | 虚部 Ω | 验收 |
|---:|---:|---:|---|
| 1 Ω | 1.053687 | 0.341832 | fail：虚部超限 |
| 5 Ω | 5.045566 | 0.122007 | pass |
| 7.2 Ω | 7.248699 | -0.007874 | pass |
| 20 Ω | 20.000767 | -0.766657 | pass |
| 100 Ω | 98.815931 | -5.605413 | fail：虚部超限 |

`RUN_FIXED_SIGNOFF_SPLIT.sh` 本身也已完整执行，逐工况调度和最终聚合正常。

## 正式动态签核

5 个 ngspice 工况全部数值完成，但 5 个全部验收失败，汇总/脚本退出码 3。

| 调制频率 | p95 实部相对误差 | p95 虚部相对值 | 限值 | 验收 |
|---:|---:|---:|---:|---|
| 10 Hz | 0.482850 | 1.030622 | 0.1 | fail |
| 30 Hz | 0.564615 | 1.199943 | 0.1 | fail |
| 100 Hz | 0.698100 | 1.749187 | 0.1 | fail |
| 300 Hz | 0.883115 | 1.084344 | 0.1 | fail |
| 1000 Hz | 1.154846 | 2.881177 | 0.1 | fail |

`RUN_DYNAMIC_SIGNOFF_SPLIT.sh` 本身也已完整执行，逐工况调度和最终聚合正常。

## 与需求背景对照

| 需求 | 覆盖情况 | 结论 |
|---|---|---|
| 扬声器参数 Re=7.2 Ω、Le=0.2 mH、Bl=4.6 Tm、Mms=5.7 g、fs=90 Hz、Qms=2.29、Sd=0.005 m² | 配置一致 | 覆盖 |
| Python + ngspice | 实际使用 Python 3.12 + ngspice 42 | 可运行 |
| 理想、行为、真实器件模型 | 单/双正弦三种模型工况均存在；补齐模板后可跑 | 原 ZIP 打包缺文件 |
| 固定 1、5、7.2、20、100 Ω | 全部数值完成 | 1 Ω、100 Ω 未签核 |
| 单正弦动态变化 | 有基线与电流注入签核 | 严格动态指标未通过 |
| 双正弦叠加 | ideal/behavioral/full 基线均数值完成且安全类判据通过 | 尚非动态电阻精度签核 |
| 10–1000 Hz 调制 | 10、30、100、300、1000 Hz 正式签核均完成 | 5/5 未通过动态精度 |
| 寄生参数与异常工况 | 16 个寄生、7 个故障工况已调度 | 纯厂商模型下存在大量收敛失败及安全失败 |
| 固件控制 | 包中无 MCU 源码 | 不可审计 |

项目自带 README 已声明“不声称完整 1–100 Ω、10–1000 Hz 动态目标通过”，本次实跑与该声明一致。

## 建议的修包动作

1. 把上述两个缺失模板加入 FINAL ZIP，并加入 `PACKAGE_MANIFEST_REPAIRED.json`。
2. 修改 `scripts/check_project.py`，把两个模板加入 `REQUIRED`，防止冒烟通过但完整套件启动失败。
3. 在 README 中明确区分 `quick smoke`、`complete`、fixed signoff、dynamic signoff，并写明退出码 2/3 的含义。
4. 对寄生工况增加适用于官方 PSpice 宏模型的启动/收敛策略，或明确这些工况需使用经过验证的 ngspice 兼容模型；不能把当前 16/16 失败写成完成验证。
5. 调整动态前馈/相位补偿后重新签核，当前动态误差远高于 10% 限值。
6. 补充真实 MCU 固件及上电、限幅、故障关断逻辑后再做控制路径签核。

## 验证产物

验证副本根目录：

`validation_workspace_20260904_19wI9s`

主要结果：

- `project/SPICE_project_repaired_20260710_FINAL/1SPICE_SPICE_SIM/results_complete_runtime_patched/`
- `project/SPICE_project_repaired_20260710_FINAL/1SPICE_SPICE_SIM/results_fixed_signoff_runtime/`
- `project/SPICE_project_repaired_20260710_FINAL/1SPICE_SPICE_SIM/results_dynamic_signoff_runtime/`
- `project/SPICE_project_repaired_20260710_FINAL/1SPICE_SPICE_SIM/results_fixed_signoff_combined/`
- `project/SPICE_project_repaired_20260710_FINAL/1SPICE_SPICE_SIM/results_dynamic_signoff_combined/`

为减少磁盘占用，完整运行关闭了 PNG 和逐点派生 CSV；每个工况的原始 `.dat`、ngspice `.log`、渲染后的 `.cir`、配置 JSON、摘要 JSON，以及总表和报告均保留。
