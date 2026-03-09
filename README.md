# Strip Field / Urban Field Generator

**城市线驱动向量场生成器** — 基于 Seed Curve 的非中心式扩张，用于城市形态学研究与参数化设计。

## 简介

本工具通过一条种子曲线（Seed Curve）生成可配置的向量场，支持多种扩张模式与场类型，可输出流线、街道网络和地块划分，适用于城市设计、形态学研究和参数化生成。

## 功能特性

- **三种运行模式**
  - **A - Flow Lines**：流线模式，展示向量场方向
  - **B - Street Network**：街道网络模式，生成纵向主街与横向连接
  - **C - Parcel Blocks**：地块模式，在街道网络基础上划分地块

- **七种场类型**
  1. Parallel Offset（平行偏移）
  2. Curve Tangent（曲线切向）
  3. Curve Normal（曲线法向）
  4. Distance Contour（距离等高线）
  5. Strip Growth（条带生长）
  6. Hybrid Tangent-Normal（混合切向-法向）
  7. Noise-Modified Line Field（噪声修正线场）

- **种子线类型**：直线、正弦波、弧线/曲线
- **扩张参数**：线间距、正负向数量、间距模式（线性 / 指数 / 斐波那契）、间距缩放
- **噪声与扰动**：可选的噪声扭曲，支持调节噪声尺度与强度
- **街道与地块参数**：横向道路间距、地块最小/最大尺寸、地块深度偏移

## 环境要求

- Python 3.x
- 标准库：`tkinter`（通常随 Python 安装）

## 安装与运行

```bash
# 克隆或进入项目目录
cd strip-field

# 直接运行（无需额外依赖）
python urban_field_gen.py
```

## 使用说明

1. 启动程序后，左侧为控制面板，右侧为预览画布。
2. 调整参数后，结果会实时更新。
3. 点击 **Generate** 重新生成，点击 **Reset** 恢复默认参数。
4. 可调整场地尺寸（Site Width / Height）、种子旋转、线间距等参数。
5. 在 Mode B 或 C 下可进一步设置街道与地块相关参数。
6. **导出到 Rhino**：点击 **Export .py (RhinoScript)** 保存 Python 脚本，在 Rhino 中打开 **EditPythonScript**，运行该脚本即可在视图中生成曲线；或点击 **Export DXF** 导出 DXF 文件（需 `pip install ezdxf`），在 Rhino 中直接导入。导出时以场地矩形（Site Width × Site Height）为边界，自动裁剪掉超出边界的线，仅保留内部部分。

## 项目结构

```
strip-field/
├── urban_field_gen.py   # 主程序入口
├── requirements.txt    # 可选依赖（DXF 导出需 ezdxf）
├── output.svg           # 示例输出
├── flow.svg
├── output_b.svg
├── output_c.svg
├── test_curve.svg
├── .gitignore
└── README.md
```

## 技术说明

- 采用笛卡尔坐标系，扩张向量基于曲线局部法向。
- 使用 Lattice Noise 实现简易噪声扰动。
- 界面为 Tkinter 深色主题，适合长时间使用。

## 版本

V.1.0 — Line-Driven Engine

## 许可证

仅供学习与研究使用。
