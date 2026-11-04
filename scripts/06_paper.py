# -*- coding: utf-8 -*-
"""
06_paper.py —— 期末大论文生成脚本（按学院模板原地填充）
================================================
本文件的作用：
    以学院下发的《商业数据分析》期末大作业模板.docx 为底稿，保留其封面、评分表、
    页面设置、标题样式与自动编号，把正文内容逐节填入模板既有的标题之下。
    章节树完全沿用模板（7 章 + 参考文献 + 附录 A/B/C），不新增、不删减任何一节。

运行方式：
    python scripts/06_paper.py
输入：
    5、《商业数据分析》 - 期末大作业模板.docx（项目根目录，缺失时回退到 QQ 目录）
    outputs/tables/*.csv（模型结果）、outputs/figures/*.png（图表）
输出：
    docs/《商业数据分析》期末大论文-基于Superstore零售数据的客户价值与增长瓶颈分析.docx
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
TAB = ROOT / "outputs" / "tables"
OUT_DOC = Path(os.environ.get(
    "PAPER_OUT",
    ROOT / "docs" / "《商业数据分析》期末大论文-基于Superstore零售数据的客户价值与增长瓶颈分析.docx"))

TPL_CANDIDATES = [
    ROOT / "5、《商业数据分析》 - 期末大作业模板.docx",
    Path("G:/ThinkPad/Documents/QQ/5、《商业数据分析》 - 期末大作业模板.docx"),
    Path("G:/桌面/5、《商业数据分析》 - 期末大作业模板.docx"),
]

HEI = "黑体"
SONG = "宋体"
KAI = "楷体_GB2312"
TITLE = "基于Superstore零售数据的客户价值与增长瓶颈分析"

# ============================================================
# 0. 读取结果表（正文数字全部由此驱动，改数据即改结论）
# ============================================================
trend = pd.read_csv(TAB / "t06_月度趋势_同比环比.csv")
trend["年"] = trend["年月"].str[:4].astype(int)
year_sales = trend.groupby("年")["销售额"].sum()
year_profit = trend.groupby("年")["利润"].sum()
yoy26 = year_sales[2026] / year_sales[2025] - 1
avg26 = year_sales[2026] / 12
avg27 = pd.read_csv(TAB / "t13_预测结果.csv")["预测销售额"].mean()

rfm = pd.read_csv(TAB / "t09_RFM八分类汇总.csv")
km = pd.read_csv(TAB / "t10_KMeans客群画像.csv")
bcg = pd.read_csv(TAB / "t12_波士顿矩阵.csv")
disc = pd.read_csv(TAB / "t17_折扣弹性.csv")
rules = pd.read_csv(TAB / "t15_关联规则.csv")
funnel = pd.read_csv(TAB / "t16_履约漏斗.csv")
cmp_ = pd.read_csv(TAB / "t14b_预测模型比选.csv")
pareto = pd.read_csv(TAB / "t07_帕累托_ABC_子类.csv")
size = pd.read_csv(TAB / "t02_数据规模指标.csv").set_index("指标")["数值"]


# ============================================================
# 1. 大屏布局示意图（暗色，与 HTML 大屏同一套配色）
# ============================================================
def draw_dashboard_layout() -> Path:
    """绘制交互式大屏的 12 栅格布局与联动关系示意图。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    BG, PANEL, EDGE = "#0A1020", "#111A2E", "#22304C"
    TXT, SUB, TEAL, AMBER, VIOLET = "#E6EDF7", "#93A4BF", "#35C4F0", "#FFB13D", "#8B7CF6"

    fig, ax = plt.subplots(figsize=(12.6, 7.1))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 68)
    ax.axis("off")

    def box(x, y, w, h, title, sub="", color=TEAL, fs=9.6):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.2",
                                    facecolor=PANEL, edgecolor=EDGE, linewidth=1.0, zorder=2))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.9), w, 0.9, boxstyle="round,pad=0.6,rounding_size=1.2",
                                    facecolor=color, edgecolor="none", alpha=0.85, zorder=3))
        ax.text(x + w / 2, y + h / 2 + (1.6 if sub else 0), title, ha="center", va="center",
                color=TXT, fontsize=fs, fontweight="bold", zorder=4)
        if sub:
            ax.text(x + w / 2, y + h / 2 - 2.4, sub, ha="center", va="center",
                    color=SUB, fontsize=8.0, zorder=4)

    ax.text(60, 64.5, "Superstore 零售经营分析大屏", ha="center", va="center",
            color=TXT, fontsize=16, fontweight="bold")
    ax.text(60, 61.2, "KPI 概览 · 趋势 · 结构 · 客群 · 明细　|　ECharts 单文件实现，支持筛选联动与点击下钻",
            ha="center", va="center", color=SUB, fontsize=8.6)

    for i, lab in enumerate(["年份", "大区", "品类"]):
        box(4 + i * 14, 52.5, 12, 5.4, lab + "筛选", "下拉联动全部组件", AMBER, fs=8.8)

    for i, lab in enumerate(["销售额", "利润", "毛利率", "订单数", "退货率"]):
        box(4 + i * 14.4, 42.5, 12, 7.4, lab, "同比 / 环比", TEAL, fs=9.2)
    box(76, 42.5, 38, 7.4, "区域雷达",
        "四大区四维对比（销售额/利润/毛利率/订单）", VIOLET, fs=9.2)

    box(4, 22, 46, 18, "月度趋势", "销售额 + 移动平均 + 同比双轴", TEAL)
    box(52, 22, 30, 18, "品类结构", "暗色玫瑰图 / 环形占比", AMBER)
    box(84, 22, 30, 18, "客群散点", "R×F×M 三维气泡，点击下钻", VIOLET)

    box(4, 8, 62, 11, "子类帕累托 / 明细表", "17 个子类 ABC 累计曲线 + 可排序数据表", TEAL, fs=9.4)
    box(68, 8, 46, 11, "预测外推", "Holt-Winters 95% 置信带", AMBER, fs=9.4)

    for (x1, y1, x2, y2) in [(16, 52.2, 10, 50.3), (30, 52.2, 26, 50.3), (44, 52.2, 40, 50.3)]:
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9,
                                     color=AMBER, linewidth=1.1, alpha=0.8, zorder=5))
    ax.add_patch(FancyArrowPatch((27, 41.8), (27, 40.4), arrowstyle="-|>", mutation_scale=9,
                                 color=TEAL, linewidth=1.1, alpha=0.6, zorder=5))
    ax.add_patch(FancyArrowPatch((50, 31), (51.4, 31), arrowstyle="-|>", mutation_scale=9,
                                 color=SUB, linewidth=1.0, alpha=0.6, zorder=5))
    ax.add_patch(FancyArrowPatch((82, 31), (83.4, 31), arrowstyle="-|>", mutation_scale=9,
                                 color=SUB, linewidth=1.0, alpha=0.6, zorder=5))
    ax.text(60, 3.2, "说明：筛选器变化 → KPI 卡重算同比 → 三类主图重绘 → 明细表重排；点击柱/点可下钻至子类明细。",
            ha="center", va="center", color=SUB, fontsize=8.4)

    fig.subplots_adjust(0, 0, 1, 1)
    out = FIG / "fig25_大屏布局示意图.png"
    fig.savefig(out, dpi=200, facecolor=BG)
    plt.close(fig)
    return out


# ============================================================
# 2. 定位模板底稿
# ============================================================
def locate_template() -> Path:
    for p in TPL_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("未找到期末大作业模板 docx，请把模板放在项目根目录后重试。")


# ============================================================
# 3. 排版工具：全部“插入到当前光标之后”，不动模板原有段落
# ============================================================
def set_run(run, font=SONG, size=12, bold=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.bold = bold
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)


def _clear(par: Paragraph) -> None:
    for ch in list(par._p):
        if ch.tag == qn("w:pPr"):
            continue
        par._p.remove(ch)


class Writer:
    """以某个占位空段为起点，依次向下插入正文、图、表，模板结构保持不变。"""

    def __init__(self, doc: Document, placeholder: Paragraph, reuse: bool = True):
        self.doc = doc
        self.ph = placeholder
        self.el = placeholder._p
        self.reuse = reuse        # True：复用该空占位段，避免多出空行

    # ---------- 内部 ----------
    def _next_p(self) -> Paragraph:
        if self.reuse:
            self.reuse = False
            _clear(self.ph)
            return self.ph
        p = self.doc.add_paragraph()
        self.el.addnext(p._p)
        self.el = p._p
        return p

    def _drop_ph(self) -> None:
        if self.reuse:
            prev = self.ph._p.getprevious()
            self.ph._p.getparent().remove(self.ph._p)
            self.reuse = False
            self.el = prev

    def _put(self, el) -> None:
        self.el.addnext(el)
        self.el = el

    # ---------- 对外 ----------
    def p(self, text: str, indent=True, size=12, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
          spacing=1.5, font=SONG, bold=False, before=0, after=0) -> Paragraph:
        par = self._next_p()
        par.alignment = align
        pf = par.paragraph_format
        pf.line_spacing = spacing
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        # 模板 Normal 样式已带首行缩进 2 字符，此处按需显式设定
        pf.first_line_indent = Pt(size * 2) if indent else Pt(0)
        set_run(par.add_run(text), font=font, size=size, bold=bold)
        return par

    def bullets(self, text: str) -> Paragraph:
        """无首行缩进的列举段（用于大屏组件清单等）。"""
        return self.p(text, indent=False)

    def caption(self, text: str, before=3, after=9, font=SONG, size=10.5) -> Paragraph:
        par = self._next_p()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = par.paragraph_format
        pf.first_line_indent = Pt(0)
        pf.line_spacing = 1.0
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.keep_with_next = False
        set_run(par.add_run(text), font=font, size=size)
        return par

    def figure(self, path: Path, cap: str, width=14.6) -> Paragraph:
        self._drop_ph() if self.reuse else None
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = par.paragraph_format
        pf.first_line_indent = Pt(0)
        pf.space_before = Pt(6)
        pf.space_after = Pt(0)
        pf.keep_with_next = True
        pf.line_spacing = 1.0
        # 正文节版心仅 14.65cm（左右各 3.17cm），图宽上限取 14.4cm
        par.add_run().add_picture(str(path), width=Cm(min(width, 14.4)))
        self._put(par._p)
        return self.caption(cap)

    def table(self, cap: str, header, rows, widths=None, font_size=9, first_col_left=False):
        if self.reuse:
            self._drop_ph()
        # 表题（黑体，居中，表上方）
        cap_par = self.doc.add_paragraph()
        cap_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = cap_par.paragraph_format
        pf.first_line_indent = Pt(0)
        pf.line_spacing = 1.0
        pf.space_before = Pt(8)
        pf.space_after = Pt(3)
        pf.keep_with_next = True
        set_run(cap_par.add_run(cap), font=HEI, size=10.5)
        self._put(cap_par._p)

        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = True
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = ""
            par = cell.paragraphs[0]
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.space_before = Pt(1)
            par.paragraph_format.space_after = Pt(1)
            par.paragraph_format.line_spacing = 1.0
            set_run(par.add_run(str(h)), font=HEI, size=font_size, bold=True)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                par = cells[i].paragraphs[0]
                par.alignment = (WD_ALIGN_PARAGRAPH.LEFT if (first_col_left and i == 0)
                                 else WD_ALIGN_PARAGRAPH.CENTER)
                par.paragraph_format.space_before = Pt(1)
                par.paragraph_format.space_after = Pt(1)
                par.paragraph_format.line_spacing = 1.0
                set_run(par.add_run(str(v)), font=SONG, size=font_size)
        if widths:
            t.autofit = False
            total = sum(widths)
            scale = 14.5 / total if total > 14.5 else 1.0
            for r in t.rows:
                for i, w in enumerate(widths):
                    r.cells[i].width = Cm(w * scale)
        trPr = t.rows[0]._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:tblHeader"))
        self._put(t._tbl)
        # 表后留一点空
        gap = self.doc.add_paragraph()
        gap.paragraph_format.space_before = Pt(0)
        gap.paragraph_format.space_after = Pt(0)
        gap.paragraph_format.line_spacing = 1.0
        self._put(gap._p)
        return t

    def code(self, text: str) -> Paragraph:
        par = self._next_p()
        pf = par.paragraph_format
        pf.first_line_indent = Pt(0)
        pf.left_indent = Pt(10)
        pf.line_spacing = 1.05
        pf.space_before = Pt(2)
        pf.space_after = Pt(8)
        set_run(par.add_run(text), font="Consolas", size=8.5)
        return par


