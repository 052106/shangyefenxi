"""
viz_helpers.py —— 绘图“零件库”（渐变、圆角、水球、玫瑰、仪表盘等非标准图形）
--------------------------------------------------------------------------------
Matplotlib 默认没有渐变填充、圆角柱、水球图等能力，本文件用底层 Path/Patch/imshow
自行实现，保证模板复现图在视觉上贴近《Excel数据可视化》原作的“商务图表”质感。
所有函数只负责画，不做业务计算。
"""

from __future__ import annotations

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Rectangle, Wedge


# ---------------------------------------------------------------- 颜色
def lighten(color, amount: float = 0.55):
    """把颜色向白色方向提亮，amount=0 原色、1 纯白。"""
    r, g, b = to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def darken(color, amount: float = 0.25):
    """把颜色向黑色方向压暗。"""
    r, g, b = to_rgb(color)
    return (r * (1 - amount), g * (1 - amount), b * (1 - amount))


# ---------------------------------------------------------------- 渐变柱
def gradient_bar(ax, x, height, width, color, bottom=0.0,
                 top_light: float = 0.70, horizontal: bool = False,
                 zorder: int = 3, alpha: float = 1.0, shadow: float = 0.05):
    """
    画一根“自下而上由深到浅”的渐变柱（Excel 渐变柱形图的经典做法）。
    实现：先用 Rectangle 定出柱形区域，再用 imshow 铺渐变图并按柱形 Path 裁剪。
    """
    if height is None or height <= 0:
        return
    if not horizontal:
        if shadow:
            ax.add_patch(Rectangle((x - width / 2 + width * 0.10, bottom),
                                   width, height, facecolor="#1F2A37",
                                   alpha=shadow, zorder=zorder - 1, linewidth=0))
        rect = Rectangle((x - width / 2, bottom), width, height)
        ax.add_patch(rect)
        grad = np.linspace(0, 1, 256).reshape(-1, 1)
        cmap = LinearSegmentedColormap.from_list("g", [color, lighten(color, top_light)])
        im = ax.imshow(grad, extent=[x - width / 2, x + width / 2, bottom, bottom + height],
                       aspect="auto", cmap=cmap, origin="lower", zorder=zorder, alpha=alpha)
        im.set_clip_path(rect)
    else:
        rect = Rectangle((0, x - width / 2), height, width)
        ax.add_patch(rect)
        grad = np.linspace(0, 1, 256).reshape(1, -1)
        cmap = LinearSegmentedColormap.from_list("g", [color, lighten(color, top_light)])
        im = ax.imshow(grad, extent=[0, height, x - width / 2, x + width / 2],
                       aspect="auto", cmap=cmap, origin="lower", zorder=zorder, alpha=alpha)
        im.set_clip_path(rect)
    rect.set_facecolor("none")
    rect.set_edgecolor("none")


def rounded_gradient_bar(ax, x, height, width, color, radius_frac: float = 0.42,
                         bottom: float = 0.0, zorder: int = 3, top_light: float = 0.62):
    """
    渐变 + 圆角柱（对应模板“渐变圆角柱形图”）：
    用 FancyBboxPatch 画顶部圆角柱体，再用 imshow 做纵向渐变裁剪。
    """
    if height is None or height <= 0:
        return
    r = min(width * radius_frac, height * 0.95)
    box = FancyBboxPatch((x - width / 2, bottom), width, max(height, 1e-6),
                         boxstyle=f"round,pad=0,rounding_size={r}",
                         linewidth=0, facecolor="none", zorder=zorder)
    ax.add_patch(box)
    grad = np.linspace(0, 1, 256).reshape(-1, 1)
    cmap = LinearSegmentedColormap.from_list("g", [color, lighten(color, top_light)])
    im = ax.imshow(grad, extent=[x - width / 2, x + width / 2, bottom, bottom + height],
                   aspect="auto", cmap=cmap, origin="lower", zorder=zorder)
    im.set_clip_path(box)


# ---------------------------------------------------------------- 标注
def callout(ax, x, y, text, color="#1F2A37", bg="white", edge="#DCE3EC",
            dy=0.07, fontsize=9, bold=True, arrow=True):
    """
    柱顶“引线 + 圆角标签”标注（对应模板“标注柱形图”）。
    dy 为相对当前 y 轴高度比例的偏移，避免不同量纲下标签重叠。
    """
    ymin, ymax = ax.get_ylim()
    off = (ymax - ymin) * dy
    ax.annotate("", xy=(x, y), xytext=(x, y + off * 0.8),
                arrowprops=dict(arrowstyle="-", color=color, lw=0.8, alpha=0.45),
                zorder=6, annotation_clip=False) if arrow else None
    ax.text(x, y + off, text, ha="center", va="bottom", fontsize=fontsize,
            color=color, fontweight="bold" if bold else "normal", zorder=7,
            bbox=dict(boxstyle="round,pad=0.34", facecolor=bg, edgecolor=edge,
                      linewidth=0.8, alpha=0.98))


