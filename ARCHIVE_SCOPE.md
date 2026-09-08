# GitHub archive scope

本仓库采用私有归档策略，重点是审计可追溯性和可复核源码。

保留：

- V7 原始加工基线、V8 工作修正版、Gerber/BOM/CPL 和验证报告；
- SPICE 网表、官方/替代模型、脚本、需求与分析文字；
- 2026-09-08 故障假设的独立目录、完整日志和交叉审查。

排除：

- KiCad/ngspice/Python 安装包、压缩包和 wheel；
- `.dat` 波形、`results*`、`split_*`、`cases` 等可由网表重新生成的输出；
- Python 缓存、编译产物和机器相关 KiCad 首选项；
- 临时 Codex 审计目录、外部辅助 skill 和嵌套的独立固件 Git 仓库。

排除项不会改变原工作区文件，只是不进入本仓库。历史文本中可能出现
Windows/Linux 本地绝对路径；因此仓库默认保持私有。SPICE 网表若要在新
机器运行，应先把 `.include` 路径改为相对路径或本机路径，并以日志中的
模型版本为准。