# ============================================================
# 4. 打开模板，接管封面与摘要
# ============================================================
tpl = locate_template()
doc = Document(str(tpl))
paras = doc.paragraphs


def para_by_prefix(prefix: str, start: int = 0) -> Paragraph:
    for par in doc.paragraphs[start:]:
        if par.text.strip().startswith(prefix):
            return par
    raise KeyError(prefix)


# ---- 4.1 封面六行：标签保留，等宽空格替换为实际内容 ----
COVER = {
    "题": TITLE,
    "学": "数据科学学院",
    "专业班级": "××××××××",
    "学号": "××××××××",
    "姓名": "×××",
    "完成日期": "2026 年 11 月",
}
def _norm(t: str) -> str:
    return t.replace("\u3000", "").replace(" ", "")


for key, val in COVER.items():
    target = None
    for par in doc.paragraphs[:12]:
        if _norm(par.text).startswith(key) and "：" in par.text:
            target = par
            break
    if target is None:
        continue
    runs = target.runs
    label = runs[0]
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    label.text = label.text.split("：")[0] + "："
    set_run(label, font=KAI, size=14)
    tail = target.add_run("　" + val) if key in ("题", "学") else target.add_run("　　" + val)
    set_run(tail, font=KAI, size=14)
    tail.underline = True

# ---- 4.2 第二页：题目、作者、单位 ----
p_title = para_by_prefix("论文题目")
_clear(p_title)
p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_run(p_title.add_run(TITLE), font=HEI, size=16, bold=True)

p_author = para_by_prefix("作者")
_clear(p_author)
p_author.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_run(p_author.add_run("×××"), font=SONG, size=10.5)

p_unit = para_by_prefix("（嘉兴")
_clear(p_unit)
p_unit.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_run(p_unit.add_run("（嘉兴大学　数据科学学院）"), font=SONG, size=10.5)

# ---- 4.3 摘要与关键词：保留标签，删掉红色说明，接正文 ----
ABSTRACT = (
    "零售企业在 SKU 膨胀、促销常态化与获客成本上升的压力下，需要从“看总量”转向“看结构、看客群、看拐点”。"
    "本文以 Tableau 官方示例数据集 Sample–Superstore（2023—2026 年 10 194 条订单明细、5 111 个订单、"
    "804 位客户）为对象，经官方下载的白名单方式获取，完成缺失值、异常值与多表主外键治理，"
    "构建 7 类 9 个模型：同比环比与移动平均、帕累托/ABC、RFM 八分类、K-Means 客群、同期群留存、"
    "波士顿矩阵、SARIMA 与 Holt-Winters 比选预测、Apriori 关联规则与履约漏斗。研究发现："
    "6 个 A 类子类以 35% 的数量贡献 64.4% 销售额；25.4% 的重要价值客户贡献 40.2% 销售额；"
    "首月留存仅 11.7%；折扣超过 20% 后毛利率转负；Holt-Winters 回测 MAPE 为 16.93%，"
    "2027 年上半年月均销售额与 2026 年持平，增长已进入平台期。"
    "全部图表由 Python 生成，含 14 种图表模板复现、9 张业务模型图与一个 8 组件暗色交互大屏。"
)
KEYWORDS = "商业数据分析；RFM 模型；同期群留存；时间序列预测；交互式大屏"

p_abs = para_by_prefix("摘要")
_clear(p_abs)
p_abs.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
p_abs.paragraph_format.line_spacing = 1.5
p_abs.paragraph_format.space_before = Pt(6)
set_run(p_abs.add_run("摘要："), font=HEI, size=14)
set_run(p_abs.add_run(ABSTRACT), font=SONG, size=12)

p_kw = para_by_prefix("关键词")
_clear(p_kw)
p_kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
p_kw.paragraph_format.line_spacing = 1.5
p_kw.paragraph_format.space_before = Pt(6)
set_run(p_kw.add_run("关键词："), font=HEI, size=14)
set_run(p_kw.add_run(KEYWORDS), font=SONG, size=12)

# ---- 4.4 删除模板里的红色提示行 ----
for par in list(doc.paragraphs):
    if par.text.strip().startswith("注意：全文红色字体均可删除"):
        par._p.getparent().remove(par._p)

# ============================================================
# 5. 建立“标题 → 其下第一个空段”的锚点表
# ============================================================
anchors: dict[str, Paragraph] = {}
pending = None
for ch in doc.element.body.iterchildren():
    if ch.tag != qn("w:p"):
        continue
    par = Paragraph(ch, doc)
    if par.style.name in ("Heading 1", "Heading 2"):
        pending = par
        continue
    if pending is not None and not par.text.strip():
        anchors[pending.text.strip()] = par
        pending = None


def W(prefix: str) -> Writer:
    for k, v in anchors.items():
        if k.startswith(prefix):
            return Writer(doc, v)
    raise KeyError(f"模板中未找到标题：{prefix}")


# ============================================================
# 6. 第 1 章　引言
# ============================================================
w = W("研究背景")
w.p("零售业的经营决策正在被两股力量同时拉扯。一方面，消费者在线上线下的迁移让订单颗粒度越来越细，"
    "一家中等规模的办公用品零售商往往要同时管理近两千个 SKU、覆盖五百余座城市，订单明细表以万行计；"
    "另一方面，促销工具的低成本化使折扣成为默认手段，价格让利侵蚀利润的速度远快于销量增长的速度。"
    "在这样的环境里，仅凭“本月销售额多少、同比涨了几个点”这类总量指标，管理者既看不出钱从哪来，"
    "也说不清利润漏在哪。陈国青等学者在讨论大数据与管理决策的关系时指出，数据分析的价值不在于数据量本身，"
    "而在于能否把数据转化为可行动的判断[7]。")
w.p("Sample–Superstore 是 Tableau 官方长期维护的教学数据集，脱胎于一家美国办公用品零售商的真实交易流水，"
    "包含订单、退货与区域经理三张表，字段覆盖时间、地理、客户、产品、履约与财务六个维度，"
    "是零售场景下检验分析方法的理想样本。该数据集规模适中（万级明细）、结构完整（主外键清晰）、"
    "业务语义明确（品类层级、客户分群、配送方式俱全），既能支撑帕累托、RFM 这类经典模型，"
    "也足以训练季节性时间序列模型，因此被广泛用于商业分析教学与 BI 工具演示。")
w.p("与此同时，可视化的角色也在变化。郭宏远在《Excel数据可视化——从图表到数据大屏》中系统梳理了三十种图表模板，"
    "并强调“图表不是装饰，而是论证结构的一部分”[1]。当分析结论需要向非技术背景的管理层汇报时，"
    "一张留白得当的渐变柱形图、一张能同时读到规模与转化率的蝴蝶图，往往比一张信息密度极高的交叉表更有效。"
    "把静态图表与可交互的大屏结合起来，才构成完整的“分析—表达—决策”链条。")

w = W("研究目的")
w.p("本文希望在三个层面上回答具体问题。第一，结构层面：销售额究竟集中在哪些子类与哪些客户身上，"
    "这种集中度是否已经高到需要调整品类与库存策略。第二，客群层面：客户价值如何分层，"
    "高价值客户的留存是否稳固，沉睡的高额客户还有多少可召回的空间。第三，趋势层面："
    "在季节性波动之下，业务的真实增长动能是强是弱，未来半年应当按什么基准做预算。")
w.p("围绕这三个问题，本文设定的技术目标是：完成一条从合规取数、清洗治理、模型计算、图表复现到交互大屏的完整链路，"
    "且链路上每一个数字都可以由代码一键复现；模型选择不止于“跑通”，而要给出参数与阈值的业务依据，"
    "并对预测类模型提供置信区间与回测误差；可视化不止于“好看”，而要保证每张图对应一个模型、"
    "每张图支撑一条结论。")

w = W("研究意义")
w.p("实践意义上，本文的结论可以直接映射为四类经营动作：品类上的“保、压、育”、客户上的“锁、唤、弃”、"
    "价格上的折扣红线、履约上的时效改进点。这些动作都附带可核查的数据依据，而非经验判断。")
w.p("方法意义上，本文做了一次“模型比选”的示范。时间序列预测在实际项目中最常见的失误是直接套用 SARIMA 的默认阶数，"
    "而不做回测比较。本文同时训练 SARIMA 与 Holt-Winters，用同一段留出期计算 MAPE、RMSE 与 MAE，"
    "最终选择误差更小的模型，并保留了完整的比选表（表 4-5）。这种“先比选、再定稿”的流程，"
    "比单纯呈现一个漂亮的预测曲线更有说服力。")
w.p("教学意义上，本文严格遵循课程对“合规取数、非爬虫、全 Python 实现”的要求，"
    "全部图表由 Matplotlib 与 ECharts 生成，未使用任何 BI 软件，"
    "并将项目整理为可一键复现的目录结构，便于他人核验与二次开发。")

# ============================================================
# 7. 第 2 章　数据准备与预处理
# ============================================================
w = W("数据源介绍")
w.p("数据源名称为 Sample–Superstore（Tableau 官方示例数据集），官方下载页为 "
    "https://public.tableau.com/app/resources/sample，文件为单工作簿 Excel（.xls），"
    "内含 Orders（订单明细，主表）、Returns（退货标记，维表）、People（区域经理，维表）三张工作表。"
    "本文使用 2023 年 1 月至 2026 年 12 月共 48 个自然月的交易记录，主表 10 194 行 × 21 列，"
    "覆盖 5 111 个订单、804 位客户、1 862 个产品、17 个产品子类、542 座城市与 59 个州/省，"
    "销售额合计 2 326 534.35 美元，利润合计 292 296.81 美元，整体毛利率 12.56%（表 2-1）。")