def value_labels(ax, xs, ys, fmt="{:,.0f}", color="#1F2A37", fontsize=8.5,
                 dy=0.012, bold=False):
    """统一在柱顶/点上方写数值标签。"""
    ymin, ymax = ax.get_ylim()
    for x, y in zip(xs, ys):
        if y is None or (isinstance(y, float) and np.isnan(y)):
            continue
        ax.text(x, y + (ymax - ymin) * dy, fmt.format(y), ha="center", va="bottom",
                fontsize=fontsize, color=color,
                fontweight="bold" if bold else "normal", zorder=6)


# ---------------------------------------------------------------- 平滑曲线
def smooth_curve(x, y, n: int = 320):
    """单调三次插值（PCHIP）生成平滑曲线：保留极值、不产生虚假过冲。"""
    from scipy.interpolate import PchipInterpolator
    f = PchipInterpolator(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    xs = np.linspace(float(min(x)), float(max(x)), n)
    return xs, f(xs)


def gradient_area(ax, x, y, color, base=0.0, alpha=0.45, zorder=2):
    """平滑曲线下的渐变面积（自下而上由淡到浓），增强折线图层次感。"""
    poly = ax.fill_between(x, y, base, color="none", zorder=zorder)
    grad = np.linspace(0, 1, 256).reshape(-1, 1)
    cmap = LinearSegmentedColormap.from_list(
        "ga", [to_rgb(color) + (0.02,), to_rgb(color) + (alpha,)])
    im = ax.imshow(grad, extent=[float(min(x)), float(max(x)), base, float(max(y))],
                   aspect="auto", cmap=cmap, origin="lower", zorder=zorder)
    im.set_clip_path(poly.get_paths()[0], ax.transData)


# ---------------------------------------------------------------- 圆环 / 水球
def donut(ax, pct: float, color: str, track: str = "#E9EFF6",
          label: str = "", sub: str = "", width: float = 0.22,
          text_color: str = "#1F2A37", fontsize: int = 30, start: float = 90):
    """
    单值圆环图（对应模板“单值圆环图”）：灰色轨道 + 高亮进度环 + 中心大号数字。
    """
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Wedge((0, 0), 1, 0, 360, width=width, facecolor=track, edgecolor="none"))
    theta = start - 360 * pct
    ax.add_patch(Wedge((0, 0), 1, theta, start, width=width, facecolor=color, edgecolor="none"))
    a = np.deg2rad(theta)
    ax.add_patch(Circle((np.cos(a) * (1 - width / 2), np.sin(a) * (1 - width / 2)),
                        width / 2 * 0.98, color=color, zorder=5))
    ax.text(0, 0.06, label or f"{pct:.1%}", ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=text_color)
    if sub:
        ax.text(0, -0.24, sub, ha="center", va="center", fontsize=fontsize * 0.40,
                color="#6B7A90")
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)


def liquid_fill(ax, pct: float, color: str, text_color="#E6EDF7",
                bg="#0A1020", waves: int = 3, amp: float = 0.020):
    """
    水球图（对应模板“水球图”）：圆形裁剪 + 多层正弦波液面 + 中心百分比。
    """
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.add_patch(Circle((0, 0), 1.00, facecolor=bg, edgecolor="none", zorder=0))
    clip = Circle((0, 0), 1.0, transform=ax.transData)
    ax.add_patch(Circle((0, 0), 1.03, facecolor="none", edgecolor=color, lw=1.2, alpha=0.30))
    ax.add_patch(Circle((0, 0), 1.00, facecolor="none", edgecolor=color, lw=2.4, alpha=0.75))

    level = -1 + 2 * max(min(pct, 1.0), 0.0)
    xs = np.linspace(-1.15, 1.15, 500)
    for k in range(waves):
        ys = level + amp * np.sin(2.6 * np.pi * xs + k * np.pi / 2.6)
        poly = ax.fill_between(xs, ys, -1.25, color=color, alpha=0.80 - 0.24 * k,
                               linewidth=0, zorder=2 + k)
        poly.set_clip_path(clip)
    ax.text(0, 0, f"{pct:.1%}", ha="center", va="center", fontsize=32,
            fontweight="bold", color=text_color, zorder=9)


