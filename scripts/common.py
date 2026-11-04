"""
common.py —— 全局配置：路径、配色、中文字体、绘图风格、中文标签映射、保存工具
--------------------------------------------------------------------------------
本文件是整个项目的“公共底座”，被 01~05 各脚本统一 import。
作用：
  1) 统一项目目录（data / outputs / dashboard），避免各脚本硬编码相对路径；
  2) 统一中文字体（Microsoft YaHei），保证所有图表中文正常显示、负号不乱码；
  3) 提供两套配色：亮色（论文插图，鲜明但不刺眼）与暗色（交互大屏）；
  4) 提供英文→中文的维度标签映射，满足“图表全部用中文”的要求；
  5) 提供 save_fig()：统一 150dpi 以上、白底、紧凑边距、figXX_名称.png 命名规范。
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ============================ 1. 项目路径 ============================
ROOT = Path(__file__).resolve().parents[1]          # 项目根目录：.../数据分析大作业
DATA_RAW = ROOT / "data" / "raw"                     # 原始数据（只读，不修改）
DATA_CLEAN = ROOT / "data" / "clean"                 # 清洗后数据
OUT_FIG = ROOT / "outputs" / "figures"               # 图表输出
OUT_TAB = ROOT / "outputs" / "tables"                # 结果表输出
DASH_DIR = ROOT / "dashboard"                        # 大屏 HTML 输出
DOCS_DIR = ROOT / "docs"                             # 合规声明等文档

for _d in (DATA_CLEAN, OUT_FIG, OUT_TAB, DASH_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

RAW_XLS = DATA_RAW / "sample_-_superstore.xls"
DB_PATH = DATA_CLEAN / "superstore.sqlite"

# ============================ 2. 中文字体 ============================
def _setup_chinese_font() -> str:
    """挑选系统中可用的中文字体，优先微软雅黑，其次黑体/思源，最后退化为默认字体。"""
    candidates = ["Microsoft YaHei", "SimHei", "Source Han Sans SC",
                  "Noto Sans CJK SC", "WenQuanYi Micro Hei", "Arial Unicode MS"]
    from matplotlib.font_manager import fontManager
    installed = {f.name for f in fontManager.ttflist}
    chosen = next((c for c in candidates if c in installed), None)
    if chosen is None and platform.system() == "Windows":
        chosen = "Microsoft YaHei"
    plt.rcParams["font.sans-serif"] = ([chosen] if chosen else []) + ["DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False      # 负号正常显示（不出现方框）
    return chosen or "DejaVu Sans"


CN_FONT = _setup_chinese_font()

# ============================ 3. 配色体系 ============================
# 亮色系：饱和度中等偏高、明度适中，打印/投影都清爽，避免荧光色造成视觉疲劳
C = {
    "blue":    "#3A7BD5",
    "teal":    "#16A3A3",
    "coral":   "#E8735A",
    "amber":   "#E9A33A",
    "violet":  "#7A6FD0",
    "green":   "#4CA97B",
    "rose":    "#D9637E",
    "slate":   "#6B7A90",
    "ink":     "#1F2A37",   # 主文字
    "sub":     "#5A6778",   # 次文字
    "grid":    "#DCE3EC",   # 网格线
    "bg":      "#FFFFFF",
    "panel":   "#F5F8FC",
}

# 主序列：用于多系列图表的固定顺序，保证全篇配色统一
PALETTE = [C["blue"], C["teal"], C["amber"], C["coral"],
           C["violet"], C["green"], C["rose"], C["slate"]]

# 暗色大屏配色：深空蓝黑底 + 高亮青/琥珀/珊瑚/紫，明亮但不刺眼
D = {
    "bg":       "#0A1020",
    "panel":    "#111A2E",
    "panel2":   "#16223A",
    "line":     "#22304C",
    "text":     "#E6EDF7",
    "text_sub": "#93A4BF",
    "cyan":     "#35C4F0",
    "amber":    "#FFB13D",
    "coral":    "#FF6B6B",
    "violet":   "#8B7CF6",
    "green":    "#35D0A5",
    "pink":     "#F06CA8",
}
D_PALETTE = [D["cyan"], D["amber"], D["coral"], D["violet"], D["green"], D["pink"]]

# 发散色（同期群热力图 / 相关系数）
CMAP_SEQ = "YlGnBu"
CMAP_DIV = "RdYlGn"


def set_style(dark: bool = False, grid: bool = True) -> None:
    """切换全局绘图风格。dark=True 用于大屏配图，False 用于论文插图。"""
    base = {
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "figure.facecolor": D["bg"] if dark else C["bg"],
        "axes.facecolor": D["bg"] if dark else C["bg"],
        "savefig.facecolor": D["bg"] if dark else C["bg"],
        "axes.edgecolor": D["line"] if dark else C["grid"],
        "axes.labelcolor": D["text"] if dark else C["ink"],
        "text.color": D["text"] if dark else C["ink"],
        "xtick.color": D["text_sub"] if dark else C["sub"],
        "ytick.color": D["text_sub"] if dark else C["sub"],
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9.5,
        "font.size": 10,
        "axes.grid": grid,
        "grid.color": D["line"] if dark else C["grid"],
        "grid.alpha": 0.55 if dark else 0.75,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "figure.autolayout": False,
    }
    plt.rcParams.update(base)


set_style(dark=False)

# ============================ 4. 中文标签映射 ============================
# 业务图与大屏全部中文展示：原始英文维度在此翻译，图表中不再出现英文
REGION_CN = {"East": "东部", "West": "西部", "Central": "中部", "South": "南部"}
SEGMENT_CN = {"Consumer": "消费者", "Corporate": "企业客户", "Home Office": "家庭办公"}
CATEGORY_CN = {"Office Supplies": "办公用品", "Furniture": "家具", "Technology": "技术产品"}
SHIP_CN = {"Standard Class": "标准快递", "Second Class": "二级快递",
           "First Class": "一级快递", "Same Day": "当日达"}
SUBCAT_CN = {
    "Binders": "装订用品", "Paper": "纸张", "Furnishings": "家居陈设", "Phones": "手机",
    "Storage": "收纳存储", "Art": "美术用品", "Accessories": "配件", "Chairs": "座椅",
    "Appliances": "小家电", "Labels": "标签", "Tables": "桌子", "Envelopes": "信封",
    "Bookcases": "书架", "Fasteners": "紧固用品", "Supplies": "耗材", "Machines": "机器设备",
    "Copiers": "复印机",
}
# RFM 八分类中文名
RFM_CN = {
    "重要价值客户": "重要价值客户", "重要唤回客户": "重要唤回客户",
    "重要深耕客户": "重要深耕客户", "重要挽留客户": "重要挽留客户",
    "潜力新客": "潜力新客", "一般保持客户": "一般保持客户",
    "一般发展客户": "一般发展客户", "流失客户": "流失客户",
}
MONTH_CN = {1: "1月", 2: "2月", 3: "3月", 4: "4月", 5: "5月", 6: "6月",
            7: "7月", 8: "8月", 9: "9月", 10: "10月", 11: "11月", 12: "12月"}


def money(v: float, unit: str = "万元") -> str:
    """金额友好格式化：默认按月/年汇总以“万美元”展示。"""
    if unit == "万美元":
        return f"{v / 1e4:,.1f} 万美元"
    if unit == "美元":
        return f"{v:,.0f} 美元"
    return f"{v:,.0f} 元"


def fmt_thousand(x, _pos=None):
    """坐标轴千分位格式。"""
    return f"{x:,.0f}"


def fmt_pct(x, _pos=None):
    """坐标轴百分比格式（输入为 0~1 的小数）。"""
    return f"{x:.0%}"


THOUSAND = FuncFormatter(fmt_thousand)
PERCENT = FuncFormatter(fmt_pct)

# ============================ 5. 保存工具 ============================
def save_fig(fig, filename: str, tight: bool = True) -> Path:
    """
    统一定稿保存：figXX_名称.png（150dpi 以上，白/暗底与当前风格一致）。
    同时在 figures 目录维护一份同名 png，便于论文直接引用。
    """
    if tight:
        fig.savefig(OUT_FIG / filename, dpi=200, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
    else:
        fig.savefig(OUT_FIG / filename, dpi=200, facecolor=fig.get_facecolor())
    path = OUT_FIG / filename
    print(f"  [√] 已保存图表：{filename}")
    return path


def save_table(df, filename: str) -> Path:
    """统一保存结果表到 outputs/tables（UTF-8-SIG，Excel 直接打开不乱码）。"""
    path = OUT_TAB / filename
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [√] 已保存结果表：{filename}")
    return path


def add_source_note(fig, text: str = "数据来源：Tableau 官方示例数据集 Sample–Superstore（2023–2026，10,194 条订单明细）"):
    """在图片右下角加数据来源脚注，符合学术图表规范。"""
    fig.text(0.995, 0.005, text, ha="right", va="bottom",
             fontsize=7.5, color=C["sub"], alpha=0.85)


if __name__ == "__main__":
    print(f"项目根目录：{ROOT}")
    print(f"中文字体：{CN_FONT}")
    print(f"原始数据存在：{RAW_XLS.exists()} -> {RAW_XLS}")