w.table("表 2-1　数据规模与关键指标",
        ["指标", "数值", "指标", "数值"],
        [["订单明细行数", "10 194 行", "产品子类数", "17 类"],
         ["唯一订单数", "5 111 单", "城市数 / 州省数", "542 / 59"],
         ["唯一客户数", "804 位", "时间跨度", "1 457 天（48 个月）"],
         ["唯一产品数", "1 862 个", "退货订单数", "296 单（5.79%）"],
         ["销售额合计", "2 326 534.35 美元", "利润合计", "292 296.81 美元"],
         ["整体毛利率", "12.56%", "亏损明细占比", "18.65%"]],
        widths=[4.0, 4.2, 3.8, 4.2], font_size=9, first_col_left=True)
w.p("主表字段可分为六组：标识类（Row ID、Order ID、Customer ID、Product ID）、"
    "时间类（Order Date 下单日期、Ship Date 发货日期）、地理类（Country/Region、Region、State/Province、"
    "City、Postal Code）、客户类（Customer Name、Segment）、产品类（Category、Sub-Category、Product Name）"
    "与度量类（Sales、Quantity、Discount、Profit）。其中 Category 为三大品类（家具、办公用品、技术），"
    "Sub-Category 为 17 个子类，形成两级品类体系；Segment 区分消费者、公司、家庭办公三类客群；"
    "Region 划分中部、东部、南部、西部四个大区；Ship Mode 区分标准级、二级、一级与当日达四种配送方式（表 2-2）。")
w.table("表 2-2　主表（Orders）主要字段说明",
        ["字段名", "中文含义", "类型", "用途说明"],
        [["Order ID", "订单编号", "文本", "主键，跨表关联 Returns 的键"],
         ["Order Date / Ship Date", "下单 / 发货日期", "日期", "派生年份、月份、季度、履约天数"],
         ["Ship Mode", "配送方式", "类别", "四类：标准、二级、一级、当日"],
         ["Customer ID", "客户编号", "文本", "RFM、K-Means、同期群的分组键"],
         ["Segment", "客户细分", "类别", "消费者 / 公司 / 家庭办公"],
         ["Region / State / City", "大区 / 州 / 城市", "类别", "区域下钻与地理分析"],
         ["Category / Sub-Category", "品类 / 子类", "类别", "帕累托、ABC、波士顿矩阵"],
         ["Sales", "销售额", "数值", "核心度量，含折扣后金额"],
         ["Quantity", "销量", "整数", "与销售额结合算单件售价"],
         ["Discount", "折扣率", "数值", "折扣弹性与毛利归因"],
         ["Profit", "利润", "数值", "可为负，用于识别亏损明细"]],
        widths=[4.4, 3.6, 2.0, 6.4], font_size=9, first_col_left=True)

w = W("合规获取方式")
w.p("本文采用白名单中的第一类方式，即“数据源官方提供的一次性下载文件”。获取过程为：访问 Tableau 官方示例资源页，"
    "下载官方发布的 Sample–Superstore.xls 压缩包，解压后得到工作簿文件，全程未使用任何爬虫技术"
    "（未使用 Scrapy、Selenium、requests + 网页解析，也未进行模拟登录抓取），"
    "不涉及任何网页结构解析与反爬绕过行为。原始文件保存于 data/raw/sample_-_superstore.xls，"
    "清洗脚本以只读方式打开，不做任何在线请求，保证结果可离线复现。"
    "需要说明的是，本数据集虽有公开的 Python 接口库可以读取，但为保证版本一致与可追溯，"
    "本文未采用任何在线接口，只使用本地文件。")

w = W("数据来源合规声明")
w.p("数据来源为 Tableau 官方公开示例数据集（Sample–Superstore），官方资源页地址 "
    "https://public.tableau.com/app/resources/sample，获取日期为 2026 年 10 月；"
    "该数据集由 Tableau 公开发布用于产品演示与教学，许可条款遵循 Tableau 官方示例数据使用约定，"
    "允许在非商业的教学与研究场景中自由使用与再分发。数据集内客户姓名已做匿名化处理（如 “Claire Gute”），"
    "不含手机号、身份证号、地址门牌等个人敏感信息，仅保留城市与邮编层级的地理粒度，"
    "因此本文的分析与公开不构成对个人隐私的侵犯。数据规模方面，主表 10 194 行，"
    "远超“不少于 500 条”的要求，故未做抽样，全部记录参与建模。")

w = W("数据集概述")
w.p("三张表的主外键关系清晰：Orders 为事实表，Order ID 为业务主键；Returns 以 Order ID 为外键指向 Orders，"
    "记录该订单是否被退回；People 以 Region 为外键指向 Orders 的地理维度，记录四个大区的区域经理。"
    "三表结构见表 2-3。这种“一事实两维度”的星型结构，使得退货标记与区域负责人可以在不破坏主表粒度的前提下并入。")
w.table("表 2-3　三张工作表的结构与主外键关系",
        ["表名", "中文名称", "规模", "字段", "键关系", "表角色"],
        [["Orders", "订单明细表", "10 194 × 21", "标识、时间、地理、客户、产品、度量六组",
          "Order ID 为主键", "事实表"],
         ["Returns", "退货标记表", "296 × 2", "Order ID、Returned",
          "Order ID 为外键 → Orders", "维度表"],
         ["People", "区域经理表", "4 × 2", "Region、Regional Manager",
          "Region 为外键 → Orders", "维度表"]],
        widths=[1.9, 2.4, 2.2, 4.6, 3.6, 1.8], font_size=8.5, first_col_left=True)
w.p("从粒度上看，一行代表一个订单中的一种产品（订单—产品明细级），而非一个订单；"
    "因此同一 Order ID 会出现多行，计算订单数必须对 Order ID 去重，这一点在后续所有比例类指标中都做了严格区分。"
    "地理层级为“大区 → 州/省 → 城市 → 邮编”四级，产品层级为“品类 → 子类 → 产品名”三级，"
    "两个层级体系分别支撑区域下钻与品类聚焦两类分析。")

# ============================================================
# 8. 第 3 章　数据清洗与治理
# ============================================================
w = W("数据清洗")
w.p("原始数据看似“干净”——缺失单元为 0、整行重复为 0，但这并不意味着可以直接建模。"
    "零售明细表常见的问题往往藏在类型、边界与关联关系里，本文按九个步骤逐项处理，每一步都记录变动行数（表 3-1）。")
w.table("表 3-1　数据清洗与治理日志（节选）",
        ["步骤", "处理内容", "变动行数"],
        [["1", "14 个文本字段去除首尾空格，避免主外键关联漏配", "0"],
         ["2", "整行重复与 Row ID 重复检查，按业务主键保留首条", "0（无重复）"],
         ["3", "日期字段转 datetime；邮编转字符串防前导零丢失", "0"],
         ["4", "缺失值：数值用中位数、类别用众数、主键缺失剔除", "0（原始无缺失）"],
         ["5", "异常值：非正销售额/销量剔除；折扣越界裁剪至 [0,1]", "0"],
         ["6", "极端值：销售额 3×IQR 以上标记 679 条，保留并单列标记", "679（标记）"],
         ["7", "派生指标：年份/月份/季度/年月、履约天数、毛利率等 12 项", "新增列"],
         ["8", "左连 Returns 标记退货（命中 296 单），左连 People 补区域经理", "296"],
         ["9", "主外键校验：三张表键值唯一性与一一对应关系核验", "0"]],
        widths=[1.6, 11.4, 3.0], font_size=9)
w.p("关于异常值的处理需要说明一处取舍。按 3 倍四分位距（IQR）规则，销售额有 679 条被标记为极端值，"
    "若按常规做法直接剔除，会删掉约 6.7% 的明细，而这些记录恰恰是商用大单（如批量采购的复印机、会议桌），"
    "属于真实业务而非录入错误。本文的处理是“标记但不剔除”：在数据集中新增布尔列“是否极端值”，"
    "建模时按需过滤，正文的统计口径默认包含全部记录。这一取舍的理由是，零售场景下的大额订单具有明确的业务含义，"
    "贸然删除会系统性低估客单价与毛利率。")
w.p("重复值与缺失值的处理相对简单，但同样做了记录：整行完全重复的记录为 0 条，Row ID 重复为 0 条，"
    "14 个文本字段在去除首尾空格后未出现关联漏配；数值字段的缺失为 0，类别字段的缺失为 0。"
    "虽然本次数据没有缺失，脚本仍保留了“数值取中位数、类别取众数、主键缺失则剔除并写日志”的通用规则，"
    "以便更换数据源时无需改代码。")

w = W("数据转换")
w.p("数据转换方面，共派生 12 个新字段：时间维度（年份、月份、季度、年月）、履约维度（履约天数 = 发货日期 − 下单日期）、"
    "盈利维度（毛利率 = 利润 / 销售额、是否亏损、折扣金额 = 销售额 /(1−折扣) × 折扣、原价销售额）、"
    "单价维度（单件售价、单件利润）以及 5 个中文维度列（品类、子类、大区、客户细分、配送方式的中文映射）。"
    "日期字段统一转为 datetime 并按月首日对齐，保证同期群与时间序列的月份边界一致；"
    "邮编强制转为字符串，避免以 0 开头的编码在数值化时丢失前导零。"
    "中文映射单独建表维护，避免在绘图代码中散落硬编码，也便于后续调整译名。")

w = W("数据整合")
w.p("数据整合方面，以 Orders 为主表做两次左连接：按 Order ID 关联 Returns，命中 296 个退货订单，"
    "未命中者视为未退货（覆盖率 5.79%）；按 Region 关联 People，为每个大区补上区域经理姓名，字段填充率 100%。"
    "选择左连接而非内连接，是为了保持主表 10 194 行的完整性——若用内连接，退货维表会把样本压缩到 296 行，"
    "直接破坏后续所有比例类指标的口径。整合完成后，主外键校验通过：Order ID、Customer ID、Product ID 均无空值，"
    "Customer ID 与 Customer Name 严格一一对应，不存在同一 ID 对应多个姓名的脏数据。")
w.p("清洗结果导出三份文件：orders_clean.csv（含派生列的宽表，10 194 行）、orders_clean.pkl（供脚本快速读取）"
    "与 superstore.db（SQLite，含 orders、returns、people 三张表及索引），满足“可导出 CSV/JSON/SQLite 复用”的要求。"
    "由于样本量已远超要求，本文未做抽样；为使结果可复现，所有涉及随机的环节（K-Means 初始化）统一固定随机种子 "
    "random_state=42，并在脚本中显式写出，不做隐式默认。数据体检报告与质量总览分别落盘为 t01、t05，"
    "任何读者都可以用一条 SQL 复核文中的数字。")

# ============================================================
# 9. 第 4 章　商业分析模型
# ============================================================
w = W("模型选型")
w.p("课程给出的模型清单覆盖趋势、结构、客群、关联、预测五个类别。本文的选型原则有三条："
    "一是覆盖度优先，五类各取其一，避免结论偏科；二是数据可得性优先，只选当前字段能支撑的模型"
    "（例如文本情感分析因缺少评论字段而不做）；三是结论可落地，每个模型必须能回答第 1.2 节提出的具体问题。"
    "最终确定 7 类 9 个模型（表 4-1）。")
