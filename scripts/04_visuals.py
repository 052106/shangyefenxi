"""
04_visuals.py —— 全部静态图表（模板复现 14 张 + 业务模型图 10 张）
--------------------------------------------------------------------------------
本文件职责：
  A. 模板复现（fig01–fig14）：对照《Excel数据可视化——从图表到大屏》第二章 30 种模板，
     用 Matplotlib 复刻其图表类型、布局结构、配色方案、标签与图例样式；
  B. 业务模型图（fig15–fig24）：与 03_analysis.py 的 7 个模型一一对应，用于论文第 5 章。

命名规范：figXX_主题.png，全部 200dpi、白底、中文字体、含数据来源脚注。
运行方式：python 04_visuals.py（依赖 03_analysis.py 已产出结果表）
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from common import (C, OUT_FIG, PALETTE, PERCENT, THOUSAND, add_source_note,
                    save_fig, set_style)
from importlib import import_module
import importlib.util
from pathlib import Path

import viz_helpers as V

set_style(dark=False)
plt.rcParams["axes.grid"] = False


# ============================================================
# 内部工具
# ============================================================
def _load_analysis():
    """按路径导入 03_analysis.py（文件名以数字开头，不能直接 import）。"""
    p = Path(__file__).with_name("03_analysis.py")
    spec = importlib.util.spec_from_file_location("step03_analysis", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _title(fig, title: str, sub: str = "", y: float = 0.975):
    """统一标题排版：主标题 + 副标题（左上角，商务图表惯例）。"""
    fig.text(0.055, y, title, fontsize=17, fontweight="bold", color=C["ink"], va="top")
    if sub:
        fig.text(0.055, y - 0.052, sub, fontsize=10, color=C["sub"], va="top")


def _clean_axes(ax, grid_axis="y"):
    """留白清理：只保留需要的网格线，去掉多余边框。"""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(C["grid"])
    if grid_axis is None:
        ax.grid(False)
    elif grid_axis:
        ax.grid(axis=grid_axis, color=C["grid"], linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)


# ============================================================
# 业务口径的公共数据切片
# ============================================================
def _slices(orders: pd.DataFrame) -> dict:
    """预先算好各图需要的聚合切片，避免每个图重复 groupby。"""
    o = orders
    m26 = o[o["年份"] == 2026]
    monthly_26 = (m26.groupby("月份")["Sales"].sum().reindex(range(1, 13), fill_value=0))
    monthly_all = o.groupby("年月")["Sales"].sum()
    sub = o.groupby("子类")["Sales"].sum().sort_values(ascending=False)
    sub26 = m26.groupby("子类")["Sales"].sum().sort_values(ascending=False)
    sub25 = o[o["年份"] == 2025].groupby("子类")["Sales"].sum()
    region_yr = o.pivot_table(index="大区", columns="年份", values="Sales", aggfunc="sum")
    cat_yr = o.pivot_table(index="年份", columns="品类", values="Sales", aggfunc="sum")
    quarter = o.groupby(["年份", "季度"])["Sales"].sum()
    yoy26 = (o[o["年份"] == 2026].groupby("月份")["Sales"].sum()
             / o[o["年份"] == 2025].groupby("月份")["Sales"].sum().replace(0, np.nan) - 1)
    # 复购率：下单次数 ≥2 的客户占比（水球图用）
    cnt = o.groupby("Customer ID")["Order ID"].nunique()
    repurchase = float((cnt >= 2).mean())
    # 履约达标率：订单在下单后 4 天内发货的占比（行业通用的“快速履约”口径）
    od = o.groupby("Order ID")["履约天数"].max()
    on_time = float((od <= 4).mean())
    # 履约天数分位（甘特图用）
    lead = o.groupby("配送方式")["履约天数"].describe(percentiles=[0.1, 0.5, 0.9])
    gross_margin = float(o["Profit"].sum() / o["Sales"].sum())
    return dict(monthly_26=monthly_26, monthly_all=monthly_all, sub=sub, sub26=sub26,
                sub25=sub25, region_yr=region_yr, cat_yr=cat_yr, quarter=quarter,
                yoy26=yoy26, repurchase=repurchase, on_time=on_time, lead=lead,
                gross_margin=gross_margin, m26=m26)


# ============================================================
# 模板复现 1：渐变柱形图
# ============================================================
def fig01_gradient_bar(s: dict):
    monthly = s["monthly_26"]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.subplots_adjust(top=0.80, left=0.075, right=0.97, bottom=0.12)
    x = monthly.index.values
    for xi, h in zip(x, monthly.values):
        V.gradient_bar(ax, xi, h, 0.62, C["blue"], top_light=0.78)
    ax.set_xticks(x, [f"{m}月" for m in x])
    ax.set_ylim(0, monthly.max() * 1.20)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    peak = int(np.argmax(monthly.values))
    V.callout(ax, x[peak], monthly.values[peak],
              f"全年峰值 {monthly.values[peak]/1e4:,.2f} 万美元",
              color=C["blue"], bg="#F2F7FE", edge="#C9DCF5")
    _clean_axes(ax)
    _title(fig, "2026 年月度销售额走势（渐变柱形图）",
           "模板复现 01｜渐变填充自下而上由深到浅，突出“柱体高度”这一唯一信息")
    add_source_note(fig)
    save_fig(fig, "fig01_渐变柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 2：带均值柱形图
# ============================================================
def fig02_mean_bar(s: dict):
    sub = s["sub"]
    mean_v = sub.mean()
    fig, ax = plt.subplots(figsize=(12, 5.9))
    fig.subplots_adjust(top=0.80, left=0.07, right=0.97, bottom=0.20)
    x = np.arange(len(sub))
    for xi, (name, v) in zip(x, sub.items()):
        color = C["blue"] if v >= mean_v else "#A9BCD6"
        V.gradient_bar(ax, xi, v, 0.66, color, top_light=0.72)
    ax.axhline(mean_v, color=C["coral"], lw=1.6, ls=(0, (6, 3)), zorder=5)
    ax.text(len(sub) - 0.4, mean_v * 1.03, f"整体均值 {mean_v/1e4:,.1f} 万美元",
            ha="right", va="bottom", fontsize=10, color=C["coral"], fontweight="bold")
    ax.set_xticks(x, sub.index, rotation=38, ha="right")
    ax.set_ylim(0, sub.max() * 1.16)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    _clean_axes(ax)
    _title(fig, "17 个产品子类销售额与整体均值对比（带均值柱形图）",
           "模板复现 02｜均值参考线以上（深蓝）为“高于平均贡献”的核心子类")
    add_source_note(fig)
    save_fig(fig, "fig02_带均值柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 3：渐变圆角柱形图
# ============================================================
def fig03_rounded_bar(s: dict):
    r = s["region_yr"][2026].sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    fig.subplots_adjust(top=0.80, left=0.10, right=0.96, bottom=0.14)
    colors = [C["blue"], C["teal"], C["amber"], C["violet"]]
    for i, (name, v) in enumerate(r.items()):
        V.rounded_gradient_bar(ax, i, v, 0.42, colors[i % len(colors)])
        ax.text(i, v * 1.03, f"{v/1e4:,.0f} 万", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=C["ink"])
    ax.set_xticks(range(len(r)), r.index)
    ax.set_ylim(0, r.max() * 1.20)
    ax.set_ylabel("2026 年销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    _clean_axes(ax)
    _title(fig, "四大区 2026 年销售额（渐变圆角柱形图）",
           "模板复现 03｜圆角 + 纵向渐变替代纯色柱，视觉更柔和，适合大屏/汇报")
    add_source_note(fig)
    save_fig(fig, "fig03_渐变圆角柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 4：标注柱形图
# ============================================================
def fig04_callout_bar(s: dict):
    monthly = s["monthly_26"]
    yoy = s["yoy26"].reindex(monthly.index)
    fig, ax = plt.subplots(figsize=(12, 6.0))
    fig.subplots_adjust(top=0.78, left=0.075, right=0.97, bottom=0.13)
    x = monthly.index.values
    for xi, h in zip(x, monthly.values):
        V.gradient_bar(ax, xi, h, 0.60, C["teal"], top_light=0.80)
    ax.set_xticks(x, [f"{m}月" for m in x])
    ax.set_ylim(0, monthly.max() * 1.32)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    for xi, h, g in zip(x, monthly.values, yoy.values):
        if np.isnan(g):
            continue
        up = g >= 0
        V.callout(ax, xi, h, f"{'+' if up else ''}{g:.1%}",
                  color=C["green"] if up else C["coral"],
                  bg="#F1FAF5" if up else "#FDF2EF",
                  edge="#C6E9D8" if up else "#F6D5CC", dy=0.045, fontsize=8.6)
    _clean_axes(ax)
    _title(fig, "2026 年月度销售额与同比增速标注（标注柱形图）",
           "模板复现 04｜用引线标签把“同比”这一第二维信息挂在柱顶，避免再开副轴")
    add_source_note(fig)
    save_fig(fig, "fig04_标注柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 5：层叠柱形图
# ============================================================
def fig05_stacked_bar(s: dict):
    cat = s["cat_yr"]
    fig, ax = plt.subplots(figsize=(10, 5.7))
    fig.subplots_adjust(top=0.79, left=0.09, right=0.97, bottom=0.13)
    years = cat.index.tolist()
    colors = [C["blue"], C["amber"], C["teal"]]
    bottom = np.zeros(len(years))
    for color, col in zip(colors, cat.columns):
        vals = cat[col].values
        ax.bar(range(len(years)), vals, 0.52, bottom=bottom, color=color,
               edgecolor="white", linewidth=1.4, label=col, zorder=3)
        for i, (b, v) in enumerate(zip(bottom, vals)):
            if v / cat.sum(axis=1).values[i] > 0.18:
                ax.text(i, b + v / 2, f"{v/1e4:,.0f}", ha="center", va="center",
                        fontsize=9, color="white", fontweight="bold", zorder=4)
        bottom += vals
    for i, tot in enumerate(cat.sum(axis=1).values):
        ax.text(i, tot * 1.02, f"合计 {tot/1e4:,.0f} 万", ha="center", va="bottom",
                fontsize=10, color=C["ink"], fontweight="bold")
    ax.set_xticks(range(len(years)), [f"{y} 年" for y in years])
    ax.set_ylim(0, cat.sum(axis=1).max() * 1.18)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.legend(loc="upper left", ncol=3, bbox_to_anchor=(0, 1.02))
    _clean_axes(ax)
    _title(fig, "2023–2026 年各品类销售额构成（层叠柱形图）",
           "模板复现 05｜同一根柱内叠放三个品类，兼顾总量与结构")
    add_source_note(fig)
    save_fig(fig, "fig05_层叠柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 6：蝴蝶图
# ============================================================
def fig06_butterfly(s: dict):
    a, b = s["sub25"], s["sub26"]
    idx = b.sort_values(ascending=False).head(10).index[::-1]
    left = a.reindex(idx).fillna(0).values
    right = b.reindex(idx).fillna(0).values
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    fig.subplots_adjust(top=0.79, left=0.20, right=0.80, bottom=0.11)
    y = np.arange(len(idx))
    ax.barh(y, -left, 0.62, color=C["slate"], alpha=0.85, zorder=3)
    ax.barh(y, right, 0.62, color=C["blue"], alpha=0.92, zorder=3)
    for yi, l, r in zip(y, left, right):
        ax.text(-l - 3e3, yi, f"{l/1e4:,.0f}", ha="right", va="center",
                fontsize=8.6, color=C["sub"])
        ax.text(r + 3e3, yi, f"{r/1e4:,.0f}", ha="left", va="center",
                fontsize=8.6, color=C["ink"], fontweight="bold")
    ax.set_yticks(y, idx)
    ax.axvline(0, color=C["grid"], lw=1.2)
    ax.set_xlim(-max(left) * 1.35, max(right) * 1.35)
    ax.set_xlabel("← 2025 年销售额（万美元）        2026 年销售额（万美元） →")
    ax.xaxis.set_major_formatter(lambda v, p: f"{abs(v)/1e4:,.0f}")
    ax.set_xticks([])
    for s_ in ("top", "right", "bottom", "left"):
        ax.spines[s_].set_visible(False)
    _title(fig, "重点子类 2025 vs 2026 销售额对比（蝴蝶图）",
           "模板复现 06｜左右对称双轴条形，中心为类别轴，适合“攻守对比”场景")
    add_source_note(fig)
    save_fig(fig, "fig06_蝴蝶图.png")
    plt.close(fig)


# ============================================================
# 模板复现 7：对比柱形图
# ============================================================
def fig07_compare_bar(s: dict):
    r = s["region_yr"][[2025, 2026]].sort_values(2026, ascending=False)
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    fig.subplots_adjust(top=0.79, left=0.10, right=0.96, bottom=0.14)
    x = np.arange(len(r))
    w = 0.30
    ax.bar(x - w / 2 - 0.02, r[2025], w, color="#C3D2E6", label="2025 年", zorder=3)
    ax.bar(x + w / 2 + 0.02, r[2026], w, color=C["blue"], label="2026 年", zorder=3)
    for i in x:
        v25, v26 = r[2025].values[i], r[2026].values[i]
        g = v26 / v25 - 1
        ax.text(i, max(v25, v26) * 1.06, f"{g:+.1%}", ha="center", va="bottom",
                fontsize=10.5, fontweight="bold",
                color=C["green"] if g >= 0 else C["coral"])
        ax.text(i - w / 2 - 0.02, v25 * 1.01, f"{v25/1e4:,.0f}", ha="center",
                va="bottom", fontsize=8.5, color=C["sub"])
        ax.text(i + w / 2 + 0.02, v26 * 1.01, f"{v26/1e4:,.0f}", ha="center",
                va="bottom", fontsize=8.5, color=C["ink"])
    ax.set_xticks(x, r.index)
    ax.set_ylim(0, r.values.max() * 1.22)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.legend(loc="upper right", ncol=2)
    _clean_axes(ax)
    _title(fig, "四大区销售额同比对比（对比柱形图）",
           "模板复现 07｜并列双柱 + 柱顶增速，一眼看出“增长来自哪个大区”")
    add_source_note(fig)
    save_fig(fig, "fig07_对比柱形图.png")
    plt.close(fig)


# ============================================================
# 模板复现 8：甘特图（履约周期区间）
# ============================================================
def fig08_gantt(s: dict):
    lead = s["lead"].sort_values("50%")
    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    fig.subplots_adjust(top=0.76, left=0.13, right=0.95, bottom=0.16)
    colors = [C["blue"], C["teal"], C["amber"], C["violet"]]
    for i, (name, row) in enumerate(lead.iterrows()):
        start, end = row["10%"], row["90%"]
        ax.barh(i, end - start, left=start, height=0.42, color=colors[i % 4],
                alpha=0.30, zorder=2)
        ax.barh(i, row["50%"] - start, left=start, height=0.42, color=colors[i % 4],
                alpha=0.92, zorder=3)
        ax.text(end + 0.25, i, f"P10–P90：{start:.0f}–{end:.0f} 天｜中位 {row['50%']:.0f} 天",
                va="center", fontsize=9, color=C["sub"])
    ax.set_yticks(range(len(lead)), lead.index)
    ax.set_xlabel("下单至发货天数（天）")
    ax.set_xlim(0, lead["90%"].max() * 1.52)
    ax.invert_yaxis()
    _clean_axes(ax, grid_axis="x")
    _title(fig, "各配送方式履约周期区间（甘特图）",
           "模板复现 08｜浅色段为 P10–P90 区间，深色段为 P10–中位数，可直观看履约稳定性")
    add_source_note(fig)
    save_fig(fig, "fig08_甘特图.png")
    plt.close(fig)


# ============================================================
# 模板复现 9：平滑折线图
# ============================================================
def fig09_smooth_line(s: dict):
    m = s["monthly_all"]
    x = np.arange(len(m))
    xs, ys = V.smooth_curve(x, m.values)
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    fig.subplots_adjust(top=0.79, left=0.08, right=0.97, bottom=0.16)
    V.gradient_area(ax, xs, ys, C["blue"], base=0, alpha=0.40)
    ax.plot(xs, ys, color=C["blue"], lw=2.8, zorder=5, solid_capstyle="round")
    ax.scatter(x[::6], m.values[::6], s=32, color="white", edgecolor=C["blue"],
               linewidth=1.6, zorder=6)
    ax.set_xticks(x[::3], [m.index[i][2:] for i in range(0, len(m), 3)], fontsize=9)
    ax.set_ylim(0, m.max() * 1.18)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    _clean_axes(ax)
    imax = int(np.argmax(m.values))
    ax.annotate(f"峰值 {m.values[imax]/1e4:,.1f} 万", xy=(imax, m.values[imax]),
                xytext=(imax - 3.2, m.values[imax] * 1.06), fontsize=9.5,
                color=C["ink"], fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=C["sub"], lw=1.0,
                                shrinkA=2, shrinkB=6))
    _title(fig, "2023–2026 年月度销售额趋势（平滑折线图）",
           "模板复现 09｜PCHIP 单调插值平滑曲线 + 渐变面积，弱化锯齿、强化趋势")
    add_source_note(fig)
    save_fig(fig, "fig09_平滑折线图.png")
    plt.close(fig)


# ============================================================
# 模板复现 10：菱形走势图
# ============================================================
def fig10_diamond_trend(s: dict):
    q = s["quarter"]
    labels, vals = [], []
    for (y, qq), v in q.items():
        labels.append(f"{y}\nQ{qq}")
        vals.append(v)
    fig, ax = plt.subplots(figsize=(12, 5.4))
    fig.subplots_adjust(top=0.78, left=0.08, right=0.97, bottom=0.18)
    x = np.arange(len(vals))
    ax.plot(x, vals, color="#C3D2E6", lw=1.6, zorder=2)
    ax.scatter(x, vals, marker="D", s=95, color=C["violet"], edgecolor="white",
               linewidth=1.8, zorder=4)
    for xi, v in zip(x, vals):
        ax.text(xi, v * 1.035, f"{v/1e4:,.0f}", ha="center", va="bottom",
                fontsize=8.6, color=C["ink"])
    ax.set_xticks(x, labels, fontsize=8.8)
    ax.set_ylim(min(vals) * 0.90, max(vals) * 1.15)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    _clean_axes(ax)
    _title(fig, "季度销售额走势（菱形走势图）",
           "模板复现 10｜以菱形点替代圆点、弱化连线，突出“季度节点值”本身")
    add_source_note(fig)
    save_fig(fig, "fig10_菱形走势图.png")
    plt.close(fig)


# ============================================================
# 模板复现 11：对比折线图
# ============================================================
def fig11_compare_line(s: dict):
    o_years = s["monthly_all"]
    y25 = [o_years.get(f"2025-{m:02d}", np.nan) for m in range(1, 13)]
    y26 = [o_years.get(f"2026-{m:02d}", np.nan) for m in range(1, 13)]
    s25 = pd.Series(y25).rolling(2, min_periods=1).mean()
    s26 = pd.Series(y26).rolling(2, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(10.6, 5.6))
    fig.subplots_adjust(top=0.79, left=0.09, right=0.97, bottom=0.14)
    x = np.arange(1, 13)
    ax.plot(x, s25, color="#A9BCD6", lw=2.4, marker="o", ms=5,
            markerfacecolor="white", label="2025 年")
    ax.plot(x, s26, color=C["blue"], lw=2.8, marker="o", ms=5.5,
            markerfacecolor="white", label="2026 年")
    ax.fill_between(x, s25.values, s26.values, where=(s26.values >= s25.values),
                    color=C["blue"], alpha=0.10, interpolate=True)
    ax.fill_between(x, s25.values, s26.values, where=(s26.values < s25.values),
                    color=C["coral"], alpha=0.10, interpolate=True)
    ax.set_xticks(x, [f"{m}月" for m in x])
    ax.set_ylim(0, max(np.nanmax(s25), np.nanmax(s26)) * 1.10)
    ax.set_ylabel("2 期移动平均销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.legend(loc="upper left", ncol=2)
    _clean_axes(ax)
    _title(fig, "2025 与 2026 年月度销售额对比（对比折线图）",
           "模板复现 11｜双线 + 差异阴影：蓝色区域表示 2026 领先月份，红色表示落后月份")
    add_source_note(fig)
    save_fig(fig, "fig11_对比折线图.png")
    plt.close(fig)


# ============================================================
# 模板复现 12：单值圆环图
# ============================================================
def fig12_donut(s: dict):
    gm = s["gross_margin"]
    fig = plt.figure(figsize=(9.6, 5.2))
    fig.subplots_adjust(top=0.78, bottom=0.08, left=0.02, right=0.99)
    ax = fig.add_axes([0.06, 0.06, 0.40, 0.72])
    V.donut(ax, gm, C["blue"], label=f"{gm:.2%}", sub="整体毛利率")

    # 右侧三个配套指标
    orders = s["m26"]
    kpis = [("2026 年销售额", f"{orders['Sales'].sum()/1e4:,.0f} 万美元", C["teal"]),
            ("2026 年利润", f"{orders['Profit'].sum()/1e4:,.1f} 万美元", C["amber"]),
            ("履约达标率", f"{s['on_time']:.1%}", C["violet"])]
    for i, (k, v, c) in enumerate(kpis):
        y = 0.62 - i * 0.20
        fig.patches.append(Rectangle((0.50, y - 0.02), 0.46, 0.155, transform=fig.transFigure,
                                     facecolor=c, alpha=0.07, edgecolor="none", zorder=0))
        fig.patches.append(Rectangle((0.50, y - 0.02), 0.008, 0.155, transform=fig.transFigure,
                                     facecolor=c, edgecolor="none", zorder=1))
        fig.text(0.525, y + 0.095, k, fontsize=10, color=C["sub"], va="top")
        fig.text(0.525, y + 0.045, v, fontsize=17, fontweight="bold", color=C["ink"], va="top")
    _title(fig, "整体毛利率单值圆环（单值圆环图）",
           "模板复现 12｜环形进度替代饼图，把“单一核心指标”放大到视觉中心")
    add_source_note(fig)
    save_fig(fig, "fig12_单值圆环图.png")
    plt.close(fig)


# ============================================================
# 模板复现 13：水球图
# ============================================================
def fig13_liquid(s: dict):
    val = s["on_time"]
    fig = plt.figure(figsize=(7.6, 5.8))
    fig.patch.set_facecolor(C["bg"])
    ax = fig.add_axes([0.24, 0.14, 0.52, 0.62])
    V.liquid_fill(ax, val, C["blue"], text_color=C["ink"], bg="#F4F8FD")
    _title(fig, "订单履约达标率（水球图）",
           "模板复现 13｜液面高度映射指标达成度，适合大屏“单指标蓄水”展示")
    fig.text(0.5, 0.075, f"「下单后 4 天内发货」的订单占比 {val:.1%}　|　未达标 {1 - val:.1%}",
             ha="center", fontsize=10.5, color=C["sub"])
    add_source_note(fig)
    save_fig(fig, "fig13_水球图.png")
    plt.close(fig)


# ============================================================
# 模板复现 14：南丁格尔玫瑰图
# ============================================================
def fig14_rose(s: dict):
    sub = s["sub"].head(10)
    other = s["sub"].sum() - sub.sum()
    vals = list(sub.values) + [other]
    labels = list(sub.index) + ["其他小类"]
    colors = (PALETTE * 3)[:len(vals)]
    fig = plt.figure(figsize=(8.6, 7.4))
    ax = fig.add_subplot(111, projection="polar")
    V.nightingale(ax, vals, labels, colors)
    _title(fig, "产品子类销售额结构（南丁格尔玫瑰图）",
           "模板复现 14｜极坐标扇形半径映射销售额，按大小排序后易读性优于饼图")
    fig.text(0.5, 0.035, "注：取销售额前 10 的子类，其余合并为“其他小类”",
             ha="center", fontsize=9, color=C["sub"])
    save_fig(fig, "fig14_玫瑰图.png")
    plt.close(fig)


# ============================================================
# 业务模型图 15：同比 / 环比趋势（M1）
# ============================================================
def fig15_yoy_mom(res: dict):
    t = res["trend"].copy()
    t = t[t["年月"] >= "2025-01"].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(12, 6.0))
    fig.subplots_adjust(top=0.78, left=0.08, right=0.90, bottom=0.16)
    x = np.arange(len(t))
    for xi, h in zip(x, t["销售额"]):
        V.gradient_bar(ax, xi, h, 0.58, C["blue"], top_light=0.74)
    ax.plot(x, t["销售额_MA3"], color=C["amber"], lw=2.4, label="3 期移动平均")
    ax.set_xticks(x[::2], [v[2:] for v in t["年月"][::2]], rotation=0, fontsize=9)
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.set_ylim(0, t["销售额"].max() * 1.28)
    _clean_axes(ax)

    ax2 = ax.twinx()
    ax2.plot(x, t["同比"] * 100, color=C["coral"], lw=1.9, marker="o", ms=3.6,
             label="同比增速")
    ax2.axhline(0, color=C["grid"], lw=1.0)
    ax2.set_ylabel("同比增速（%）", color=C["coral"])
    ax2.tick_params(axis="y", colors=C["coral"])
    for s_ in ("top", "left"):
        ax2.spines[s_].set_visible(False)
    ax2.grid(False)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2)
    _title(fig, "近两年月度销售额、移动平均与同比增速（M1 同比/环比）",
           "柱=当月销售额，橙线=3 期移动平均（去噪后的趋势），红线=同比增速（右轴）")
    add_source_note(fig)
    save_fig(fig, "fig15_月度趋势与同比.png")
    plt.close(fig)


# ============================================================
# 业务模型图 16：帕累托 / ABC（M2）
# ============================================================
def fig16_pareto(res: dict):
    g = res["pareto_sub"].copy()
    fig, ax = plt.subplots(figsize=(11.5, 6.0))
    fig.subplots_adjust(top=0.78, left=0.08, right=0.90, bottom=0.20)
    x = np.arange(len(g))
    cmap = {"A 类": C["blue"], "B 类": C["teal"], "C 类": "#B9C6D8"}
    for xi, v, lv in zip(x, g["销售额"], g["ABC等级"]):
        ax.bar(xi, v, 0.62, color=cmap[lv], zorder=3)
    ax.set_xticks(x, g["子类"], rotation=38, ha="right")
    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.set_ylim(0, g["销售额"].max() * 1.15)
    _clean_axes(ax)

    ax2 = ax.twinx()
    ax2.plot(x, g["累计占比"] * 100, color=C["coral"], lw=2.2, marker="o", ms=5,
             markerfacecolor="white", zorder=6)
    ax2.set_ylim(0, 108)
    ax2.set_ylabel("累计销售额占比（%）", color=C["coral"])
    ax2.tick_params(axis="y", colors=C["coral"])
    for s_ in ("top", "left"):
        ax2.spines[s_].set_visible(False)
    ax2.grid(False)
    for line, label in [(70, "A 类线 70%"), (90, "B 类线 90%")]:
        ax2.axhline(line, color=C["sub"], lw=1.0, ls=(0, (5, 4)), alpha=0.8)
        ax2.text(len(g) - 0.4, line + 1.6, label, ha="right", fontsize=8.6, color=C["sub"])

    nA = int((g["ABC等级"] == "A 类").sum())
    ax.text(0.015, 0.94, f"A 类仅 {nA} 个子类（占 {nA/len(g):.0%}），贡献 "
                         f"{g.loc[g['ABC等级']=='A 类','销售额占比'].sum():.1%} 的销售额",
            transform=ax.transAxes, fontsize=10.5, color=C["ink"], fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#F3F7FD",
                      edgecolor="#CFDEF0"))
    _title(fig, "产品子类帕累托分析与 ABC 分类（M2 帕累托/ABC）",
           "柱=销售额（按 A/B/C 着色），红线=累计占比；70%/90% 为库存 ABC 管理的行业标准切分线")
    add_source_note(fig)
    save_fig(fig, "fig16_帕累托ABC.png")
    plt.close(fig)


# ============================================================
# 业务模型图 17：RFM 八分类气泡散点（M3）
# ============================================================
def fig17_rfm(res: dict):
    rfm = res["rfm"]
    order = ["重要价值客户", "重要唤回客户", "重要深耕客户", "重要挽留客户",
             "一般保持客户", "一般发展客户", "潜力新客", "流失客户"]
    colors = [C["blue"], C["coral"], C["teal"], C["amber"],
              C["violet"], C["slate"], C["green"], C["rose"]]
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    fig.subplots_adjust(top=0.77, left=0.08, right=0.78, bottom=0.12)
    rng = np.random.default_rng(42)          # 固定随机种子，保证图可复现
    for seg, c in zip(order, colors):
        d = rfm[rfm["RFM客群"] == seg]
        jitter = rng.uniform(-0.045, 0.045, len(d))   # 次数是整数，做轻微横向抖动避免重叠
        ax.scatter(d["F值"] * (1 + jitter), d["R值"],
                   s=np.clip(np.sqrt(d["M值"]) * 3.6, 12, 420), color=c, alpha=0.55,
                   edgecolors="white", linewidths=0.6, label=f"{seg}（{len(d)} 人）", zorder=3)
    r_thr = rfm["R值"].median()
    f_thr = rfm["F值"].median()
    ax.axhline(r_thr, color=C["sub"], lw=1.0, ls=(0, (5, 4)), alpha=0.75)
    ax.axvline(f_thr, color=C["sub"], lw=1.0, ls=(0, (5, 4)), alpha=0.75)
    ax.invert_yaxis()      # R 越小越活跃，放到上方
    ax.text(f_thr * 1.06, rfm["R值"].min() + 40,
            f"中位线 F={f_thr:.0f} 次", fontsize=8.6, color=C["sub"])
    ax.text(rfm["F值"].min() * 0.92, r_thr - 30,
            f"中位线 R={r_thr:.0f} 天", fontsize=8.6, color=C["sub"], va="bottom")
    ax.set_xlabel("购买次数 F（次，对数轴，已做轻微抖动）")
    ax.set_ylabel("最近购买间隔 R（天，越靠上越活跃）")
    ax.set_xscale("log")
    ax.set_xlim(0.8, rfm["F值"].max() * 1.7)
    _clean_axes(ax, grid_axis="y")
    leg = ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), labelspacing=0.95,
                    title="RFM 八分类", title_fontsize=10, scatterpoints=1,
                    markerscale=0.55)
    for h in leg.legend_handles:
        h.set_alpha(0.85)
    _title(fig, "RFM 客户八分类气泡图（M3 RFM 模型）",
           "气泡=客户，X=购买次数（对数轴），Y=最近购买间隔，气泡大小=累计消费额；虚线为中位数切分线")
    add_source_note(fig)
    save_fig(fig, "fig17_RFM八分类.png")
    plt.close(fig)


# ============================================================
# 业务模型图 18：K-Means 客群画像（M4）
# ============================================================
def fig18_kmeans(res: dict):
    k = res["rfm_k"]
    prof = res["km_prof"]
    labels = prof["业务标签"].tolist()
    colors = dict(zip(labels, [C["blue"], C["coral"], C["teal"], C["amber"],
                               C["violet"], C["green"]]))
    fig = plt.figure(figsize=(12.2, 6.2))
    gs = GridSpec(1, 2, width_ratios=[1.35, 1], wspace=0.32)
    fig.subplots_adjust(top=0.76, left=0.07, right=0.97, bottom=0.13)

    ax = fig.add_subplot(gs[0, 0])
    for lab, c in colors.items():
        d = k[k["KMeans客群"] == lab]
        ax.scatter(d["M值"], d["R值"], s=24, color=c, alpha=0.55,
                   edgecolors="white", linewidths=0.4, label=f"{lab}（{len(d)} 人）")
        # 簇心用大号 X 标出，便于看三个客群在“R/M”平面上的分离程度
        ax.scatter([d["M值"].median()], [d["R值"].median()], s=170, marker="X",
                   color=c, edgecolors="white", linewidths=1.6, zorder=6)
    ax.set_xscale("log")
    ax.invert_yaxis()
    ax.set_xlabel("累计消费额 M（美元，对数轴）")
    ax.set_ylabel("最近购买间隔 R（天，越靠上越活跃）")
    _clean_axes(ax, grid_axis="both")
    ax.legend(loc="lower left", fontsize=8.4, labelspacing=0.5, markerscale=1.1)
    ax.set_title("客群分布：金额 × 活跃度（X 为簇中位数）", fontsize=12, color=C["ink"], pad=10)

    ax2 = fig.add_subplot(gs[0, 1])
    y = np.arange(len(prof))
    ax2.barh(y + 0.19, prof["客户占比"] * 100, 0.36, color="#B9C6D8", label="客户数占比")
    ax2.barh(y - 0.19, prof["销售额占比"] * 100, 0.36, color=C["blue"], label="销售额占比")
    for yi, a, b in zip(y, prof["客户占比"] * 100, prof["销售额占比"] * 100):
        ax2.text(a + 0.8, yi + 0.19, f"{a:.1f}%", va="center", fontsize=8.4, color=C["sub"])
        ax2.text(b + 0.8, yi - 0.19, f"{b:.1f}%", va="center", fontsize=8.4,
                 color=C["ink"], fontweight="bold")
    ax2.set_yticks(y, prof["业务标签"])
    ax2.invert_yaxis()
    ax2.set_xlim(0, 100)
    ax2.set_xlabel("占比（%）")
    ax2.legend(loc="lower right", fontsize=8.8)
    _clean_axes(ax2, grid_axis="x")
    ax2.set_title("客群价值贡献对比", fontsize=12, color=C["ink"], pad=10)

    _title(fig, "K-Means 用户分群结果（M4 用户分群）",
           f"特征=log(R,F,M) 标准化后聚类，K 由轮廓系数在 3~6 中择优；"
           f"共 {len(k)} 位客户、{len(prof)} 个客群")
    add_source_note(fig)
    save_fig(fig, "fig18_KMeans客群.png")
    plt.close(fig)


# ============================================================
# 业务模型图 19：同期群留存热力图（M5）
# ============================================================
def fig19_cohort(res: dict):
    import seaborn as sns
    c = res["cohort"].set_index("首购月")
    mat = c.drop(columns=["群规模"]).astype(float)
    mat.columns = [f"第{i}期" for i in range(mat.shape[1])]
    fig, ax = plt.subplots(figsize=(12.6, 6.0))
    fig.subplots_adjust(top=0.76, left=0.10, right=0.99, bottom=0.14)
    sns.heatmap(mat * 100, ax=ax, cmap="YlGnBu", annot=True, fmt=".0f",
                linewidths=1.4, linecolor="white", cbar_kws={"label": "留存率（%）", "shrink": 0.8},
                annot_kws={"fontsize": 8.2})
    ax.set_ylabel("同期群（首次购买月份）")
    ax.set_xlabel("距首购的月份数")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=9)
    _title(fig, "客户同期群留存热力图（M5 同期群分析）",
           "行=首次购买月份形成的同期群，列=其后第 n 个月仍有购买的客户占比（颜色越深留存越高）")
    add_source_note(fig)
    save_fig(fig, "fig19_同期群留存.png")
    plt.close(fig)


# ============================================================
# 业务模型图 20：波士顿矩阵（M6）
# ============================================================
def fig20_bcg(res: dict):
    g = res["bcg"]
    share_line = g.attrs.get("share_line", 1 / len(g))
    growth_line = g.attrs.get("growth_line", g["同比增速"].median())
    fig, ax = plt.subplots(figsize=(11.2, 7.0))
    fig.subplots_adjust(top=0.78, left=0.09, right=0.99, bottom=0.13)

    xmax = 0.165
    ymin, ymax = -0.35, 0.85          # 增速上限截断到 85%，避免个别爆发式子类压扁主体
    g = g.copy()
    g["增速_绘图"] = g["同比增速"].clip(upper=ymax - 0.03)

    # 四象限底色
    for (x0, y0, x1, y1, col) in [
            (share_line, growth_line, xmax, ymax, C["amber"]),
            (0, growth_line, share_line, ymax, C["teal"]),
            (share_line, ymin, xmax, growth_line, C["blue"]),
            (0, ymin, share_line, growth_line, C["slate"])]:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=col,
                               alpha=0.055, zorder=0))
    for tx, ty, name, col, ha, va in [
            (0.98, 0.96, "明星业务｜高份额·高增长", C["amber"], "right", "top"),
            (0.02, 0.96, "问题业务｜低份额·高增长", C["teal"], "left", "top"),
            (0.98, 0.04, "现金牛业务｜高份额·低增长", C["blue"], "right", "bottom"),
            (0.02, 0.13, "瘦狗业务｜低份额·低增长", C["slate"], "left", "bottom")]:
        ax.text(tx, ty, name, transform=ax.transAxes, ha=ha, va=va, fontsize=10,
                color=col, alpha=0.9, fontweight="bold")

    sc = ax.scatter(g["销售额份额"], g["增速_绘图"],
                    s=g["2026销售额"] / 110, c=g["毛利率"], cmap="RdYlGn",
                    vmin=-0.2, vmax=0.45, edgecolors=C["ink"], linewidths=0.8, zorder=5)
    ax.axvline(share_line, color=C["sub"], lw=1.1, ls=(0, (5, 4)), alpha=0.8)
    ax.axhline(growth_line, color=C["sub"], lw=1.1, ls=(0, (5, 4)), alpha=0.8)
    ax.axhline(0, color=C["grid"], lw=0.9)

    # 标注：交替上下错位 + 半透明白底，尽量压住重叠
    for i, (_, row) in enumerate(g.iterrows()):
        yv = row["增速_绘图"]
        up = i % 2 == 0
        dy = 0.035 if up else -0.035
        label = row["子类"] + ("（实际 +515%）" if row["同比增速"] > ymax else "")
        ax.annotate(label, (row["销售额份额"], min(max(yv + dy, ymin), ymax)),
                    ha="center", va="bottom" if up else "top", fontsize=8.4,
                    color=C["ink"], zorder=7,
                    bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                              edgecolor="none", alpha=0.62))

    ax.set_xlim(0, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("销售额份额（2026 年，分界线=平均份额 %.2f%%）" % (share_line * 100))
    ax.set_ylabel("同比增速（2026 vs 2025，分界线=整体增速 %.2f%%）" % (growth_line * 100))
    ax.xaxis.set_major_formatter(PERCENT)
    ax.yaxis.set_major_formatter(PERCENT)
    _clean_axes(ax, grid_axis=None)
    ax.text(xmax * 0.99, ymax - 0.01, "注：增速 >85% 的子类做截断显示，气泡贴顶",
            ha="right", va="top", fontsize=8, color=C["sub"])
    cb = fig.colorbar(sc, ax=ax, pad=0.015, shrink=0.72)
    cb.set_label("毛利率", fontsize=9.5)
    cb.ax.yaxis.set_major_formatter(PERCENT)
    _title(fig, "产品子类波士顿矩阵：份额 × 增速 × 毛利率（M6）",
           "气泡位置=结构地位与增长性，气泡面积=2026 年销售额，颜色=毛利率（红=亏损，绿=高毛利）")
    add_source_note(fig)
    save_fig(fig, "fig20_波士顿矩阵.png")
    plt.close(fig)


# ============================================================
# 业务模型图 21：预测 + 95% 置信区间（M7）
# ============================================================
def fig21_forecast(res: dict):
    r = res["sarima"]
    hist, fc, bt = r["history"], r["forecast"], r["backtest"]
    fig, ax = plt.subplots(figsize=(12.4, 6.0))
    fig.subplots_adjust(top=0.77, left=0.08, right=0.97, bottom=0.14)

    ax.plot(hist.index, hist.values, color=C["blue"], lw=2.0, label="历史实际销售额", zorder=4)
    fdates = pd.to_datetime(fc["年月"] + "-01")
    ax.plot(fdates, fc["预测销售额"], color=C["coral"], lw=2.4, marker="o", ms=5,
            label=f"预测值（{r['chosen']}）", zorder=5)
    ax.fill_between(fdates, fc["下限95"], fc["上限95"], color=C["coral"], alpha=0.16,
                    label="95% 置信区间", zorder=2)
    # 衔接线
    ax.plot([hist.index[-1], fdates[0]], [hist.values[-1], fc["预测销售额"].iloc[0]],
            color=C["coral"], lw=1.4, ls=(0, (3, 3)), alpha=0.8)

    # 回测区
    bdates = pd.to_datetime(bt["年月"] + "-01")
    ax.plot(bdates, bt["预测销售额"], color=C["amber"], lw=2.0, marker="s", ms=4.5,
            label="回测期预测值", zorder=5)
    ax.axvspan(bdates.min(), bdates.max(), color=C["amber"], alpha=0.06, zorder=0)

    ax.axvline(fdates[0], color=C["sub"], lw=1.1, ls=(0, (4, 4)), alpha=0.8)
    ax.text(fdates[0], ax.get_ylim()[1] * 0.97, " 预测起点", fontsize=9, color=C["sub"],
            va="top")

    ax.set_ylabel("销售额（万美元）")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v/1e4:,.0f}")
    ax.legend(loc="upper left", fontsize=9)
    _clean_axes(ax)
    ax.text(0.985, 0.04,
            f"回测误差：MAPE {r['mape']:.1%}　RMSE {r['rmse']:,.0f} 美元",
            transform=ax.transAxes, ha="right", fontsize=9.6, color=C["ink"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF8EC", edgecolor="#F0DCB4"))
    _title(fig, "月度销售额预测与 95% 置信区间（M7 时间序列预测）",
           f"以样本外 6 个月回测误差择优：{r['chosen']} 胜出（SARIMA 见 t14b 比选表）")
    add_source_note(fig)
    save_fig(fig, "fig21_预测置信区间.png")
    plt.close(fig)


# ============================================================
# 业务模型图 22：关联规则（M8）
# ============================================================
def fig22_rules(res: dict):
    r = res["rules"]
    if r is None or r.empty:
        return
    top = r.head(12).iloc[::-1]
    labels = [f"{a}  →  {b}" for a, b in zip(top["前项"], top["后项"])]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.subplots_adjust(top=0.78, left=0.30, right=0.93, bottom=0.13)
    y = np.arange(len(top))
    norm = (top["提升度"] - top["提升度"].min()) / (top["提升度"].max() - top["提升度"].min() + 1e-9)
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    cmap = plt.get_cmap("YlOrRd")
    bars = ax.barh(y, top["提升度"], 0.62, color=[cmap(0.35 + 0.5 * n) for n in norm], zorder=3)
    for yi, lift, conf, sup in zip(y, top["提升度"], top["置信度"], top["支持度"]):
        ax.text(lift + 0.02, yi, f"提升度 {lift:.2f}｜置信度 {conf:.0%}｜支持度 {sup:.1%}",
                va="center", fontsize=8.6, color=C["ink"])
    ax.axvline(1, color=C["coral"], lw=1.2, ls=(0, (5, 4)))
    ax.text(1.01, len(top) - 0.6, "提升度 = 1（无关联）", fontsize=8.6, color=C["coral"])
    ax.set_yticks(y, labels, fontsize=9.2)
    ax.set_xlabel("提升度（Lift）")
    ax.set_xlim(1, top["提升度"].max() * 1.55)
    _clean_axes(ax, grid_axis="x")
    _title(fig, "购物篮关联规则 Top 12（M8 Apriori）",
           f"全量规则 {len(r)} 条（lift>1）；提升度越高，说明两品类被同单购买的倾向越强")
    add_source_note(fig)
    save_fig(fig, "fig22_关联规则.png")
    plt.close(fig)


# ============================================================
# 业务模型图 23：履约漏斗（M9）
# ============================================================
def fig23_funnel(res: dict):
    f = res["funnel"]
    fig, ax = plt.subplots(figsize=(9.8, 6.0))
    fig.subplots_adjust(top=0.79, left=0.10, right=0.97, bottom=0.10)
    n = len(f)
    colors = [C["blue"], C["teal"], C["amber"], C["violet"]]
    maxw = 1.0
    for i, row in f.iterrows():
        w_top = maxw * (row["订单数"] / f["订单数"].iloc[0]) ** 0.55
        w_bot = maxw * (f["订单数"].iloc[i + 1] / f["订单数"].iloc[0]) ** 0.55 \
            if i + 1 < n else w_top * 0.86
        y0 = -i * 1.0
        poly = plt.Polygon([(-w_top / 2, y0), (w_top / 2, y0),
                            (w_bot / 2, y0 - 0.86), (-w_bot / 2, y0 - 0.86)],
                           closed=True, facecolor=colors[i], alpha=0.88, edgecolor="white",
                           linewidth=2.0, zorder=3)
        ax.add_patch(poly)
        ax.text(0, y0 - 0.43, f"{row['环节']}\n{row['订单数']:,.0f} 单（{row['整体转化率']:.1%}）",
                ha="center", va="center", fontsize=10.5, color="white", fontweight="bold",
                zorder=4, linespacing=1.6)
        if i + 1 < n:
            ax.annotate(f"↓ {f['环节转化率'].iloc[i+1]:.1%}",
                        xy=(maxw * 0.58, y0 - 0.43), fontsize=10, color=C["coral"],
                        fontweight="bold", va="center")
    ax.set_xlim(-maxw * 0.75, maxw * 0.95)
    ax.set_ylim(-n + 0.1, 0.55)
    ax.axis("off")
    _title(fig, "订单履约转化漏斗（M9 漏斗分析）",
           "从下单到“按时履约→未退货→盈利”的逐级流失；百分比为相对上一环节的转化率")
    add_source_note(fig)
    save_fig(fig, "fig23_履约漏斗.png")
    plt.close(fig)


# ============================================================
# 业务模型图 24：折扣—毛利弹性（支撑定价建议）
# ============================================================
def fig24_discount(res: dict):
    d = res["discount"].dropna(subset=["折扣档"])
    fig, ax = plt.subplots(figsize=(10.6, 5.8))
    fig.subplots_adjust(top=0.78, left=0.09, right=0.90, bottom=0.20)
    x = np.arange(len(d))
    colors = [C["green"] if v >= 0.08 else (C["amber"] if v >= 0 else C["coral"])
              for v in d["毛利率"]]
    for xi, v, c in zip(x, d["毛利率"], colors):
        ax.bar(xi, v * 100, 0.58, color=c, zorder=3)
        ax.text(xi, v * 100 + (0.8 if v >= 0 else -1.8), f"{v:.1%}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9, color=C["ink"])
    ax.axhline(0, color=C["ink"], lw=1.0)
    ax.axhline(12.56, color=C["blue"], lw=1.2, ls=(0, (5, 4)))
    ax.text(len(d) - 0.5, 13.6, "整体毛利率 12.6%", ha="right", fontsize=9, color=C["blue"])
    ax.set_xticks(x, d["折扣档"].astype(str))
    ax.set_ylabel("毛利率（%）")
    ax.set_xlabel("折扣档位")
    ax.set_ylim(-25, max(d["毛利率"]) * 100 * 1.35)
    _clean_axes(ax)

    ax2 = ax.twinx()
    ax2.plot(x, d["亏损占比"] * 100, color=C["violet"], lw=2.2, marker="o", ms=6,
             markerfacecolor="white")
    ax2.set_ylabel("亏损明细占比（%）", color=C["violet"])
    ax2.tick_params(axis="y", colors=C["violet"])
    ax2.set_ylim(0, 100)
    for s_ in ("top", "left"):
        ax2.spines[s_].set_visible(False)
    ax2.grid(False)
    _title(fig, "折扣力度与毛利率、亏损占比的关系（定价依据）",
           "柱=各折扣档毛利率（绿=健康、橙=临界、红=亏损），紫线=该档亏损明细占比（右轴）")
    add_source_note(fig)
    save_fig(fig, "fig24_折扣毛利弹性.png")
    plt.close(fig)


# ============================================================
# 模板复现调度
# ============================================================
TEMPLATE_FUNCS = [fig01_gradient_bar, fig02_mean_bar, fig03_rounded_bar,
                  fig04_callout_bar, fig05_stacked_bar, fig06_butterfly,
                  fig07_compare_bar, fig08_gantt, fig09_smooth_line,
                  fig10_diamond_trend, fig11_compare_line, fig12_donut,
                  fig13_liquid, fig14_rose]

BUSINESS_FUNCS = [fig15_yoy_mom, fig16_pareto, fig17_rfm, fig18_kmeans,
                  fig19_cohort, fig20_bcg, fig21_forecast, fig22_rules,
                  fig23_funnel, fig24_discount]


def run_templates(orders: pd.DataFrame) -> None:
    s = _slices(orders)
    print(f"[A] 模板复现：{len(TEMPLATE_FUNCS)} 张")
    for fn in TEMPLATE_FUNCS:
        fn(s)


def run_business(res: dict) -> None:
    print(f"[B] 业务模型图：{len(BUSINESS_FUNCS)} 张")
    for fn in BUSINESS_FUNCS:
        fn(res)


def run_all(res: dict | None = None) -> dict:
    """一键出全部图（模板复现 + 业务模型图）。"""
    if res is None:
        res = _load_analysis().run_all()
    run_templates(res["orders"])
    run_business(res)
    print(f"\n全部 {len(TEMPLATE_FUNCS) + len(BUSINESS_FUNCS)} 张图已输出到：{OUT_FIG}")
    return res


if __name__ == "__main__":
    run_all()
