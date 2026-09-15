# 主动审计复现入口

本目录检查的不是“某个 SPICE deck 是否成功结束”，而是模型是否真的包含它
声称检查的物理状态和网络。

主要内容：

- `EVIDENCE_REASSESSMENT_20260915.md`：修正峰值取电与持续 CC 混淆、证据因果推断和历史状态冲突。
- `reassess_evidence.py`：复跑四组平均/峰值电流、105 kHz 增益和四组较大启动扰动，并检查测量是否存在及有效。
- `ACTIVE_AUDIT_REPORT.md`：最终审计结论和解释边界；
- `spice_static_lint.py`：查找 E/S 硬钳、旧 C27/R10、绝对 include 路径和
  OPA548 供电节点断链特征；
- `release_assembly_crosscheck.py`：比较最终 V8 release 的 PCB、BOM 和 CPL；
- `corrected_decks/`：修正 OPA548 供电节点与 C27 后的 H07/H08 网表和历史日志；
- `run_checks.sh`：在当前仓库重新生成检查结果。

运行：

证据复核使用 `python3 reassess_evidence.py`（可从任意目录通过脚本路径运行）。
默认使用 ngspice-42，支持 `NGSPICE` 指定可执行文件；输出位于被忽略的
`results_reassessment/`，含生成的诊断 deck、日志与 `summary.json`。
生成的 deck 使用早期复现目录中的相对模型路径，手工复跑需以该目录为工作目录。
每个案例限时 60 秒；超时、缺失测量、非有限值或错误返回均失败，失败时 summary 不保留旧成功状态。

历史主动审计使用：

```bash
./run_checks.sh
```

若 ngspice 不在 `PATH`：

```bash
NGSPICE=/绝对路径/ngspice ./run_checks.sh
```

生成内容写入被 Git 忽略的 `results/`。H07 现在覆盖固定±10/±5 V偏置，
3.5586 mΩ/1 Ω/10 Ω三例均有完整结果；上电顺序仍在该deck范围之外。
`run_checks.sh`会检查失败字样、案例数和数据块数；ngspice退出0不再单独视为通过。