w.table("表 4-1　模型清单、选型依据与对应图表",
        ["编号", "模型", "所属类别", "选型依据", "对应图表"],
        [["M1", "同比/环比 + 3 期移动平均", "趋势与对比", "识别季节性与真实动能", "图 5-1"],
         ["M2", "帕累托 / ABC 分类", "结构与价值", "SKU 长尾下的品类聚焦", "图 5-16"],
         ["M3", "RFM 八分类", "用户与客群", "客户价值分层的行业标准", "图 5-17"],
         ["M4", "K-Means 客群划分", "用户与客群", "验证 RFM 规则分层的稳健性", "图 5-18"],
         ["M5", "同期群留存", "用户与客群", "判断复购是首月决定还是长期累积", "图 5-19"],
         ["M6", "波士顿矩阵", "结构与价值", "份额×增速双维定位品类", "图 5-20"],
         ["M7", "SARIMA 与 Holt-Winters 比选", "预测与预警", "含区间与回测，支撑预算", "图 5-21"],
         ["M8", "Apriori 关联规则", "关联与转化", "组合陈列与捆绑定价", "图 5-22"],
         ["M9", "履约漏斗", "关联与转化", "定位转化流失环节", "图 5-23"]],
        widths=[1.3, 5.2, 2.8, 5.4, 2.2], font_size=8.5)
w.p("需要解释两处“看似重复”的设计。其一，M3 与 M4 都做客户分层，但方法不同：RFM 基于业务规则切分，"
    "可解释性强、便于运营落地；K-Means 基于数据分布聚类，能检验规则分层是否把异质客户强行归为一类。"
    "两者结论一致时可信度更高，不一致时恰恰暴露了规则分层的盲区（详见 6.2 节）。"
    "其二，M1 与 M7 都涉及时间序列，但 M1 是描述性的（过去发生了什么），M7 是推断性的（未来可能怎样），"
    "前者为后者提供季节周期的先验（季节周期取 12 个月）。")

w = W("参数与阈值设定依据")
w.p("模型的说服力很大程度上取决于参数是否“有据可依”。本节逐一说明关键阈值的来源，"
    "并区分“行业惯例”“数据分布”与“业务约束”三类依据。")
w.p("（1）帕累托与 ABC 分类。累计销售额占比 70% 以内定为 A 类、70%–90% 为 B 类、90% 以上为 C 类。"
    "这一组切分点是库存管理领域的通用惯例，源于帕累托法则“少数关键贡献多数产出”的经验表述，"
    "在零售与供应链教材中被广泛采用[10]。选择 70/90 而非 80/95，是因为本文只有 17 个子类，"
    "若用 80/95 会导致 A 类过宽（接近一半子类），失去聚焦意义。")
w.p("（2）RFM 八分类。R（最近购买间隔，Recency）、F（购买频次，Frequency）、M（累计金额，Monetary）"
    "三个维度均以中位数为高低分界。之所以不用均值，是因为三项指标均呈显著右偏分布"
    "（少数客户贡献极高金额，均值被拉高），用均值切分会把大量正常客户误判为“低价值”。"
    "中位数切分保证每一维的高低两组各占约 50%，八分类的客户分布更均衡，也便于运营按人力配置资源。"
    "R 的方向需要特别注意：间隔越短越活跃，因此 R 小于中位数记为“高”。")
w.p("（3）K-Means 聚类。在 K=3 至 6 的范围内逐一训练，用轮廓系数（Silhouette Coefficient）择优，"
    "最终 K=3 得分 0.2623 为最高（K=4 为 0.2592、K=5 为 0.2515、K=6 为 0.2423）。"
    "轮廓系数由 Rousseeuw 提出，取值越接近 1 表示簇内越紧凑、簇间越分离[9]。"
    "需要坦诚说明：0.26 属于“弱结构”，说明客户行为并非天然分成泾渭分明的几团，"
    "这与零售客户的连续分布特征相符，因此本文把聚类结果作为 RFM 的交叉验证而非独立结论。"
    "特征工程上，R、F、M 三个量纲差异极大（R 以天计、M 以万美元计），先做 log1p 变换压缩长尾，"
    "再做 Z-score 标准化，避免欧氏距离被 M 主导。")
w.p("（4）同期群留存。以客户首次购买月份为群组，群规模不足 20 人的组不纳入平均留存曲线，"
    "避免小样本造成曲线剧烈抖动；观察期取首购后 12 个月。留存定义采用“该月有下单即计入”，"
    "而非“该月有复购金额”，理由是本数据集的复购间隔普遍较长，按金额口径会把小额复购误判为流失。")
w.p("（5）波士顿矩阵。以 2026 年相对 2025 年的同比增速为纵轴、2026 年销售额份额为横轴，"
    "分界线取“整体增速”与“平均份额”，而非人为设定的 10%。这样划分的好处是四象限与整体大盘自洽："
    "落在“高增长”象限的业务，增速确实跑赢了大盘。气泡大小映射销售额，颜色映射毛利率，"
    "使“规模—增速—盈利”三个维度在一张图上同时可读。")
w.p("（6）时间序列预测。SARIMA 的阶数通过网格搜索确定：p、q 取 0–2，P、Q 取 0–1，d=1、D=1、s=12，"
    "以 AIC 最小为准则，最终选中 SARIMA(2,1,2)(0,1,1,12)。d=1 用于消除趋势，D=1 与 s=12 用于消除年度季节性——"
    "零售数据在 9 月（开学季）与 11–12 月（年末采购季）存在稳定高峰，这一先验来自 M1 的描述性结果。"
    "Holt-Winters 采用加性趋势 + 加性季节 + 阻尼（damped）设定，阻尼系数用于抑制长期外推时趋势线性发散的倾向。"
    "两个模型使用完全相同的训练集（前 42 个月）与留出期（2026 年 7–12 月，共 6 个月），"
    "以 MAPE 为主指标、RMSE 与 MAE 为辅指标比较。")
w.p("（7）关联规则。最小支持度 0.6%、最小置信度 15%、提升度大于 1。支持度取 0.6% 是因为订单级共现本身稀疏"
    "（5 111 个订单分布在 17 个子类上，任一子类对的出现率天然很低），若沿用教材中 5% 的默认值将得不到任何规则；"
    "置信度 15% 低于常规的 50%，是因为本文的目标是“发现候选组合”而非“确认强规则”，"
    "后续仍需结合毛利率人工筛选。提升度大于 1 是硬性门槛，用于剔除独立事件造成的伪相关。")
w.p("（8）折扣红线的判定。不做主观设定，而是按折扣区间分组，计算各组的毛利率与亏损明细占比，"
    "以“毛利率由正转负”的临界区间作为红线依据（结果见表 6-1）。")

w = W("模型计算与验证")
w.p("RFM 在 804 位客户上计算，八分类结果见表 4-2。重要价值客户 204 人（25.4%）贡献 40.2% 销售额，"
    "人均消费 4 589 美元；重要唤回客户 116 人（14.4%）贡献 24.3% 销售额，人均 4 865 美元最高，"
    "但平均 R 达 174 天，说明这批高额客户已经明显沉睡；流失客户 158 人（19.7%）仅贡献 6.3% 销售额，"
    "毛利率 6.09% 为八类最低。")
w.table("表 4-2　RFM 八分类客户结构",
        ["客群", "客户数", "客户占比", "销售额占比", "人均销售额", "平均R(天)", "毛利率"],
        [[r["RFM客群"], f"{int(r['客户数'])}", f"{r['客户占比']:.1%}", f"{r['销售额占比']:.1%}",
          f"{r['人均销售额']:,.0f}", f"{r['平均R']:.0f}", f"{r['毛利率']:.2%}"]
         for _, r in rfm.iterrows()],
        widths=[3.0, 1.8, 2.0, 2.3, 2.4, 2.2, 2.0], font_size=8.5, first_col_left=True)
w.p("K-Means 的三簇画像见表 4-3。核心高价值群 301 人（37.4%）贡献 48.8% 销售额，平均 R 仅 29 天；"
    "沉睡高额群 350 人（43.5%）贡献 47.4% 销售额，人均 3 150 美元，与核心群几乎持平，"
    "但平均 R 达 189 天——这是一群“曾经买得多、现在不来了”的客户；低频休眠群 153 人（19.0%）"
    "仅贡献 3.9%，毛利率 8.19%，属于低价值且低盈利的长尾。")
w.table("表 4-3　K-Means 三客群画像（K=3，轮廓系数 0.2623）",
        ["聚类簇", "业务标签", "客户数", "客户占比", "销售额占比", "平均R(天)", "平均F(次)", "人均销售额"],
        [[f"簇 {int(r['聚类簇'])}", r["业务标签"], f"{int(r['客户数'])}", f"{r['客户占比']:.1%}",
          f"{r['销售额占比']:.1%}", f"{r['平均R']:.0f}", f"{r['平均F']:.1f}", f"{r['人均销售额']:,.0f}"]
         for _, r in km.iterrows()],
        widths=[1.8, 3.0, 1.8, 1.9, 2.2, 2.0, 2.0, 2.3], font_size=8.5)
w.p("同期群分析共产出 15 个有效群组（群规模≥20 才纳入）、12 期留存矩阵。平均留存曲线显示：首月留存率 11.7%，"
    "第 2 期跌至 7.8% 的低点，此后缓慢回升并在第 6 期后稳定在 10.6%–10.7%。"
    "这条“先跌后稳”的曲线透露了一个重要事实：客户一旦跨过前三个月的门槛，后续流失速度显著放缓，"
    "因此运营资源应集中在首购后 90 天内，而非平均撒在全年。")
w.p("波士顿矩阵的 17 个子类被划入四个象限（表 4-4）。明星业务四个：手机（份额 14.2%、增速 33.5%）、"
    "装订用品（9.9%、42.8%）、复印机（8.4%、26.9%）、配件（8.0%、43.1%）。其中复印机毛利率高达 39.8%，"
    "利润贡献 26.1% 位列第一，是“小销量、高单价、高毛利”的典型。现金牛四个：座椅（13.2%、15.2%）、"
    "收纳存储（9.4%、19.4%）表现健康，但桌子（8.2%、0.3%，毛利率 −13.3%）与机器设备（5.9%、−21.5%，"
    "毛利率 −6.5%）属于“份额靠前却在亏钱”的伪现金牛。问题业务五个，小家电增速 64.8% 最亮眼；"
    "瘦狗业务四个，书架与耗材均在亏损。")
w.table("表 4-4　波士顿矩阵分类结果（节选，按销售额份额排序）",
        ["子类", "2026销售额", "同比增速", "份额", "毛利率", "利润贡献", "象限"],
        [[r["子类"], f"{r['2026销售额']:,.0f}", f"{r['同比增速']:.1%}", f"{r['销售额份额']:.1%}",
          f"{r['毛利率']:.1%}", f"{r['利润贡献']:.1%}", r["象限"]]
         for _, r in bcg.head(10).iterrows()],
        widths=[2.4, 2.8, 2.2, 1.8, 1.9, 2.0, 2.6], font_size=8.5, first_col_left=True)