# ---------------------------------------------------------------- 玫瑰 / 仪表盘 / 子弹 / 滑珠
def nightingale(ax, values, labels, colors):
    """
    南丁格尔玫瑰图：极坐标扇形柱，半径映射数值、角度均分，中心留白。
    """
    n = len(values)
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    width = 2 * np.pi / n * 0.88
    vmax = float(max(values))
    ax.set_theta_direction(-1)
    ax.set_theta_offset(np.pi / 2)
    for t, v, c in zip(theta, values, colors):
        ax.bar(t, v, width=width, bottom=0, color=c, edgecolor="white",
               linewidth=1.5, alpha=0.93, zorder=3)
    ax.set_ylim(0, vmax * 1.16)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    ax.grid(False)
    for t, v, lab in zip(theta, values, labels):
        ax.text(t, vmax * 1.10, f"{lab}\n{v / 1e4:,.0f} 万", ha="center", va="center",
                fontsize=8.6, color="#1F2A37", zorder=5)


def gauge(ax, value: float, vmin: float = 0, vmax: float = 1.0, color="#3A7BD5",
          title: str = "", unit: str = "", segments=None, text_color="#1F2A37",
          fmt=None):
    """
    仪表盘图：180° 弧形表盘 + 刻度 + 指针 + 中心数值（对应模板“仪表盘图”）。
    """
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.32, 1.32)
    ax.set_ylim(-0.42, 1.22)
    width = 0.26
    ax.add_patch(Wedge((0, 0), 1.0, 0, 180, width=width, facecolor="#E9EFF6", edgecolor="none"))
    if segments:
        start = 180
        for frac, c in segments:
            ang = 180 * frac
            ax.add_patch(Wedge((0, 0), 1.0, start - ang, start, width=width,
                               facecolor=c, edgecolor="white", linewidth=1.6))
            start -= ang
    else:
        ang = 180 * (value - vmin) / (vmax - vmin)
        ax.add_patch(Wedge((0, 0), 1.0, 180 - ang, 180, width=width, facecolor=color,
                           edgecolor="none"))
    for i in range(11):
        a = np.deg2rad(180 - i * 18)
        r0 = 0.64
        r1 = 0.70 if i % 5 == 0 else 0.675
        ax.plot([np.cos(a) * r0, np.cos(a) * r1], [np.sin(a) * r0, np.sin(a) * r1],
                color="#94A3B8", lw=1.1)
        if i % 5 == 0:
            val = vmin + (vmax - vmin) * i / 10
            txt = f"{val:.0%}" if vmax <= 1.5 else f"{val:,.0f}"
            ax.text(np.cos(a) * 0.55, np.sin(a) * 0.55, txt, ha="center", va="center",
                    fontsize=8, color="#6B7A90")
    ang = np.deg2rad(180 - 180 * (value - vmin) / (vmax - vmin))
    ax.plot([0, np.cos(ang) * 0.70], [0, np.sin(ang) * 0.70], color=color, lw=3.4,
            solid_capstyle="round", zorder=6)
    ax.add_patch(Circle((0, 0), 0.05, color=color, zorder=7))
    txt = fmt(value) if fmt else (f"{value:.1%}" if vmax <= 1.5 else f"{value:,.0f}{unit}")
    ax.text(0, -0.16, txt, ha="center", va="center", fontsize=21, fontweight="bold",
            color=text_color)
    if title:
        ax.text(0, 1.14, title, ha="center", va="center", fontsize=11.5, color=text_color,
                fontweight="bold")


def bullet(ax, y, actual: float, target: float, ranges: list,
           color="#3A7BD5", track_colors=("#EFF4FA", "#DEE8F4", "#CBD9EB"), height=0.34):
    """子弹图：背景三档 + 实绩条 + 目标竖线（对应模板“子弹图”）。"""
    for i, (hi, c) in enumerate(zip(ranges, track_colors)):
        lo = 0 if i == 0 else ranges[i - 1]
        ax.add_patch(Rectangle((lo, y - height / 2), hi - lo, height,
                               facecolor=c, edgecolor="none", zorder=1))
    ax.add_patch(Rectangle((0, y - height / 5.6), actual, height / 2.8,
                           facecolor=color, edgecolor="none", zorder=3))
    ax.plot([target, target], [y - height / 1.85, y + height / 1.85],
            color="#1F2A37", lw=2.0, zorder=4)


def dumbbell(ax, y, x1, x2, color1, color2, lw=3.2, size=110):
    """滑珠图（哑铃图）：同一维度两个时点之间的连线 + 端点圆珠。"""
    ax.plot([x1, x2], [y, y], color="#CBD9EB", lw=lw, solid_capstyle="round", zorder=2)
    ax.scatter([x1], [y], s=size, color=color1, zorder=4, edgecolors="white", linewidths=1.5)
    ax.scatter([x2], [y], s=size, color=color2, zorder=4, edgecolors="white", linewidths=1.5)
