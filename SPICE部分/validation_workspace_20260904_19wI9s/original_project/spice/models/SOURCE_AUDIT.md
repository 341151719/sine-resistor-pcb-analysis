# 模型来源与替换审计

## 默认模型

`ngspice_compatible_macros.lib` 是本项目生成的 surrogate macromodel 集合，不是 TI/ADI 官方模型。它的目的：

- 让电路以完整器件接口方式接入；
- 引入有限带宽、输出摆幅、限流、输入/输出负载等一阶非理想；
- 保持 ngspice 兼容，便于批处理扫参；
- 允许后续用官方宏模型逐步替换。

## 为什么没有直接把官方宏模型改写进默认库

1. AD633 官网模型下载会跳转到 ADI SPICE Model License Agreement，需要用户/公司确认许可后下载。
2. TI 的 PSpice/TINA 模型通常以 ZIP/TSC 发布，可能包含 PSpice/TINA 语法，需要本地清理后才能被 ngspice 接受。
3. 本项目的仿真目标是先验证全链路稳定性和应力边界；供应商模型替换后必须重新跑 `macro_smoke_tests.cir` 与全套 `run_sweeps.py`。

## 替换流程

1. 运行：

```bash
python scripts/fetch_vendor_models.py --print-links
```

2. 本地打开链接并确认厂商许可证。
3. 将下载的 `.lib/.cir/.sub/.mod` 放入：

```text
spice/models/vendor_downloads/
```

4. 在 netlist 中把：

```spice
.include ../models/ngspice_compatible_macros.lib
```

替换为官方模型 `.include`，并修正 `XU...` 子电路名称和 pin order。

5. 先跑：

```bash
ngspice -b spice/circuits/macro_smoke_tests.cir
```

6. 再跑全量扫描。

## v2 repair note

`ngspice_compatible_macros.lib` was repaired on 2026-05-22 after uploaded results showed every full-component case pinned near the OPA548 current limit. The root cause was not an external vendor model issue; it was the local surrogate model's behavioral current-source polarity.

The original v1 surrogate is retained as:

```text
spice/models/ngspice_compatible_macros_faulty_legacy.lib
```

Do not use the legacy file for design validation except when reproducing the old failure.