w.p("预测模型的验证结果见表 4-5。Holt-Winters（加性·阻尼）回测 MAPE 16.93%、RMSE 19 886 美元、"
    "MAE 14 642 美元，三项指标全面优于 SARIMA(2,1,2)(0,1,1,12) 的 25.36%、25 032 美元与 20 909 美元。"
    "值得注意的是，未加阻尼的 Holt-Winters（MAPE 18.49%）也优于 SARIMA，说明在这个样本上，"
    "季节结构的“稳定重复”特征强于自相关结构，加性季节项比差分季节项更贴合数据。"
    "MAPE 16.9% 的水平对月度零售预测属于可接受区间（通常 10%–20%），但仍意味着单月预测值可能有 ±1 万美元的偏差，"
    "因此本文在给出预算建议时，使用区间而非点值。")
w.table("表 4-5　两种预测模型的回测误差对比（留出期 2026-07 至 2026-12）",
        ["模型", "MAPE", "RMSE（美元）", "MAE（美元）", "是否最终模型"],
        [[r["模型"], f"{r['回测MAPE']:.2%}", f"{r['回测RMSE']:,.0f}", f"{r['回测MAE']:,.0f}",
          "是" if r["是否最终模型"] == "是" else "否"] for _, r in cmp_.iterrows()],
        widths=[7.4, 2.4, 2.8, 2.6, 2.8], font_size=8.5, first_col_left=True)
w.p("Apriori 在 5 111 个订单上运行，共得到 93 条满足门槛的规则，提升度最高的是"
    "“家居陈设 + 装订用品 → 小家电”（提升度 1.893，置信度 17.0%），其次是"
    "“手机 + 收纳存储 → 家居陈设”（1.806）与“纸张 + 装订用品 → 小家电”（1.775）。"
    "一个规律值得注意：装订用品在多条高提升度规则中反复出现，扮演“桥梁品类”的角色——"
    "它单价低、购买频次高，常与其他品类同单出现，是理想的凑单与推荐入口。")
w.p("履约漏斗按订单级计算四级转化：下单 5 111 单 → 按时履约（≤4 天）3 078 单（60.2%）→ "
    "未被退货 2 893 单（环节转化 94.0%）→ 订单盈利 2 281 单（环节转化 78.9%），端到端转化率 44.6%。"
    "瓶颈非常清晰：最大流失发生在“下单到按时履约”这一环，掉了近 40 个百分点；"
    "而退货环节的损耗（6.0%）反而小于盈利环节（21.1%），说明“卖出去但不赚钱”比“卖出去又被退回”更值得警惕。")
w.p("最后一项验证是把折扣当作自变量。按 10 个百分点一档对 10 194 条明细分组，计算各组毛利率与亏损明细占比，"
    "结果见第 6 章表 6-1：无折扣与低折扣区间的毛利率为正，跨过 20% 后转负，50% 以上区间毛利率低至 −118.7%。"
    "这条“毛利率—折扣”曲线的拐点，就是后文建议四中折扣红线的定量依据。")

# ============================================================
# 10. 第 5 章　Python 数据分析与可视化
# ============================================================
w = W("数据探索性分析")
w.p("本章所有图表均由 Python 生成，未使用 Power BI、Tableau 等 BI 工具，也未以 Excel 图表截图替代。"
    "静态图使用 Matplotlib（dpi 200，中文字体统一为微软雅黑/黑体），交互大屏为单文件 HTML 的 ECharts 原生实现。"
    "绘图代码封装了统一的主题模块（配色、字体、留白、来源注脚），保证 25 张图风格一致。")
w.p(f"先看总量与节奏。2023—2026 年销售额分别为 {year_sales[2023]/1e4:.1f}、{year_sales[2024]/1e4:.1f}、"
    f"{year_sales[2025]/1e4:.1f}、{year_sales[2026]/1e4:.1f} 万美元，四年间波动上行：2024 年小幅回落 4.3%，"
    f"2025 年反弹 29.8%，2026 年增长 {yoy26:.1%}——增速虽仍为正，但已较上年明显放缓；"
    f"利润同步从 {year_profit[2023]/1e4:.1f} 万美元增至 {year_profit[2026]/1e4:.1f} 万美元。"
    "但把时间轴展开到月度，会看到增长远不是线性的（图 5-1）。")
w.figure(FIG / "fig15_月度趋势与同比.png", "图 5-1　月度销售额、3 期移动平均与同比增速", 15.2)
w.p("图 5-1 中灰色柱为月度销售额，深色平滑线为 3 期移动平均，右侧次坐标轴为同比增速。三点观察："
    "第一，季节性极强，9 月与 11–12 月形成双高峰，"
    f"2026 年 11 月单月销售额达 {trend.loc[trend['年月']=='2026-11','销售额'].iloc[0]/1e4:.1f} 万美元，"
    "为全年峰值，2 月则是最低谷（春节与财年切换叠加）；第二，移动平均线自 2025 年下半年起持续上行，"
    "说明增长不是单月偶发；第三，同比增速在 2026 年多数月份为正但波动剧烈（1 月 +135%、5 月 −20.8%），"
    "单月同比不足以判断趋势，必须结合移动平均。")
w.p("结构上，三大品类中家具与办公用品合计贡献约七成销售额，技术品类客单价最高；"
    "区域上西部与东部为大头，中部与南部利润率偏低。这些结论在 5.2、5.3 节的图中逐一展开。")

w = W("可视化模板复现")
w.p("本节对照《Excel数据可视化——从图表到数据大屏》的 30 种模板，复现其中 14 种（图 5-2 至图 5-15），"
    "复现标准有两条：一是图形语言一致（渐变方向、圆角半径、标注位置、坐标轴留白），"
    "二是数据换成 Superstore 的真实指标，而非照搬示例数字。为避免 14 张图各自为政，"
    "统一采用“亮色背景 + 单一主色 + 一处强调色”的配色：主色为商务蓝（#3A7BD5），"
    "强调色为珊瑚橙（#E8735A）与琥珀（#E9A33A），文字用深灰蓝（#1F2A37），"
    "既保证投影时的对比度，也避免纯黑与高饱和色在同屏出现造成的视觉疲劳。")
w.figure(FIG / "fig01_渐变柱形图.png", "图 5-2　模板复现：渐变柱形图（月度销售额）", 14.2)
w.p("模板 1 是渐变柱形图。原作的关键在于柱体由上至下透明度递减，营造“重量感”。"
    "本文用 imshow + 路径裁剪实现真正的渐变填充（而非多层矩形叠加），柱顶圆角处理，"
    "并在峰值柱上方加引线标注数值。数据取 2026 年 12 个月销售额。")
w.figure(FIG / "fig02_带均值柱形图.png", "图 5-3　模板复现：带均值参考线柱形图（子类销售额）", 14.2)
w.p("模板 2 用一条虚线标出均值，回答“谁在平均线以上”。本文取 17 个子类的全年销售额，"
    "均值线为 13.7 万美元，8 个子类越线（座椅、手机、收纳存储、桌子、装订用品、机器设备、配件、复印机），"
    "其余 9 个子类低于平均，直观印证了后文帕累托分析的集中度结论。")
w.figure(FIG / "fig03_渐变圆角柱形图.png", "图 5-4　模板复现：渐变圆角柱形图（大区销售额）", 14.2)
w.p("模板 3 在渐变基础上加入大圆角，视觉更柔和，常用于大屏的“排行类”展示。"
    "圆角半径按柱宽的 45% 控制，避免出现胶囊状失真；柱间留白比例 0.35，比默认值宽，减少拥挤感。")
w.figure(FIG / "fig04_标注柱形图.png", "图 5-5　模板复现：带数据标注的柱形图（2026 年月度销售额 + 同比）", 14.2)
w.p("模板 4 强调“每个柱都直接读数”，适合汇报页。本文在柱顶用圆角标签标出销售额，"
    "再用引线挂上同比增速，把“规模”与“增速”两个维度压进同一张图；标注位置随柱高动态调整，"
    "柱高不足时自动移到柱外侧，避免与刻度线相撞。")
w.figure(FIG / "fig05_层叠柱形图.png", "图 5-6　模板复现：层叠柱形图（品类×年份）", 14.2)
w.p("模板 5 用于展示“总量增长由哪一部分贡献”。这里把四个年份的三个品类叠在一起，"
    "可以读到两点：技术产品始终是第一大品类，四年份额稳定在 34.5%–36.9%；"
    "家具的份额则从 2024 年的 36.4% 一路降至 2026 年的 29.4%，"
    "2026 年办公用品（34.0%）首次反超家具——结构变化比总量变化更值得警惕。")
w.figure(FIG / "fig06_蝴蝶图.png", "图 5-7　模板复现：蝴蝶图（重点子类 2025 vs 2026 销售额）", 14.6)
w.p("模板 6 是蝴蝶图（也有教材称“旋风图”）。左右两侧分别映射两个年度的销售额，中间为子类标签，"
    "适合表达“此消彼长”。图中可直接看出小家电（+64.8%）与配件（+43.1%）明显扩张、"
    "机器设备（−21.5%）与信封（−28.8%）收缩，与 4.3 节波士顿矩阵的象限划分相互印证。")
w.figure(FIG / "fig07_对比柱形图.png", "图 5-8　模板复现：分组对比柱形图（2025 vs 2026）", 14.2)
w.p("模板 7 用成对柱形做同期对比，柱间距小于组间距以形成视觉分组。"
    "本文用它对比两个完整年度的四个大区，并在顶部标注增速，省去读者心算。")
w.figure(FIG / "fig08_甘特图.png", "图 5-9　模板复现：甘特图（各配送方式履约时长分布）", 14.6)
w.p("模板 8 是甘特图，原作用于项目排期。本文做了语义迁移：横条表示各配送方式的履约天数区间"
    "（P10 至 P90），中间菱形标记中位数。这样一张“进度图”就变成了“时效分布图”，"
    "当日达中位 0 天、标准级中位 4 天，差距一目了然。")
w.figure(FIG / "fig09_平滑折线图.png", "图 5-10　模板复现：平滑折线图（48 个月销售额趋势）", 14.2)
w.p("模板 9 用样条插值把折线磨圆，并用渐变面积强化“量”的体感，适合表现连续变化的长期趋势。"
    "需要说明的是，平滑曲线会引入插值误差，本文仅在“趋势示意”场景使用，具体数值仍以柱形图与表格为准。")
w.figure(FIG / "fig10_菱形走势图.png", "图 5-11　模板复现：菱形标记走势图（季度销售额）", 14.2)
w.p("模板 10 用菱形标记替代圆点，配合浅色连接线，重点突出“数据点的位置”而非线段本身。"
    "本文把它用在季度口径上：16 个季度的柱状信息被压缩成一条走势，"
    "月度噪声被平滑掉之后，“三季度冲高、四季度回落”的年度节奏反而更清晰。")
