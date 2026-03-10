# Tensor Field / Urban Field Generator

**张量场城市形态生成器** — 支持多种张量场基底（Grid / Radial / Blend / Boundary / Height）与超流线追踪，用于城市形态学研究与参数化设计。

## 简介

本工具基于张量场（Tensor Field）生成城市形态，支持七种基底类型。可输出流线、街道网络、地块划分与超流线，适用于城市设计、形态学研究和参数化生成。

## 功能特性

- **张量场基底**（Tensor Field Basis）
  - **Grid**：正交网格基底，u=(1,0)、v=(0,1)
  - **Radial**：径向基底，以中心点为圆心的放射状场，支持多中心 RBF 加权
  - **Blend**：Grid 与 Radial 的混合，可调节 blend_factor
  - **Boundary**：边界场，从手绘曲线或遮罩图像提取边界方向
  - **Boundary+Grid**：边界与网格的混合
  - **Height**：高程场，从灰度高程图生成梯度方向
  - **Height+Grid**：高程与网格的混合

- **四种运行模式**
  - **A - Flow Lines**：流线模式，展示向量场方向
  - **B - Street Network**：街道网络模式，生成纵向主街与横向连接
  - **C - Parcel Blocks**：地块模式，在街道网络基础上划分地块
  - **D - Hyperstreamlines**：超流线模式，从张量场追踪主/副超流线，支持种子点、停止条件

- **边界输入**：手绘河流/边界曲线，或加载 GIF 遮罩图像
- **高程输入**：加载 PNG/JPG 高程图（需 Pillow），灰度→梯度→张量方向
- **扩张参数**：线间距、正负向数量、间距模式（线性 / 指数 / 斐波那契）、间距缩放
- **噪声与扰动**：可选的噪声扭曲，支持调节噪声尺度与强度
- **街道与地块参数**：横向道路间距、地块最小/最大面宽、最小面积、最大进深
- **地块划分模式**：临街面切分、按块切分、转角地块单独、不规则扰动（可单独开关）
- **道路等级**：primary / secondary / local，主骨架更明显
- **自适应横街**：根据曲率、吸引子距离、地价价值决定横街密度，不再固定 t 采样

- **论文式选项**（Paper-Style Options，参考 Chen et al. SIGGRAPH 2008）
  - **街道生成**：Parametric（参数化偏移）或 Hyperstreamline（超流线交替追踪）
  - **二阶段**：主路 → 分区 → 次路
  - **Perlin 旋转**：松弛正交性，产生有机街道模式
  - **Laplacian 平滑**：对张量场做网格平滑
  - **笔刷编辑**：绘制曲线设定局部张量方向

## 环境要求

- Python 3.x
- 标准库：`tkinter`（通常随 Python 安装）
- 可选：`ezdxf`（DXF 导出）、`Pillow`（高程图 PNG/JPG 支持）

## 安装与运行

```bash
# 克隆或进入项目目录
cd tensor-field

# 直接运行（无需额外依赖）
python main.py
```

## 使用说明

1. 启动程序后，左侧为控制面板，右侧为预览画布。右上角可切换 **EN / 中文** 界面。画布支持滚轮缩放、右键拖拽平移、双击重置视图。
2. 选择 **Run Mode**：A 流线 / B 街道网络 / C 地块 / D 超流线。
3. 选择 **Tensor Basis**：Grid / Radial / Blend / Boundary / Boundary+Grid / Height / Height+Grid。
4. **Boundary** 基底：勾选 Use River Boundary，可手绘河流或加载 GIF 遮罩图。
5. **Height** 基底：勾选 Use Height Map，加载 PNG/JPG 高程图（需 `pip install Pillow`）。
6. **Radial / Blend**：可点击 Add Center 在画布上添加多个张量中心，拖拽调整位置。
7. **论文式选项**：Street Gen 选 Hyperstreamline 可启用超流线街道生成；勾选 Two-Stage 启用主路→次路二阶段；Perlin Strength 调节旋转噪声；Laplacian Smooth 平滑张量场；Draw Brush 绘制笔刷曲线设定局部方向。
8. 调整参数后，结果会实时更新。点击 **Generate** 重新生成，**Reset** 恢复默认。
9. 在 Mode B 或 C 下可进一步设置街道与地块相关参数。
10. **导出到 Rhino**：**Export .py (RhinoScript)** 保存脚本，在 Rhino 的 EditPythonScript 中运行；**Export DXF** 导出 DXF（需 `pip install ezdxf`）。导出时以场地矩形为边界自动裁剪。

## 项目结构

```
tensor-field/
├── main.py                      # 程序入口
├── app.py                       # 主应用（UI + 逻辑编排）
├── app_single_file.py           # 单文件构建（由 build_single_file.py 生成）
├── build_single_file.py         # 构建脚本
├── tensor_field.py              # 张量场（7 种基底、街道生成、Laplacian 平滑、笔刷）
├── i18n.py                      # 中英文双语界面
├── config.py                    # 配置常量（T_STEP, T_COUNT, DRAW_PADDING）
├── utils.py                     # 工具函数（perlin_noise, safe_float, safe_int）
├── geom.py                      # 几何裁剪（线段/折线/多边形裁剪到矩形）
├── curve.py                     # 曲线插值（Catmull-Rom 样条、弧长采样）
├── street_network.py            # 街道网络（道路等级、自适应横街）
├── boundary_field.py            # 边界场（曲线/遮罩图→边界方向）
├── height_field.py              # 高程场（灰度高程图→梯度→张量基底）
├── hyperstreamline.py           # 超流线（主/副追踪、种子点、停止条件）
├── street_from_hyperstreamlines.py  # 论文式街道生成（交替追踪、交点图、二阶段）
├── parcel_subdivision.py        # 地块划分（frontage-based、block-by-block、转角、扰动）
├── exporter.py                  # 导出逻辑（RhinoScript、DXF）
├── requirements.txt             # 可选依赖（ezdxf: DXF 导出，Pillow: 高程图 PNG/JPG）
└── README.md
```

## 引擎架构

- **Tensor Field**：`tensor_field.py` 提供七种基底（Grid / Radial / Blend / Boundary / Boundary+Grid / Height / Height+Grid），每个点有两组互相垂直的方向 (u, v)。支持 `sample_tensor_field_grid` 采样与 `generate_streets_from_tensor_field` 街道生成。
- **Boundary Field**：`boundary_field.py` 从手绘曲线或遮罩图像提取边界方向，用于 Boundary 基底。
- **Height Field**：`height_field.py` 从灰度高程图计算梯度，转为张量方向，用于 Height 基底。
- **Hyperstreamline**：`hyperstreamline.py` 从张量场追踪主(u)/副(v)超流线，RK4 积分，停止条件：边界、最大长度、角度突变。
- **Street from Hyperstreamlines**：`street_from_hyperstreamlines.py` 实现论文式街道生成：主/副超流线交替追踪、交点构建图、二阶段主路→次路。

## 技术说明

- 采用笛卡尔坐标系，张量场基于 2×2 对称无迹矩阵表示（参考 Chen et al. SIGGRAPH 2008）。
- 使用 Perlin 噪声（论文 5.3）实现旋转场，产生有机街道模式。
- 界面为 Tkinter 深色主题，适合长时间使用。

## 版本

V.1.3 — 论文式：超流线街道、交替追踪、二阶段、Perlin 旋转、Laplacian 平滑、笔刷编辑

## 许可证

仅供学习与研究使用。
