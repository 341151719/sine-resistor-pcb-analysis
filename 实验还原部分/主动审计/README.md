# 主动审计复现入口

本目录检查的不是“某个 SPICE deck 是否成功结束”，而是模型是否真的包含它
声称检查的物理状态和网络。

主要内容：

- `ACTIVE_AUDIT_REPORT.md`：最终审计结论和解释边界；
- `spice_static_lint.py`：查找 E/S 硬钳、旧 C27/R10、绝对 include 路径和
  OPA548 供电节点断链特征；
- `release_assembly_crosscheck.py`：比较最终 V8 release 的 PCB、BOM 和 CPL；
- `corrected_decks/`：修正 OPA548 供电节点与 C27 后的 H07/H08 网表和历史日志；
- `run_checks.sh`：在当前仓库重新生成检查结果。

运行：

```bash
./run_checks.sh
```

若 ngspice 不在 `PATH`：

```bash
NGSPICE=/绝对路径/ngspice ./run_checks.sh
```

生成内容写入被 Git 忽略的 `results/`。H07 的 1 Ω/10 Ω 强故障仍可能发生
收敛失败；这必须解释成“该参数点未得到有效结果”，不能解释成物理振荡或稳定。