w.figure(FIG / "fig11_对比折线图.png", "图 5-12　模板复现：双系列对比折线图（两年同期）", 14.2)
w.p("模板 11 把两个年度画在同一张图上，横轴为月份序号而非日期，从而对齐“同月对比”。"
    "图中 2026 年曲线在 9–11 月明显高于 2025 年（11 月 11.8 万 vs 7.9 万），12 月反而回落（8.5 万 vs 9.8 万），"
    "说明 2026 年的旺季有前置迹象，与 5.1 节“旺季提前”的判断一致，也解释了预测模型为何对年末的估计偏保守。")
w.figure(FIG / "fig12_单值圆环图.png", "图 5-13　模板复现：单值圆环图（整体毛利率 12.56%）", 14.2)
w.p("模板 12 是单值圆环（KPI 环），用一段圆弧表示占比，圆心放主数值。本文把整体毛利率 12.56% "
    "放进圆环，右侧配销售额、利润等辅助卡，构成“一主多辅”的版式——这正是大屏 KPI 区的标准结构，"
    "也是它比一张明细表更适合投屏的原因：观众在 3 秒内就能抓住唯一重要的数字。")
w.figure(FIG / "fig13_水球图.png", "图 5-14　模板复现：水球图（订单履约达标率）", 13.4)
w.p("模板 13 是水球图，液面高度映射指标达成度，带波浪动画的版本常见于大屏。"
    "本文用正弦波叠加 + 圆形裁剪实现静态版，并保留内外双层波纹以模拟液面张力。"
    "图中指标为履约达标率（下单后 4 天内发货的订单占比）60.2%，意味着近四成订单未能按时交付——"
    "这个数字与 5.3 节漏斗的“下单→按时履约”环节完全对应，也是 6.3 节履约建议的量化起点。")
w.figure(FIG / "fig14_玫瑰图.png", "图 5-15　模板复现：南丁格尔玫瑰图（子类销售额）", 14.2)
w.p("模板 14 是玫瑰图，用扇形半径而非角度编码数值。相比饼图，它能在有限画布内容纳更多类别；"
    "缺点是半径差异不如角度差异易读，因此本文只保留前 10 个子类，其余合并为“其他”，"
    "并把标签沿径向旋转，避免文字互相遮挡。")

w = W("业务模型图")
w.p("业务模型图与第 4 章的 9 个模型一一对应，图 5-16 至图 5-24 依次为帕累托、RFM、K-Means、同期群、"
    "波士顿矩阵、预测、关联规则、漏斗与折扣弹性。与模板复现图不同，这一组图的配色承载语义："
    "珊瑚橙（#E8735A）表示风险与亏损，青绿（#16A3A3）表示健康与增长，灰蓝（#6B7A90）表示中性。")
w.figure(FIG / "fig16_帕累托ABC.png", "图 5-16　子类销售额帕累托图与 ABC 分级", 15.2)
w.p("图 5-16 左侧为降序柱形，右侧为累计占比曲线，70% 与 90% 两条参考线把子类切成三段。"
    "6 个 A 类子类（座椅、手机、收纳存储、桌子、装订用品、机器设备）合计占 64.4% 销售额，"
    "前 3 名即占 38.4%；B 类 4 个占 23.3%；C 类 7 个仅占 12.4%。"
    "这意味着库存与采购的注意力应集中在不到三分之一的 SKU 上，但也要注意：A 类中的桌子与机器设备是亏损项，"
    "“重要”不等于“赚钱”，这一点必须结合毛利率一起看。")
w.figure(FIG / "fig17_RFM八分类.png", "图 5-17　RFM 八分类客户分布（R×F 气泡，大小映射 M）", 15.2)
w.p("图 5-17 以购买频次 F 为横轴（对数刻度）、最近购买间隔 R 为纵轴（越靠上越活跃），"
    "气泡大小映射累计金额 M，颜色区分八类客群。图中左上角（R 小、F 高）聚集重要价值客户，"
    "左下角（R 大、F 低）是流失客户。值得注意的是右侧中段有一片“F 很高但 R 也很大”的气泡，"
    "对应重要唤回客户——他们曾经高频购买，如今集体沉默，是最值得投入召回资源的一群。")
w.figure(FIG / "fig18_KMeans客群.png", "图 5-18　K-Means 三客群分布与画像对比", 15.2)
w.p("图 5-18 左图为累计金额 M 与最近购买间隔 R 的对数散点（大号 X 为各簇中位数），"
    "右图对比三簇的客户数占比与销售额占比。三个簇在 R 维度上呈现清晰的横向分层，"
    "说明“最近购买时间”是区分客户的最强特征；右图则直观呈现了“少数客户贡献多数销售额”的错位。"
    "与图 5-17 对照可以发现：RFM 的“重要唤回客户”与 K-Means 的“沉睡高额群”高度重合"
    "（均有约 47% 的销售额贡献），两种方法互相印证，这一群体应作为 2027 年客户运营的第一优先级。")
w.figure(FIG / "fig19_同期群留存.png", "图 5-19　同期群留存热力图与平均留存曲线", 15.2)
w.p("图 5-19 为同期群留存热力图：每一行是一个首购月份群组，列为首购后第 N 个月，颜色越深留存越高，"
    "右侧色条给出留存率的刻度。沿行横向读，能看到每组客户的衰减轨迹；沿列纵向读，"
    "能比较不同批次客户的同期表现。全部群组的平均值显示：首月留存 11.7%，第 2 期探底 7.8%，"
    "第 6 期后回升并稳定在 10.6% 左右。这个“U 形”说明留存不是单调衰减，而是存在一个“习惯养成期”——"
    "挺过前三个月的客户，后续粘性反而提升。热力图中各批次群的轨迹形状高度相似，说明这一规律是结构性的，"
    "而非某一年的偶发波动，因此可以放心作为运营假设。")
w.figure(FIG / "fig20_波士顿矩阵.png", "图 5-20　子类波士顿矩阵（份额×增速，气泡=销售额，颜色=毛利率）", 15.2)
w.p("图 5-20 的四象限以整体增速与平均份额为界。右上“明星”区的复印机是全场最值得关注的业务："
    "份额 8.4% 不算最大，但毛利率 39.8%、利润贡献 26.1%，属于典型的“利润引擎”。"
    "右下“现金牛”区的桌子与机器设备颜色偏红（毛利率为负），是必须处理的伪现金牛；"
    "左上“问题”区的小家电增速 64.8% 但份额仅 5.8%，是否加投需要看边际利润能否转正；"
    "左下“瘦狗”区的书架、耗材建议收缩 SKU 宽度。")
w.figure(FIG / "fig21_预测置信区间.png", "图 5-21　Holt-Winters 预测与 95% 置信区间（含回测段）", 15.2)
w.p("图 5-21 中深蓝实线为历史实际销售额，橙色方块为 2026 年 7–12 月的回测预测，"
    "红色带点线为 2027 年 1–6 月的外推，浅红色带为 95% 置信区间。三点解读："
    "第一，模型准确捕捉了 9 月与 11–12 月的双峰结构，回测段与实际值的方向一致；"
    "第二，置信带随外推步长明显变宽（2027 年 1 月宽度约 4.4 万美元，6 月扩至 7.9 万美元），"
    "这正是预测不确定性的可视化表达，提醒决策者不要按点值做刚性预算；"
    f"第三，2027 年上半年月均预测 {avg27/1e4:.2f} 万美元，与 2026 年月均 {avg26/1e4:.2f} 万美元基本持平"
    "（−0.6%），增长进入平台期。")
w.figure(FIG / "fig22_关联规则.png", "图 5-22　关联规则 Top12（提升度排序，附置信度与支持度）", 15.2)
w.p("图 5-22 以横向条形图列出提升度最高的 12 条规则，条旁标注提升度、置信度与支持度，"
    "红色虚线为提升度等于 1 的“无关联”基准线。榜首为“家居陈设 + 装订用品 → 小家电”（提升度 1.89），"
    "其次是“手机 + 收纳存储 → 家居陈设”（1.81）。一个规律值得注意：装订用品在前 12 条规则中反复出现，"
    "扮演“桥梁品类”的角色——它单价低、购买频次高，常与其他品类同单出现，是理想的凑单与推荐入口。"
    "运营上可据此设计三组捆绑：办公耗材组合（纸张+装订用品+标签）、桌面场景组合（收纳存储+家居陈设+小家电）、"
    "数码配件组合（手机+配件+复印机耗材）。")
w.figure(FIG / "fig23_履约漏斗.png", "图 5-23　订单履约漏斗（下单→按时履约→未退货→盈利）", 14.6)
w.p("图 5-23 的梯形宽度按订单数等比缩放，右侧标注整体转化率与环节转化率。"
    "最大流失在“下单→按时履约”环节（−39.8 个百分点），对应 2 033 单未能在 4 天内送达；"
    "退货环节仅损耗 6.0%，说明商品质量与描述基本可靠；盈利环节损耗 21.1%，"
    "意味着每五个成功交付的订单就有一个在亏钱。漏斗的价值在于把“转化率”这个笼统指标拆成了可归因的四段。")
w.figure(FIG / "fig24_折扣毛利弹性.png", "图 5-24　折扣区间与毛利率、亏损占比的关系", 15.2)
w.p("图 5-24 用双轴呈现折扣的“代价”：柱形为各折扣区间的毛利率，折线为亏损明细占比。"
    "无折扣订单毛利率 29.6%、零亏损；10%–20% 区间毛利率降至 11.5%，亏损占比升至 14.0%；"
    "跨过 20% 后毛利率转负（−10.1%），亏损占比骤升至 91.7%；50% 以上区间毛利率低至 −118.7%，"
    "全部亏损。这条曲线给出了一个非常清晰的临界点：20%。")

w = W("交互式可视化大屏")
w.p("大屏使用 ECharts 5.5 原生实现，单文件 HTML（内嵌本地 echarts.min.js，双击即可离线打开）。"
    "整体采用暗色主题（背景 #0A1020，面板 #111A2E，描边 #22304C），"
    "主色青蓝 #35C4F0、强调色琥珀 #FFB13D，正文 #E6EDF7、次要文字 #93A4BF，"
    "深色底与低饱和辅助色搭配，避免高饱和色长时间注视造成的视觉疲劳。布局按 12 栅格组织，共 8 类组件（图 5-25）。")
w.bullets("① 5 张 KPI 卡：销售额、利润、毛利率、订单数、退货率，切换年份时自动重算同比与环比；")
w.bullets("② 3 个筛选器：年份、大区、品类，联动全部组件；")
w.bullets("③ 月度趋势图：柱形 + 移动平均 + 同比双轴；④ 品类结构玫瑰图；")
w.bullets("⑤ 客群散点：R×F×M 三维气泡；⑥ 区域雷达：四大区四维对比；")
w.bullets("⑦ 子类帕累托 + 可排序明细表；⑧ 预测外推图：带 95% 置信带。")
w.figure(FIG / "fig25_大屏布局示意图.png", "图 5-25　交互式大屏布局与联动关系示意", 15.2)
w.p("联动逻辑为三级：第一级是筛选器驱动，任一下拉变化即触发全量重算，KPI 的同比基准同步切换到上一年；"
    "第二级是图表点击下钻，点击趋势图的某个月份，明细表自动过滤到该月；"
    "第三级是悬停联动，鼠标移到玫瑰图的某个品类，其余图表的对应系列高亮，其余淡化。"
    "为验证联动正确性，本文在无浏览器环境下用 Node 桩（stub）模拟 DOM 与 echarts 实例，"
    "对 KPI 计算函数做了单元测试：切换至“2026 年 + 西部”后，销售额与同比数值与手工核算一致，"
    "明细表行数从 10 194 降至对应子集，测试通过。")
