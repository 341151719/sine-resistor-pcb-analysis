# 正弦电阻 V7 — KiCad 10.0.4 校正转换版

来源：`正弦电阻V7kicad2026-08-12.epro`。
参数基准：`BOM最终版(1).xlsx`，并用生产 BOM / PASTER BOM 做 LCSC 编号交叉核验。

## 转换完整性

- EPRO 原理图组件：142；KiCad：142；位号集合一致。
- EPRO PCB 组件：141；KiCad：141；位号集合一致。
- EPRO PCB 网络：76；KiCad：76；网络名称集合一致。
- BOM 受控位号：119 = 73 SMT + 44 DNP + 2 后焊；校正后 BOM 字段审计错误为 0。
- 22 个非采购板级对象（J7 裸 SWD 焊盘、TP1~TP21）已排除 BOM/CPL。
- 原导入缺失的 21 个连接器焊盘 net 属性已按原理图 netlist 恢复；最终 PCB DRC 为 0 unconnected，且 shorting_items 已清零。
- 已从 PCB 内嵌封装恢复项目级 `easyedapro.pretty`（20 种封装）。
- 已重建 `easyedapro.kicad_sym`（41 个符号定义），消除了导入后的 symbol library mismatch。

## BOM 校正

原转换中有大量 Value/装配状态与最终制造 BOM 不一致。共 96 个受控位号的可见 Value 被规范化，其中 SMT 53 个、DNP 41 个、后焊 2 个。
典型关键修正包括：

- C1/C2：2.2uF → 10uF（C15850）
- C3：10uF → 100nF（C49678）
- C17：10uF → 10nF（C342877）
- C24：220nF → 4.7uF（C380342）
- C28：`100nF ... DNP` → 1uF，并恢复 C0805 封装（C344178）
- R7：100R → 57.6kR（C5153977）
- R12：2mR → 4.7R / 2W（C2897629）
- R16：1kR → 39.0kR（C1720356）
- R18：1.6R → 100R（C2988937）
- R19：1.6R → 30.9kR（C865394）
- R34/R35：由文本 DNP 状态恢复为 SMT 装配件，并恢复 R0805 封装。
- 44 个 DNP 位号已使用 KiCad 原生 DNP 标志，不再仅靠 Value 文本表示。

## DRC / ERC

最终 ERC：436 条。已消除 annotation、library mismatch 和 footprint-link 类导入问题。剩余主要是 EasyEDA 符号电气 pin type 与 KiCad ERC 语义差异，以及原图端点/网格问题；没有发现组件或网络集合缺失。

最终 DRC：163 条，0 unconnected。源 EasyEDA 的 4 mil clearance / 10 mil 默认走线规则已迁移到 KiCad。剩余主要为：annular_width=72, silk_over_copper=40, hole_clearance=23, courtyards_overlap=15, copper_edge_clearance=7, silk_overlap=3, clearance=1, via_dangling=1, track_dangling=1。这些是原 PCB 几何/制造约束问题，未在“格式转换”阶段自动移动铜、过孔或丝印。

## 3D 模型限制

源 `.epro` 压缩包本身不包含 STEP/WRL/OBJ 模型 payload。KiCad PCB/封装中保留了原 importer 生成的 `${KIPRJMOD}/EASYEDA_MODELS/...` 引用，但当前无法从源文件恢复模型实体。因此：电气/PCB/BOM/制造数据已完整转换，3D 模型不是完整自包含状态。

## 文件说明

- `project.kicad_pro / .kicad_sch / .kicad_pcb`：校正后的主工程。
- `easyedapro.kicad_sym` + `sym-lib-table`：项目符号库。
- `easyedapro.pretty` + `fp-lib-table`：项目封装库。
- `audit/bom_engineering.csv`：119 位号工程总 BOM。
- `audit/bom_smt_73.csv`：73 位号 SMT BOM。
- `audit/bom_dnp_44.csv`：44 位号 DNP 清单。
- `audit/bom_post_2.csv`：J12/J13 后焊清单。
- `audit/cpl_smt.csv`：73 行 SMT CPL。
- `audit/erc_after3.json`、`audit/drc_final.json`：最终检查报告。
- `audit/parameter_changes.csv`：BOM 校正前后逐位号对照。
