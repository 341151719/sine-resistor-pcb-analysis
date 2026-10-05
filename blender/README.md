# V8 PCB Blender 模型与渲染

本目录提供从当前 KiCad V8 工程自动生成的 Blender 场景、脚本和渲染图。

## 输出文件

- [`output/c11_35_v8_pcb_model.blend`](output/c11_35_v8_pcb_model.blend)：可在 Blender 5.2.1 中打开的场景，包含等距相机和正视相机。
- [`output/c11_35_v8_pcb_isometric.png`](output/c11_35_v8_pcb_isometric.png)：整体等距渲染。
- [`output/c11_35_v8_pcb_top.png`](output/c11_35_v8_pcb_top.png)：正视工程布局渲染。
- [`generate_v8_pcb_scene.py`](generate_v8_pcb_scene.py)：可重复运行的生成脚本。

## 数据来源

脚本读取：

1. `KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04/project.kicad_pcb`
   - Edge.Cuts 板框；
   - F.Cu 走线；
   - 板厚和坐标。
2. `.../audit/cpl_smt.csv`
   - 73 个贴装件的位号、位置、旋转角、正反面和封装。

本次生成结果：

- 板框：约 `116.332 mm × 112.522 mm`；
- SMT 元件：73 个；
- F.Cu 线段：715 条。

## 精度边界

这是工程可读的程序化模型，不是制造级 3D 封装模型：

- 板框、元件位置和走线来自当前 KiCad 文件；
- 电阻、电容、IC、连接器等实体使用按封装尺寸的近似几何；
- 没有把外部供应商 STEP/WRL 模型伪装成精确模型；
- 为了在渲染中看清，铜线宽度按 `VISUAL_TRACE_SCALE=1.45` 做了视觉放大，不应拿渲染图测量实际线宽；
- 当前工程文件的 `cpl_smt.csv`/BOM 仍记录 `R10=100kΩ`、`C27=10pF`，而 [V8 发布说明](../KICAD部分/正弦电阻V8_KiCad10.0.4_稳定性修正版_2026-09-04/RELEASE_NOTES_V8.md) 写的是 `R10=6.8kΩ`、`C27=10nF`。本模型忠实显示当前 KiCad/CPL 文件内容，不能作为“V8 参数已同步”的证明。

## 重新生成

在仓库根目录执行：

```bash
PROJECT_ROOT="$PWD" \
BLENDER_OUT="$PWD/blender/output" \
/path/to/blender --background --python blender/generate_v8_pcb_scene.py
```

脚本默认使用 Blender Eevee，输出 `.blend`、等距图和正视图。若从其他目录运行，设置 `PROJECT_ROOT` 指向仓库根目录即可。