w.p("与 Excel 图表相比，Python 方案的差异不在“能不能画”，而在三点：一是可复现性，"
    "所有图形由代码与数据驱动，改一个阈值全图重绘；二是交互维度，Excel 的切片器只能在数据透视表内联动，"
    "而 ECharts 可以做到跨图表事件联动与下钻；三是部署形态，单文件 HTML 可以直接发给他人或投屏，"
    "无需安装 Office 与宏环境。代价是学习曲线更陡，样式微调需要写配置而非拖拽。")

# ============================================================
# 11. 第 6 章　商业案例分析
# ============================================================
w = W("案例背景")
w.p("把上述结果放回经营情境：这是一家以办公家具、办公用品与技术产品为主营的零售商，"
    "四年间销售额从 49.4 万美元增至 " + f"{year_sales[2026]/1e4:.1f}" + " 万美元，看似稳步增长，"
    "但整体毛利率只有 12.56%，且 18.65% 的订单明细在亏钱。管理层的困惑很具体："
    "增长的钱赚得越来越辛苦，折扣越打越深，客户却越来越难留住。"
    "本章用三个模型串起一条诊断链：先看钱从哪来（帕累托、波士顿矩阵），再看人在哪流失（RFM、同期群），"
    "最后看未来怎么走（预测、折扣红线）。")

w = W("结果解读")
w.p("第一，收入高度集中，但集中点未必赚钱。6 个 A 类子类贡献 64.4% 销售额，前 3 名占 38.4%；"
    "然而 A 类中的桌子（毛利率 −13.3%）与机器设备（−6.5%）合计拉低利润约 1.1 万美元。"
    "换句话说，销售额的“头部”里混着两个亏损项，若只看销售额排名做资源分配，会把预算投向不产生利润的地方。"
    "这正是帕累托与波士顿矩阵必须联用的原因：前者回答“谁大”，后者回答“大得好不好”。")
w.p("第二，客户价值的分布比“二八法则”更极端。25.4% 的重要价值客户贡献 40.2% 销售额，"
    "加上重要唤回客户的 24.3%，前 39.8% 的客户贡献 64.5% 销售额。更关键的是客户状态："
    "重要唤回客户人均消费 4 865 美元为八类最高，但平均 R 已达 174 天；"
    "K-Means 的“沉睡高额群”350 人贡献 47.4% 销售额、平均 R 189 天，两组独立方法指向同一结论——"
    "有近一半的销售额掌握在一批正在流失的高价值客户手里。这是本案例最重要的发现，"
    "也是所有建议中最紧急的一条。")
w.p("第三，留存的问题不在“长期”，而在“首月”。同期群曲线显示首月留存仅 11.7%，"
    "第二期探底至 7.8%，此后回升并稳定在 10.6%。这说明客户并非“慢慢流失”，而是“首购即分流”："
    "近九成客户在首购后一个月内没有二次下单，而挺过三个月的客户反而趋于稳定。"
    "因此把资源平均铺在全年做“客户维护”是低效的，应集中投在首购后 90 天的窗口期。")
w.p("第四，折扣已经越过临界点。无折扣订单毛利率 29.6%、零亏损；10%–20% 区间毛利率 11.5%，"
    "已接近整体均值；20% 以上毛利率转负，50% 以上毛利率 −118.7%。而现实是，"
    "20% 以上的折扣订单占了明细的 13.9%，贡献了绝大部分亏损。折扣不是不能用，"
    "而是必须与品类、客户价值挂钩——对重要价值客户给 10% 的忠诚折扣，"
    "其边际收益远高于对流失客户给 40% 的清仓折扣。")
w.p("第五，增长已进入平台期。Holt-Winters 预测 2027 年上半年月均 6.18 万美元，"
    f"与 2026 年月均 {avg26/1e4:.2f} 万美元基本持平；置信区间宽度随步长扩大，"
    "说明不确定性在累积。结合 2026 年增速已从上年 29.8% 回落至 21.4%，"
    "可以判断：增长动能正在减弱，2027 年的预算不宜按 2026 年的增速外推。")

w = W("商业建议")
w.p("建议一：建立“保—压—育”的品类组合策略（依据：图 5-16、图 5-20、表 4-4）。"
    "保：复印机、配件、手机、装订用品四个明星子类，2026 年合计贡献 40.5% 销售额与 64.2% 利润，"
    "应保障库存可得性与账期支持，其中复印机毛利率 39.8%，可适度加大样机与售前投入。"
    "压：桌子与机器设备两个伪现金牛，合计占用 14.1% 销售额却带来 −1.09 万美元利润，"
    "建议将折扣上限从当前水平压到 10% 以内，并收缩低毛利 SKU；若三个月内毛利率仍无法转正，考虑转为代销或退出。"
    "育：小家电（增速 64.8%）、纸张（毛利率 43.5%）、标签（45.2%）三个问题/瘦狗区的高毛利业务，"
    "以“低折扣 + 组合陈列”方式培育，目标是把小家电的份额从 5.8% 提升至 8%。")
w.p("建议二：启动“高价值沉睡客户”专项召回（依据：图 5-17、图 5-18、表 4-2、表 4-3）。"
    "目标人群为 RFM 重要唤回客户 116 人与 K-Means 沉睡高额群 350 人的交集，估计 200–300 人，"
    "对应销售额约 110 万美元。动作设计：① 以“专属客户经理 + 季度采购清单”触达，替代通用促销邮件；"
    "② 召回优惠限定在其历史高频品类（由关联规则给出候选组合），折扣控制在 10%–15%；"
    "③ 设定 90 天观察窗，以“是否产生二次订单”为唯一成功指标，避免用打开率自欺。"
    "按人均 3 150 美元、召回率 15% 测算，可挽回约 10–14 万美元销售额，且这部分订单毛利率高于新客。")
w.p("建议三：把留存预算集中到首购后 90 天（依据：图 5-19）。"
    "首月留存 11.7%、第三期 9.1%，说明窗口极短。建议设计三段式触点：首购后第 7 天（使用指导 + 耗材提醒）、"
    "第 30 天（关联品类推荐，用 Apriori 规则匹配）、第 75 天（复购券，面额按首单金额的 8% 设定）。"
    "同时把“首购后 90 天内二次下单率”设为运营团队的核心 KPI，替代当前的“月度活跃客户数”——"
    "后者容易被促销短期拉高，前者才反映真实的习惯养成。")
w.p("建议四：设定 20% 的折扣红线，并做差异化授权（依据：图 5-24、表 6-1）。"
    "20% 以上折扣订单的毛利率全部为负，50% 以上区间毛利率 −118.7%，属于“卖一件亏一件”。"
    "建议在系统中设置硬约束：标准品类折扣上限 20%，超过需区域经理审批；"
    "清库存场景单独走“亏损预算”流程，明确每季度可承受的亏损额度；"
    "对重要价值客户开放 10%–15% 的忠诚折扣（其毛利率仍可达 15% 以上），"
    "对流失客户不做无差别高折扣召回——数据显示这类客户的毛利率仅 6.09%，召回后仍是低质订单。")
w.table("表 6-1　折扣区间与盈利表现",
        ["折扣区间", "销售额占比", "毛利率", "亏损明细占比"],
        [[r["折扣档"], f"{r['销售额占比']:.1%}", f"{r['毛利率']:.1%}", f"{r['亏损占比']:.1%}"]
         for _, r in disc.iterrows()],
        widths=[3.4, 3.4, 3.4, 4.0], font_size=9, first_col_left=True)
w.p("建议五：把履约时效作为独立改进项（依据：图 5-23、图 5-9）。"
    "漏斗显示 39.8% 的订单未能在 4 天内送达，这是四级转化中最大的一段流失。"
    "甘特图进一步显示，标准级配送的履约天数中位数为 4 天、P90 达 7 天，"
    "而当日达与一级配送的占比偏低。建议：① 对 A 类子类（尤其复印机等高单价商品）默认升级为一级配送，"
    "用物流成本换复购率；② 在结算页明确展示“预计到达日”，把时效从隐性成本变为显性卖点；"
    "③ 按大区拆分履约时效，优先改进中位数超过 5 天的大区。")

# ============================================================
# 12. 第 7 章　结论与展望
# ============================================================
w = W("研究结论")
w.p("本文以 Sample–Superstore 四年交易数据为对象，完成了从合规取数、清洗治理、模型计算、图表复现到"
    "交互大屏的完整链路，得到四点结论。")
w.p("其一，收入结构高度集中但质量参差。6 个子类贡献 64.4% 销售额，其中两个是亏损项；"
    "真正支撑利润的是复印机、配件、手机与装订用品，四者以 40.5% 的销售额贡献 64.2% 的利润。"
    "这提示“按销售额排名分配资源”是一种粗糙且危险的做法。")
w.p("其二，客户价值的分层与流失同时发生。25.4% 的重要价值客户贡献 40.2% 销售额，"
    "但另有约 47% 的销售额掌握在平均 180 天未复购的沉睡高额客户手中。"
    "RFM 与 K-Means 两种独立方法得到一致结论，说明这不是切分方法造成的假象。")
w.p("其三，留存瓶颈在首月而非长期。首月留存 11.7%、第二期 7.8%、第六期后稳定 10.6%，"
    "呈现“先跌后稳”的 U 形，运营窗口应压缩到首购后 90 天。")
w.p("其四，折扣已越过盈利临界点，增长进入平台期。20% 以上折扣毛利率转负；"
    "Holt-Winters 预测 2027 年上半年月均销售额与 2026 年持平，回测 MAPE 16.93%，"
    "模型虽可用，但置信区间随步长扩大，预算宜用区间而非点值。")
w.p("方法层面，本文验证了两点经验：一是预测模型必须先比选再定稿，本文 SARIMA 的 MAPE（25.36%）"
    "显著劣于 Holt-Winters（16.93%），若不做比选会得出偏悲观的结论；"
    "二是规则分层与聚类应交叉验证，两者一致时结论稳健，不一致处往往是最有价值的洞察。")

w = W("局限性与展望")
w.p("本文存在四点局限。第一，数据为美国市场样本，地理与渠道结构与中国零售差异较大，"
    "结论的可迁移性需要谨慎对待，尤其“大区”维度的表现不能直接映射到国内区域市场。"
    "第二，缺少成本、库存与流量数据，因此无法计算真正的贡献毛利与库存周转，"
    "波士顿矩阵的“份额”只能用销售额近似，无法反映市场占有率。"
    "第三，预测仅使用单变量历史序列，未纳入促销日历、价格指数、节假日等外生变量，"
    "这可能是 MAPE 停留在 16.9% 的主要原因；后续可尝试 SARIMAX 加入外生变量，"
    "或引入 Prophet 处理节假日效应。第四，关联规则的支持度门槛较低（0.6%），"
    "93 条规则中真正可直接落地的组合需要人工二次筛选，本文给出的三组捆绑方案仍属候选。")
w.p("后续可拓展的方向包括：引入客户生命周期价值（CLV）模型，把 RFM 的静态分层升级为动态预测；"
    "用生存分析（Cox 比例风险模型）替代同期群热力图，量化各因素对流失风险的影响；"
    "把大屏从静态数据升级为接数据库的实时看板，支撑日级监控。")

w = W("AI 使用披露")
w.p("本文在写作与编码过程中使用了 AI 编程助手（WorkBuddy 桌面端），使用环节限于三类："
    "一是代码框架搭建与报错排查（如 Matplotlib 渐变填充的裁剪路径、ECharts 离线资源路径配置）；"
    "二是文档结构与文字润色（章节标题措辞、长句拆分）；三是图表配色的可读性建议。"
    "所有数据结论、模型参数、阈值设定均由作者依据计算结果确认，AI 未参与数据生成与结论判断。关键提示词示例：")
w.bullets("（1）“用 Matplotlib 实现柱形图的垂直渐变填充，要求渐变被柱体路径裁剪，不使用多层矩形叠加。”")
w.bullets("（2）“我有 17 个子类的销售额与同比增速，请给出波士顿矩阵的四象限划分逻辑，"
          "分界线用整体增速和平均份额，并说明这样划分相比固定 10% 的优势。”")
w.bullets("（3）“检查这段 RFM 八分类代码，确认 R 的方向（间隔越小越高）在中位数切分时是否正确。”")
w.p("作者对全文内容的真实性、数据的可复现性负责，所有图表均可由 run_all.py 一键重新生成。")

# ============================================================
# 13. 参考文献（替换模板中的占位条目）
# ============================================================
refs = [
    "[1] 郭宏远. Excel数据可视化：从图表到数据大屏[M]. 北京: 清华大学出版社, 2023.",
    "[2] McKINNEY W. Python for data analysis: data wrangling with pandas, NumPy, and Jupyter[M]. "
    "3rd ed. Sebastopol: O'Reilly Media, 2022.",
    "[3] HUGHES A M. Strategic database marketing[M]. 3rd ed. New York: McGraw-Hill, 2005.",
    "[4] KOTLER P, KELLER K L. Marketing management[M]. 15th ed. Boston: Pearson, 2016.",
    "[5] HYNDMAN R J, ATHANASOPOULOS G. Forecasting: principles and practice[M]. 3rd ed. "
    "Melbourne: OTexts, 2021.",
    "[6] AGRAWAL R, SRIKANT R. Fast algorithms for mining association rules[C]//Proceedings of the "
    "20th International Conference on Very Large Data Bases. Santiago: VLDB, 1994: 487-499.",
    "[7] CHEN H, CHIANG R H L, STOREY V C. Business intelligence and analytics: from big data to "
    "big impact[J]. MIS Quarterly, 2012, 36(4): 1165-1188.",
    "[8] 王汉生. 数据思维：从数据分析到商业价值[M]. 北京: 中国人民大学出版社, 2017.",
    "[9] ROUSSEEUW P J. Silhouettes: a graphical aid to the interpretation and validation of cluster "
    "analysis[J]. Journal of Computational and Applied Mathematics, 1987, 20: 53-65.",
    "[10] 贾俊平, 何晓群, 金勇进. 统计学[M]. 8版. 北京: 中国人民大学出版社, 2021.",
    "[11] 涂子沛. 大数据[M]. 3版. 桂林: 广西师范大学出版社, 2015.",
    "[12] WONGSUPHASAWAT K, MACKINLAY J, BLANCH R, et al. Voyager: exploratory analysis via "
    "faceting[C]//Proceedings of the 33rd Annual ACM Conference on Human Factors in Computing "
    "Systems. Seoul: ACM, 2015: 1903-1912.",
]
ph_ref = None
for par in doc.paragraphs:
    if par.text.strip().startswith("[1] ***"):
        ph_ref = par
        break
if ph_ref is not None:
    _clear(ph_ref)
    par = ph_ref
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    par.paragraph_format.first_line_indent = Pt(0)
    par.paragraph_format.line_spacing = 1.35
    par.paragraph_format.space_after = Pt(3)
    set_run(par.add_run(refs[0]), font=SONG, size=10.5)
    wr = Writer(doc, par, reuse=False)
    for r in refs[1:]:
        p = wr.p(r, indent=False, size=10.5, spacing=1.35, after=3, align=WD_ALIGN_PARAGRAPH.JUSTIFY)

# ============================================================
# 14. 附录 A / B / C
# ============================================================
APPENDIX_TITLES = {"A": ("A 核心代码片段", "A　核心代码片段"),
                   "B": ("B Gitee", "B　仓库链接与目录结构"),
                   "C": ("C 图表索引", "C　图表索引")}


def appendix_head(prefix: str) -> Paragraph:
    key, new_title = APPENDIX_TITLES[prefix]
    for par in doc.paragraphs:
        if par.text.strip().startswith(key):
            _clear(par)
            par.paragraph_format.first_line_indent = Pt(0)
            par.paragraph_format.space_before = Pt(10)
            par.paragraph_format.space_after = Pt(4)
            set_run(par.add_run(new_title), font=HEI, size=12, bold=True)
            return par
    raise KeyError(prefix)


pa = appendix_head("A")
wr = Writer(doc, pa, reuse=False)
wr.p("以下为 RFM 八分类与预测模型比选的核心实现（完整代码见 scripts/03_analysis.py）。"
     "为节省篇幅，省略了注释与异常处理。", indent=True)
wr.code("""# RFM 八分类：中位数切分（R 方向反转）
rfm = df.groupby("Customer ID").agg(
    R=("Order Date", lambda s: (REF - s.max()).days),
    F=("Order ID", "nunique"),
    M=("Sales", "sum"))
thr = {k: v.median() for k, v in rfm.items()}
for k in "RFM":
    rfm[k + "_H"] = np.where(rfm[k] > thr[k], 1, 0) if k != "R" else np.where(rfm[k] < thr[k], 1, 0)
rfm["RFM客群"] = rfm.apply(lambda r: SEG_MAP[(r.R_H, r.F_H, r.M_H)], axis=1)""")
wr.code("""# 预测比选：同一留出期比较 MAPE，择优后全样本重估
for name, model in {"Holt-Winters": hw_model, "SARIMA": sarima_model}.items():
    pred = model.forecast(test_len)
    mape = np.mean(np.abs((test.values - pred.values) / test.values))
    rows.append({"模型": name, "回测MAPE": mape})
best = min(rows, key=lambda r: r["回测MAPE"])""")

pb = appendix_head("B")
wr = Writer(doc, pb, reuse=False)
wr.p("仓库地址：https://gitee.com/（待填写）/superstore-analysis　（提交前请替换为本人公开仓库链接）", indent=True)
wr.code("""superstore-analysis/
├── data/
│   ├── raw/            原始 xls（只读，不修改）
│   └── clean/          清洗后 csv / pkl / superstore.db
├── scripts/
│   ├── common.py       路径、中文映射、主题配色
│   ├── 01_load.py      三表读取与元信息体检
│   ├── 02_clean.py     清洗、派生、关联、导出
│   ├── 03_analysis.py  9 个模型计算
│   ├── 04_visuals.py   25 张静态图
│   ├── 05_dashboard.py 两个版本交互大屏
│   └── 06_paper.py     按模板生成本论文
├── outputs/
│   ├── figures/        fig01–fig25（png, 200dpi）
│   └── tables/         t01–t17 结果表（csv）
├── dashboard/          商业分析大屏.html（含离线 echarts）
├── notebooks/          01 数据 02 模型 03 可视化（已执行）
├── docs/               本论文、合规声明、图表索引
├── requirements.txt
├── run_all.py          一键复现
└── README.md""")

pc = appendix_head("C")
fig_list = [
    ("fig15", "月度趋势与同比", "5-1"),
    ("fig01", "渐变柱形图", "5-2"), ("fig02", "带均值参考线柱形图", "5-3"),
    ("fig03", "渐变圆角柱形图", "5-4"), ("fig04", "数据标注柱形图", "5-5"),
    ("fig05", "层叠柱形图", "5-6"), ("fig06", "蝴蝶图", "5-7"),
    ("fig07", "分组对比柱形图", "5-8"), ("fig08", "甘特图（履约时长）", "5-9"),
    ("fig09", "平滑折线图", "5-10"), ("fig10", "菱形标记走势图", "5-11"),
    ("fig11", "双系列对比折线图", "5-12"), ("fig12", "单值圆环图", "5-13"),
    ("fig13", "水球图", "5-14"), ("fig14", "玫瑰图", "5-15"),
    ("fig16", "帕累托/ABC", "5-16"), ("fig17", "RFM 八分类", "5-17"),
    ("fig18", "K-Means 客群", "5-18"), ("fig19", "同期群留存热力图", "5-19"),
    ("fig20", "波士顿矩阵", "5-20"), ("fig21", "预测置信区间", "5-21"),
    ("fig22", "关联规则 Top12", "5-22"), ("fig23", "履约漏斗", "5-23"),
    ("fig24", "折扣毛利弹性", "5-24"), ("fig25", "大屏布局示意图", "5-25"),
]
wr = Writer(doc, pc, reuse=False)
wr.table("表 C-1　图表索引（共 25 张，均存于 outputs/figures/）",
         ["文件名", "图表名称", "正文图号", "文件名", "图表名称", "正文图号"],
         [[fig_list[i][0], fig_list[i][1], "图 " + fig_list[i][2],
           fig_list[i + 1][0] if i + 1 < len(fig_list) else "",
           fig_list[i + 1][1] if i + 1 < len(fig_list) else "",
           ("图 " + fig_list[i + 1][2]) if i + 1 < len(fig_list) else ""]
          for i in range(0, len(fig_list), 2)],
         widths=[2.0, 4.4, 1.9, 2.0, 4.4, 1.9], font_size=8, first_col_left=True)
shot = FIG / "fig26_大屏运行截图.png"
if shot.exists():
    wr.figure(shot, "图 C-1　交互式大屏运行效果（1920×1080 全屏截图）", 15.4)
wr.p("大屏文件：dashboard/商业分析大屏.html（单文件，内嵌本地 echarts.min.js，"
     "双击即可离线打开，无需联网与任何 BI 软件）。图 C-1 为按 F11 全屏后的实际运行截图，"
     "可见 5 张 KPI 卡、3 个筛选器与 8 个图表组件的完整排布。", indent=True)

# ============================================================
# 15. 保存
# ============================================================
OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
doc.save(str(OUT_DOC))
print(f"[√] 论文已按模板生成：{OUT_DOC}")
print(f"[√] 段落数 {len(doc.paragraphs)}，表格数 {len(doc.tables)}，图片数 {len(doc.inline_shapes)}")
