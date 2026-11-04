"""
05_dashboard.py —— 暗色系交互式商业分析大屏（单文件 HTML，全 Python 生成）
--------------------------------------------------------------------------------
本文件职责：
  1) 从 outputs/tables 与清洗后宽表读取分析结果，压缩为前端可直接消费的 JSON；
  2) 用模板化 HTML + CSS + ECharts 生成一张 1920×1080 的暗色数据大屏；
     —— 图表配置由 Python 端统一组织（配色、坐标轴、提示框全部中文化）；
     —— 组件共 8 个图表 + 5 个 KPI 卡 + 3 个筛选器 + 1 张明细表；
  3) 实现真正的联动：切换「年份 / 大区 / 品类」筛选器时，
     KPI 卡、趋势、结构、大区、帕累托、明细表全部重算；点击结构环或大区柱可下钻。

技术说明：不依赖任何 BI 软件（未使用 Tableau/Power BI/FineBI）；
         ECharts 静态库随项目放在 dashboard/echarts.min.js，双击 HTML 即可离线查看。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from common import DASH_DIR, OUT_TAB, ROOT

MAIN_JS = DASH_DIR / "echarts.min.js"


# ============================================================
# 1. 数据准备
# ============================================================
def load_data() -> dict[str, pd.DataFrame]:
    """读取清洗宽表与各模型结果表。"""
    orders = pd.read_pickle(ROOT / "data" / "clean" / "orders_clean.pkl")
    orders["Order Date"] = pd.to_datetime(orders["Order Date"])
    tabs = {
        "trend": pd.read_csv(OUT_TAB / "t06_月度趋势_同比环比.csv"),
        "rfm": pd.read_csv(OUT_TAB / "t08_RFM客户明细.csv"),
        "cohort": pd.read_csv(OUT_TAB / "t11_同期群留存矩阵.csv"),
        "bcg": pd.read_csv(OUT_TAB / "t12_波士顿矩阵.csv"),
        "fc": pd.read_csv(OUT_TAB / "t13_预测结果.csv"),
        "bt": pd.read_csv(OUT_TAB / "t13b_预测回测明细.csv"),
        "disc": pd.read_csv(OUT_TAB / "t17_折扣弹性.csv"),
        "kpi": pd.read_csv(OUT_TAB / "t02_数据规模指标.csv"),
        "pareto_sub": pd.read_csv(OUT_TAB / "t07_帕累托_ABC_子类.csv"),
    }
    return {"orders": orders, **tabs}


def build_datasets(d: dict) -> dict:
    """把宽表压缩成前端友好的紧凑数组（体积小、前端聚合快）。"""
    o = d["orders"]

    # ---------- 主数据集：年 × 月 × 大区 × 品类 ----------
    g = (o.groupby(["年份", "月份", "大区", "品类"])
         .agg(销售额=("Sales", "sum"), 利润=("Profit", "sum"),
              订单数=("Order ID", "nunique"), 销量=("Quantity", "sum"))
         .reset_index())
    ret = (o[o["是否退货"] == 1].groupby(["年份", "月份", "大区", "品类"])["Order ID"]
           .nunique().rename("退货数").reset_index())
    g = g.merge(ret, on=["年份", "月份", "大区", "品类"], how="left").fillna({"退货数": 0})
    main = [[int(r.年份), int(r.月份), r.大区, r.品类,
             round(float(r.销售额), 1), round(float(r.利润), 1),
             int(r.订单数), int(r.退货数), int(r.销量)]
            for r in g.itertuples()]

    # ---------- 订单级数据集：年 × 月 × 大区 × 品类位掩码（用于精确去重计数）----------
    # 说明：订单可能跨品类，直接按品类分组求和会重复计数；
    #       故单独给出订单级记录，用「品类位掩码」cbit 支持任意筛选下的精确去重。
    cat_list = ["办公用品", "家具", "技术产品"]
    flag = (o.groupby(["Order ID", "品类"]).size().unstack(fill_value=0) > 0)
    cbit = flag.apply(lambda r: sum((1 << i) for i, c in enumerate(cat_list) if r.get(c, False)),
                      axis=1).rename("cbit")
    od = (o.groupby("Order ID")
          .agg(y=("年份", "first"), m=("月份", "first"), r=("大区", "first"),
               s=("Sales", "sum"), p=("Profit", "sum"), ret=("是否退货", "max"))
          .join(cbit).reset_index())
    ords = [[int(x.y), int(x.m), x.r, int(x.cbit), int(x.ret)] for x in od.itertuples()]

    # ---------- 子类数据集：年 × 大区 × 品类 × 子类（用于帕累托与明细表）----------
    sg = (o.groupby(["年份", "大区", "品类", "子类"])
          .agg(销售额=("Sales", "sum"), 利润=("Profit", "sum"), 销量=("Quantity", "sum"))
          .reset_index())
    sub = [[int(r.年份), r.大区, r.品类, r.子类, round(float(r.销售额), 1),
            round(float(r.利润), 1), int(r.销量)] for r in sg.itertuples()]

    # ---------- RFM 散点：F、R、M、客群序号 ----------
    seg_order = ["重要价值客户", "重要唤回客户", "重要深耕客户", "重要挽留客户",
                 "一般保持客户", "一般发展客户", "潜力新客", "流失客户"]
    rfm = d["rfm"].copy()
    rfm["seg_i"] = rfm["RFM客群"].apply(lambda x: seg_order.index(x) if x in seg_order else 7)
    rfm_pts = [[round(float(r.F值), 2), round(float(r.R值), 1), round(float(r.M值), 1),
                int(r.seg_i)] for r in rfm.itertuples()]
    seg_count = [int((rfm["seg_i"] == i).sum()) for i in range(8)]

    # ---------- 同期群热力图 ----------
    co = d["cohort"].copy()
    cohorts = co["首购月"].astype(str).tolist()
    periods = [int(c.replace("第", "").replace("期", "")) for c in co.columns if c.startswith("第")]
    cells = []
    for i, row in co.iterrows():
        for j, p in enumerate(periods):
            v = row.get(f"第{p}期")
            if pd.notna(v):
                cells.append([j, i, round(float(v) * 100, 1)])

    # ---------- 折扣弹性 ----------
    dc = d["disc"].dropna(subset=["折扣档"])
    disc = {"labels": dc["折扣档"].astype(str).tolist(),
            "margin": [round(float(v) * 100, 2) for v in dc["毛利率"]],
            "loss": [round(float(v) * 100, 1) for v in dc["亏损占比"]],
            "share": [round(float(v) * 100, 1) for v in dc["销售额占比"]]}

    # ---------- 预测（历史近 24 期 + 未来 6 期 + 95% 区间）----------
    tr = d["trend"].tail(24)
    fc = d["fc"]
    forecast = {
        "hist_x": tr["年月"].tolist(),
        "hist_y": [round(float(v), 1) for v in tr["销售额"]],
        "fc_x": fc["年月"].tolist(),
        "fc_y": [round(float(v), 1) for v in fc["预测销售额"]],
        "lo": [round(float(v), 1) for v in fc["下限95"]],
        "hi": [round(float(v), 1) for v in fc["上限95"]],
        "mape": 0.1693,
    }
    # 从评估表读取真实 MAPE，避免硬编码
    try:
        m = pd.read_csv(OUT_TAB / "t14_预测评估指标.csv")
        forecast["mape"] = float(str(m.loc[m["指标"] == "MAPE（回测）", "取值"].iloc[0])
                                 .replace("%", "")) / 100
        forecast["model"] = str(m.loc[m["指标"] == "最终模型", "取值"].iloc[0])
    except Exception:
        forecast["model"] = "Holt-Winters"

    return {"main": main, "orders": ords, "sub": sub, "rfm": rfm_pts,
            "seg_count": seg_count,
            "seg_names": seg_order, "cohort": {"cohorts": cohorts, "periods": periods,
                                               "cells": cells},
            "disc": disc, "forecast": forecast,
            "years": sorted(o["年份"].unique().tolist()),
            "regions": ["东部", "西部", "中部", "南部"],
            "cats": ["办公用品", "家具", "技术产品"]}


# ============================================================
# 2. HTML 模板（暗色大屏）
# ============================================================
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Sample-Superstore 商业分析数据驾驶舱</title>
<style>
  :root{
    --bg:#0A1020; --panel:#111A2E; --panel2:#16223A; --line:#22304C;
    --text:#E6EDF7; --sub:#93A4BF; --cyan:#35C4F0; --amber:#FFB13D;
    --coral:#FF6B6B; --violet:#8B7CF6; --green:#35D0A5; --pink:#F06CA8;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--text);
    font-family:"Microsoft YaHei","微软雅黑",system-ui,sans-serif;
    background-image:radial-gradient(1200px 600px at 15% -10%,#142749 0%,rgba(10,16,32,0) 60%),
                     radial-gradient(900px 500px at 90% 0%,#122a3a 0%,rgba(10,16,32,0) 55%);}
  .top{display:flex;justify-content:space-between;align-items:flex-end;
    padding:16px 24px 10px;border-bottom:1px solid var(--line)}
  .title{font-size:25px;font-weight:700;letter-spacing:2px;
    background:linear-gradient(90deg,#7FD8FF,#E6EDF7 60%);-webkit-background-clip:text;
    -webkit-text-fill-color:transparent}
  .sub{font-size:12px;color:var(--sub);margin-top:6px;letter-spacing:.5px}
  .filters{display:flex;gap:10px;align-items:center}
  .filters label{font-size:12px;color:var(--sub);margin-right:2px}
  select{background:var(--panel2);color:var(--text);border:1px solid var(--line);
    border-radius:6px;padding:6px 10px;font-size:12.5px;outline:none;cursor:pointer;
    font-family:inherit}
  select:hover{border-color:#31507c}
  .btn{background:rgba(53,196,240,.12);color:var(--cyan);border:1px solid #2a5b73;
    border-radius:6px;padding:6px 12px;font-size:12.5px;cursor:pointer;font-family:inherit}
  .btn:hover{background:rgba(53,196,240,.22)}
  .kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;padding:12px 24px 0}
  .kpi{position:relative;background:linear-gradient(180deg,var(--panel2),var(--panel));
    border:1px solid var(--line);border-radius:10px;padding:12px 16px 11px;overflow:hidden}
  .kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--c)}
  .kpi::after{content:"";position:absolute;right:-30px;top:-30px;width:90px;height:90px;
    border-radius:50%;background:var(--c);opacity:.07}
  .kpi .lbl{font-size:12px;color:var(--sub);letter-spacing:.4px}
  .kpi .val{font-size:27px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
  .kpi .val small{font-size:12px;font-weight:400;color:var(--sub);margin-left:4px}
  .kpi .delta{font-size:11.5px;margin-top:3px;color:var(--sub)}
  .up{color:#35D0A5}.down{color:#FF6B6B}
  .grid{display:grid;grid-template-columns:repeat(12,1fr);gap:12px;padding:12px 24px 18px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
    padding:10px 12px 6px;position:relative}
  .card h3{margin:0;font-size:13.5px;font-weight:600;color:#CFDCF0;letter-spacing:.4px}
  .card .hint{font-size:10.5px;color:#607492;margin:3px 0 4px}
  .chart{width:100%;height:250px}
  .chart.tall{height:250px}
  table.mini{width:100%;border-collapse:collapse;font-size:11.5px}
  table.mini th{color:#7E90AD;font-weight:500;text-align:left;padding:5px 4px;
    border-bottom:1px solid var(--line)}
  table.mini td{padding:5px 4px;border-bottom:1px dashed rgba(34,48,76,.7);
    color:#D3DEF0;font-variant-numeric:tabular-nums}
  table.mini tr:hover td{background:rgba(53,196,240,.06)}
  .tag{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px}
  .foot{padding:0 24px 14px;color:#5A6C8A;font-size:10.5px;display:flex;
    justify-content:space-between}
  .loading{color:var(--sub);font-size:12px;padding:20px}
</style>
</head>
<body>
<div class="top">
  <div>
    <div class="title">Sample–Superstore 商业分析数据驾驶舱</div>
    <div class="sub">2023–2026 ｜ 10,194 条订单明细 ｜ 5,111 笔订单 ｜ 804 位客户 ｜ 全 Python 生成（Matplotlib + ECharts）</div>
  </div>
  <div class="filters">
    <label>年份</label><select id="fy"></select>
    <label>大区</label><select id="fr"></select>
    <label>品类</label><select id="fc"></select>
    <button class="btn" id="reset">重置筛选</button>
  </div>
</div>

<div class="kpis">
  <div class="kpi" style="--c:var(--cyan)"><div class="lbl">销售额合计</div>
    <div class="val" id="k1">—<small>万美元</small></div><div class="delta" id="k1s"></div></div>
  <div class="kpi" style="--c:var(--amber)"><div class="lbl">利润合计</div>
    <div class="val" id="k2">—<small>万美元</small></div><div class="delta" id="k2s"></div></div>
  <div class="kpi" style="--c:var(--green)"><div class="lbl">整体毛利率</div>
    <div class="val" id="k3">—</div><div class="delta" id="k3s"></div></div>
  <div class="kpi" style="--c:var(--violet)"><div class="lbl">订单数</div>
    <div class="val" id="k4">—<small>单</small></div><div class="delta" id="k4s"></div></div>
  <div class="kpi" style="--c:var(--coral)"><div class="lbl">退货率</div>
    <div class="val" id="k5">—</div><div class="delta" id="k5s"></div></div>
</div>

<div class="grid">
  <div class="card" style="grid-column:span 6">
    <h3>月度销售额趋势与同比增速</h3><div class="hint">柱=销售额（万美元），线=同比增速（右轴）；筛选“全部年份”时线为 3 期移动平均</div>
    <div class="chart" id="cTrend"></div>
  </div>
  <div class="card" style="grid-column:span 3">
    <h3>品类销售结构</h3><div class="hint">点击扇区可下钻到该品类</div>
    <div class="chart" id="cStruct"></div>
  </div>
  <div class="card" style="grid-column:span 3">
    <h3>四大区表现</h3><div class="hint">柱=销售额，线=毛利率；点击柱子可下钻</div>
    <div class="chart" id="cRegion"></div>
  </div>

  <div class="card" style="grid-column:span 4">
    <h3>子类帕累托 / ABC 分类</h3><div class="hint">柱=销售额，线=累计占比；70%/90% 为 A/B 类分界</div>
    <div class="chart" id="cPareto"></div>
  </div>
  <div class="card" style="grid-column:span 4">
    <h3>RFM 客户八分类</h3><div class="hint">X=购买次数（对数），Y=最近购买间隔，气泡=累计消费额</div>
    <div class="chart" id="cRfm"></div>
  </div>
  <div class="card" style="grid-column:span 4">
    <h3>同期群留存热力图</h3><div class="hint">行=首购月份，列=其后第 n 个月留存率（%）</div>
    <div class="chart" id="cCohort"></div>
  </div>

  <div class="card" style="grid-column:span 5">
    <h3>销售额预测（95% 置信区间）</h3><div class="hint" id="fcHint">未来 6 个月预测</div>
    <div class="chart" id="cFc"></div>
  </div>
  <div class="card" style="grid-column:span 4">
    <h3>折扣力度与毛利率 / 亏损占比</h3><div class="hint">柱=毛利率，线=该折扣档亏损明细占比</div>
    <div class="chart" id="cDisc"></div>
  </div>
  <div class="card" style="grid-column:span 3">
    <h3>子类经营明细 Top 10</h3><div class="hint">按当前筛选条件的销售额排序</div>
    <table class="mini" id="tbl"><thead><tr>
      <th>子类</th><th>销售额</th><th>毛利率</th></tr></thead><tbody></tbody></table>
  </div>
</div>

<div class="foot">
  <span>数据来源：Tableau 官方示例数据集 Sample–Superstore（官方 XLSX 下载，非爬虫）｜获取日期 2026-11-04</span>
  <span>图表由 Python 脚本 05_dashboard.py 生成，未使用 Tableau / Power BI / FineBI</span>
</div>

<script src="./echarts.min.js"></script>
<script>
const DS = __MAIN__;
const ORD = __ORD__;
const SUB = __SUB__;
const RFM = __RFM__;
const SEGC = __SEGC__;
const SEGN = __SEGN__;
const COH = __COH__;
const DISC = __DISC__;
const FC = __FC__;
const YEARS = __YEARS__;
const REGIONS = __REGIONS__;
const CATS = __CATS__;

const C = {cyan:'#35C4F0',amber:'#FFB13D',coral:'#FF6B6B',violet:'#8B7CF6',
           green:'#35D0A5',pink:'#F06CA8',line:'#22304C',sub:'#93A4BF',text:'#E6EDF7'};
const F = {y:'all', r:'all', c:'all'};
const charts = {};

const baseText = {color:C.sub, fontFamily:'Microsoft YaHei'};
const axisCommon = {
  axisLine:{lineStyle:{color:C.line}},
  axisLabel:{color:C.sub, fontSize:10.5},
  splitLine:{lineStyle:{color:'rgba(34,48,76,.75)'}}
};
const tooltipCommon = {
  backgroundColor:'rgba(17,26,46,.95)', borderColor:'#2A3A5A', borderWidth:1,
  textStyle:{color:C.text, fontSize:12}, extraCssText:'border-radius:6px;'
};

function init(id){ const el=document.getElementById(id); const c=echarts.init(el);
  charts[id]=c; return c; }
function wan(v){ return (v/1e4); }
function n0(v){ return Math.round(v).toLocaleString('zh-CN'); }

// ---------------- 过滤与聚合 ----------------
function fMain(){
  return DS.filter(d => (F.y==='all'||d[0]===+F.y) &&
                        (F.r==='all'||d[2]===F.r) &&
                        (F.c==='all'||d[3]===F.c));
}
function fSub(){
  return SUB.filter(d => (F.y==='all'||d[0]===+F.y) &&
                         (F.r==='all'||d[1]===F.r) &&
                         (F.c==='all'||d[2]===F.c));
}
// 订单级筛选：订单可跨品类，用位掩码判断是否含目标品类
function catBit(name){
  const i = CATS.indexOf(name);
  return i<0 ? 0 : (1<<i);
}
function fOrd(){
  const b = F.c==='all' ? 0 : catBit(F.c);
  return ORD.filter(d => (F.y==='all'||d[0]===+F.y) &&
                         (F.r==='all'||d[2]===F.r) &&
                         (b===0 || (d[3] & b)));
}
function sumBy(arr, key, val){
  const m = new Map();
  for(const d of arr){ m.set(d[key], (m.get(d[key])||0) + d[val]); }
  return m;
}

// ---------------- KPI ----------------
function renderKPI(){
  const rows = fMain();
  const ords = fOrd();
  const sales = rows.reduce((a,b)=>a+b[4],0);
  const profit = rows.reduce((a,b)=>a+b[5],0);
  const orders = ords.length;                    // 订单级去重计数（避免跨品类重复）
  const rets = ords.reduce((a,b)=>a+b[4],0);     // 退货订单数
  const margin = sales>0 ? profit/sales : 0;
  const retRate = orders>0 ? rets/orders : 0;

  // 同比：仅在选定单一年份时计算（与上一年同口径对比）
  let salesYoy=null, profitYoy=null, marginPrev=null, ordersYoy=null, retPrev=null;
  if(F.y!=='all'){
    const py = (+F.y)-1;
    const b = F.c==='all' ? 0 : catBit(F.c);
    const prev = DS.filter(d=> d[0]===py && (F.r==='all'||d[2]===F.r) &&
                               (F.c==='all'||d[3]===F.c));
    const pOrd = ORD.filter(d=> d[0]===py && (F.r==='all'||d[2]===F.r) &&
                                (b===0 || (d[3] & b)));
    if(prev.length){
      const ps = prev.reduce((a,b)=>a+b[4],0), pp = prev.reduce((a,b)=>a+b[5],0);
      const po = pOrd.length, pr = pOrd.reduce((a,b)=>a+b[4],0);
      salesYoy = ps? sales/ps-1 : null;
      profitYoy = pp? profit/pp-1 : null;
      marginPrev = ps? pp/ps : null;
      ordersYoy = po? orders/po-1 : null;
      retPrev = po? pr/po : null;
    }
  }
  const pct = v => (v>=0?'+':'') + (v*100).toFixed(1) + '%';
  const cls = v => v>=0? 'up':'down';
  const scope = (F.y==='all'?'全期':F.y+' 年') + ' · ' +
                (F.r==='all'?'全部大区':F.r) + ' · ' + (F.c==='all'?'全部品类':F.c);

  document.getElementById('k1').innerHTML = wan(sales).toFixed(1)+'<small>万美元</small>';
  document.getElementById('k1s').innerHTML = scope;
  document.getElementById('k2').innerHTML = wan(profit).toFixed(1)+'<small>万美元</small>';
  document.getElementById('k2s').innerHTML = '利润率 ' + (margin*100).toFixed(1) + '%';
  document.getElementById('k3').innerHTML = (margin*100).toFixed(2)+'%';
  document.getElementById('k3s').innerHTML = '客单价 ' + (orders? (sales/orders).toFixed(0):0) + ' 美元';
  document.getElementById('k4').innerHTML = n0(orders)+'<small>单</small>';
  document.getElementById('k4s').innerHTML = '退货订单 ' + n0(rets) + ' 单';
  document.getElementById('k5').innerHTML = (retRate*100).toFixed(2)+'%';
  document.getElementById('k5s').innerHTML = '行业常见区间 3%–8%';

  if(salesYoy!==null){
    document.getElementById('k1s').innerHTML =
      '<span class="'+cls(salesYoy)+'">同比 '+pct(salesYoy)+'</span> · '+scope;
    document.getElementById('k2s').innerHTML =
      '<span class="'+cls(profitYoy)+'">同比 '+pct(profitYoy)+'</span> · 利润率 '+
      (margin*100).toFixed(1)+'%';
    document.getElementById('k3s').innerHTML =
      '上年同期 '+(marginPrev*100).toFixed(2)+'% · 变动 '+((margin-marginPrev)*100).toFixed(2)+'pp';
    document.getElementById('k4s').innerHTML =
      '<span class="'+cls(ordersYoy)+'">同比 '+pct(ordersYoy)+'</span> · 退货 '+
      n0(rets)+' 单';
    document.getElementById('k5s').innerHTML =
      '上年同期 '+(retPrev*100).toFixed(2)+'%';
  }
}

// ---------------- 趋势 ----------------
function renderTrend(){
  const rows = fMain();
  const byMonth = new Array(12).fill(0);
  rows.forEach(d=>{ byMonth[d[1]-1] += d[4]; });
  let lineData, lineName, rightAxis = true;
  if(F.y!=='all'){
    const py=(+F.y)-1;
    const prevM = new Array(12).fill(0);
    DS.forEach(d=>{ if(d[0]===py && (F.r==='all'||d[2]===F.r) && (F.c==='all'||d[3]===F.c))
      prevM[d[1]-1]+=d[4]; });
    lineData = byMonth.map((v,i)=> prevM[i]>0 ? +(((v/prevM[i])-1)*100).toFixed(1) : null);
    lineName = '同比增速';
  } else {
    // 全部年份：用 3 期移动平均作为趋势线
    lineData = byMonth.map((v,i)=>{
      const s=[byMonth[Math.max(0,i-1)],byMonth[i],byMonth[Math.min(11,i+1)]];
      return +(s.reduce((a,b)=>a+b,0)/s.length/1e4).toFixed(1);
    });
    lineName = '3 期移动平均';
    rightAxis = false;
  }
  const c = charts.cTrend;
  const yAxis = [{
    type:'value', name:'万美元', nameTextStyle:{color:C.sub,fontSize:10},
    splitLine:{lineStyle:{color:'rgba(34,48,76,.75)'}},
    axisLabel:{color:C.sub,fontSize:10},
    axisLine:{lineStyle:{color:C.line}}
  }];
  if(rightAxis){
    yAxis.push({type:'value', name:'同比 %', nameTextStyle:{color:C.sub,fontSize:10},
      splitLine:{show:false}, axisLabel:{color:C.amber,fontSize:10}, axisLine:{show:false}});
  }
  c.setOption({
    backgroundColor:'transparent',
    grid:{left:52,right:48,top:24,bottom:28},
    tooltip:Object.assign({trigger:'axis', valueFormatter:v=> v==null?'—':v.toLocaleString()},
                          tooltipCommon),
    xAxis:Object.assign({type:'category',data:Array.from({length:12},(_,i)=>(i+1)+'月'),
                         axisTick:{show:false}}, axisCommon),
    yAxis:yAxis,
    series:[
      {name:'销售额', type:'bar', barWidth:'46%',
       data:byMonth.map(v=>+wan(v).toFixed(1)),
       itemStyle:{borderRadius:[4,4,0,0],
         color:new echarts.graphic.LinearGradient(0,0,0,1,[
           {offset:0,color:'#6FD6FF'},{offset:1,color:'rgba(53,196,240,.18)'}])}},
      {name:lineName, type:'line', yAxisIndex: rightAxis?1:0, smooth:true,
       data:lineData, symbol:'circle', symbolSize:6,
       lineStyle:{color:C.amber,width:2.4}, itemStyle:{color:C.amber},
       connectNulls:true}
    ]
  }, true);
}

// ---------------- 结构 ----------------
function renderStruct(){
  const rows = fMain();
  const m = sumBy(rows,3,4);
  const data = CATS.map(k=>({name:k, value:+wan(m.get(k)||0).toFixed(1)}));
  charts.cStruct.setOption({
    backgroundColor:'transparent',
    tooltip:Object.assign({trigger:'item', formatter:p=> p.name+'<br/>'+p.value+' 万美元 ('+
      p.percent+'%)'}, tooltipCommon),
    legend:{bottom:0, textStyle:baseText, itemWidth:9, itemHeight:9, icon:'circle'},
    series:[{
      type:'pie', radius:['42%','72%'], center:['50%','44%'], roseType:'radius',
      itemStyle:{borderColor:'#111A2E', borderWidth:2},
      label:{color:C.sub, fontSize:10, formatter:'{b}\n{d}%'},
      labelLine:{lineStyle:{color:'#33466A'}},
      data:data,
      color:[C.cyan,C.amber,C.violet]
    }]
  }, true);
  charts.cStruct.off('click');
  charts.cStruct.on('click', p=>{ F.c = p.name; document.getElementById('fc').value=p.name;
    renderAll(); });
}

// ---------------- 大区 ----------------
function renderRegion(){
  const rows = fMain();
  const s = sumBy(rows,2,4), p = sumBy(rows,2,5);
  const names = REGIONS.filter(r=> (F.r==='all') || r===F.r);
  const vals = names.map(r=>+wan(s.get(r)||0).toFixed(1));
  const margins = names.map(r=>{ const a=s.get(r)||0; return a? +(((p.get(r)||0)/a*100).toFixed(1)):0; });
  charts.cRegion.setOption({
    backgroundColor:'transparent',
    grid:{left:44,right:40,top:24,bottom:26},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, tooltipCommon),
    xAxis:Object.assign({type:'category',data:names,axisTick:{show:false}}, axisCommon),
    yAxis:[
      {type:'value',name:'万美元',nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{lineStyle:{color:'rgba(34,48,76,.75)'}},
       axisLabel:{color:C.sub,fontSize:10}},
      {type:'value',name:'毛利%',nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{show:false},axisLabel:{color:C.amber,fontSize:10}}
    ],
    series:[
      {name:'销售额', type:'bar', barWidth:'44%', data:vals,
       itemStyle:{borderRadius:[4,4,0,0],
         color:new echarts.graphic.LinearGradient(0,0,0,1,[
           {offset:0,color:'#8BE0A8'},{offset:1,color:'rgba(53,208,165,.15)'}])}},
      {name:'毛利率', type:'line', yAxisIndex:1, data:margins, symbol:'circle',
       symbolSize:6, lineStyle:{color:C.amber,width:2}, itemStyle:{color:C.amber}}
    ]
  }, true);
  charts.cRegion.off('click');
  charts.cRegion.on('click', p=>{ F.r = p.name; document.getElementById('fr').value=p.name;
    renderAll(); });
}

// ---------------- 帕累托 ----------------
function renderPareto(){
  const rows = fSub();
  const m = sumBy(rows,3,4);
  const arr = [...m.entries()].sort((a,b)=>b[1]-a[1]);
  const total = arr.reduce((a,b)=>a+b[1],0) || 1;
  const names = arr.map(d=>d[0]);
  const vals = arr.map(d=>+wan(d[1]).toFixed(1));
  let cum=0; const cums = arr.map(d=>{ cum+=d[1]; return +(cum/total*100).toFixed(1); });
  charts.cPareto.setOption({
    backgroundColor:'transparent',
    grid:{left:52,right:46,top:24,bottom:58},
    tooltip:Object.assign({trigger:'axis',axisPointer:{type:'shadow'}}, tooltipCommon),
    xAxis:Object.assign({type:'category',data:names,
      axisLabel:{color:C.sub,fontSize:9.5,rotate:42,interval:0},axisTick:{show:false}}, axisCommon),
    yAxis:[
      {type:'value',name:'万美元',nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{lineStyle:{color:'rgba(34,48,76,.75)'}},
       axisLabel:{color:C.sub,fontSize:10}},
      {type:'value',name:'累计%',max:100,nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{show:false},axisLabel:{color:C.amber,fontSize:10}}
    ],
    series:[
      {name:'销售额',type:'bar',barWidth:'58%',data:vals,
       itemStyle:{borderRadius:[3,3,0,0], color:p=> cums[p.dataIndex]<=70?C.cyan:
         (cums[p.dataIndex]<=90?'#4FA9C9':'#39506F')}},
      {name:'累计占比',type:'line',yAxisIndex:1,data:cums,symbol:'circle',symbolSize:5,
       lineStyle:{color:C.amber,width:2}, itemStyle:{color:C.amber},
       markLine:{silent:true,symbol:'none',
         label:{color:C.sub,fontSize:10,formatter:'{b}'},
         data:[{yAxis:70,name:'A 类 70%',lineStyle:{color:'#5B7BA8',type:'dashed'}},
               {yAxis:90,name:'B 类 90%',lineStyle:{color:'#5B7BA8',type:'dashed'}}]}}
    ]
  }, true);
}

// ---------------- RFM ----------------
function renderRfm(){
  const colors=[C.cyan,'#FF8E72',C.green,C.amber,C.violet,'#7E93B5',C.pink,'#C96A8E'];
  const series = SEGN.map((nm,i)=>({
    name:nm, type:'scatter',
    data:RFM.filter(d=>d[3]===i).map(d=>[d[0],d[1],d[2]]),
    symbolSize: d=> Math.min(Math.max(Math.sqrt(d[2])*0.85,4),26),
    itemStyle:{color:colors[i],opacity:.62,borderColor:'rgba(255,255,255,.25)',borderWidth:.5},
    emphasis:{focus:'series'}
  }));
  charts.cRfm.setOption({
    backgroundColor:'transparent',
    grid:{left:44,right:14,top:22,bottom:34},
    tooltip:Object.assign({trigger:'item',
      formatter:p=> p.seriesName+'<br/>购买次数 '+p.data[0]+' 次<br/>最近间隔 '+
        p.data[1]+' 天<br/>累计消费 '+n0(p.data[2])+' 美元'}, tooltipCommon),
    legend:{bottom:0,textStyle:{color:C.sub,fontSize:9.5},itemWidth:8,itemHeight:8,
      itemGap:8,icon:'circle'},
    xAxis:Object.assign({type:'log',name:'购买次数',nameTextStyle:{color:C.sub,fontSize:10},
      nameLocation:'middle',nameGap:20,min:1,
      splitLine:{show:false}}, axisCommon),
    yAxis:Object.assign({type:'value',inverse:true,name:'R（天）',
      nameTextStyle:{color:C.sub,fontSize:10}}, axisCommon),
    series:series
  }, true);
}

// ---------------- 同期群 ----------------
function renderCohort(){
  charts.cCohort.setOption({
    backgroundColor:'transparent',
    grid:{left:74,right:16,top:14,bottom:52},
    tooltip:Object.assign({formatter:p=> COH.cohorts[p.data[1]]+' 群<br/>第 '+
      COH.periods[p.data[0]]+' 期留存 '+p.data[2]+'%'}, tooltipCommon),
    xAxis:{type:'category',data:COH.periods.map(p=>'第'+p+'期'),splitArea:{show:false},
      axisLabel:{color:C.sub,fontSize:9,interval:1},axisLine:{lineStyle:{color:C.line}}},
    yAxis:{type:'category',data:COH.cohorts,splitArea:{show:false},
      axisLabel:{color:C.sub,fontSize:9},axisLine:{lineStyle:{color:C.line}}},
    visualMap:{min:0,max:100,calculable:false,orient:'horizontal',left:'center',bottom:0,
      itemWidth:10,itemHeight:70,textStyle:{color:C.sub,fontSize:9},
      inRange:{color:['#14233B','#1E5C7A','#2A93B8','#35C4F0','#9BE7FF']}},
    series:[{type:'heatmap',data:COH.cells,
      itemStyle:{borderColor:'#0A1020',borderWidth:1.2},
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1.4}}}]
  }, true);
}

// ---------------- 预测 ----------------
function renderForecast(){
  const hx = FC.hist_x, fx = FC.fc_x;
  const x = hx.concat(fx);
  const hist = FC.hist_y.concat(fx.map(()=>null));
  const fc = hx.map(v=>null).concat(FC.fc_y);
  const lo = hx.map(v=>null).concat(FC.lo);
  const band = hx.map(v=>null).concat(FC.hi.map((h,i)=>+(h-FC.lo[i]).toFixed(1)));
  charts.cFc.setOption({
    backgroundColor:'transparent',
    grid:{left:56,right:20,top:26,bottom:46},
    tooltip:Object.assign({trigger:'axis'}, tooltipCommon),
    legend:{data:['历史销售额','预测值','95% 置信区间'],bottom:0,
      textStyle:{color:C.sub,fontSize:10},itemWidth:12,itemHeight:8},
    xAxis:Object.assign({type:'category',data:x,boundaryGap:false,
      axisLabel:{color:C.sub,fontSize:9,interval:2}}, axisCommon),
    yAxis:Object.assign({type:'value',name:'万美元',
      axisLabel:{color:C.sub,fontSize:10,formatter:v=>v/1e4}}, axisCommon),
    series:[
      {name:'下界',type:'line',stack:'ci',data:lo,symbol:'none',
       lineStyle:{opacity:0},areaStyle:{opacity:0},silent:true},
      {name:'95% 置信区间',type:'line',stack:'ci',data:band,symbol:'none',
       lineStyle:{opacity:0},
       areaStyle:{color:'rgba(255,107,107,.16)'},silent:true},
      {name:'历史销售额',type:'line',data:hist,smooth:true,symbol:'none',
       lineStyle:{color:C.cyan,width:2.2},
       areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[
         {offset:0,color:'rgba(53,196,240,.45)'},{offset:1,color:'rgba(53,196,240,0)'}])}},
      {name:'预测值',type:'line',data:fc,smooth:true,symbol:'circle',symbolSize:5,
       lineStyle:{color:C.coral,width:2.4,type:'dashed'},itemStyle:{color:C.coral}}
    ]
  }, true);
  document.getElementById('fcHint').innerHTML =
    '最终模型 '+FC.model+' ｜ 回测 MAPE '+(FC.mape*100).toFixed(1)+'% ｜ 阴影为 95% 置信区间';
}

// ---------------- 折扣 ----------------
function renderDisc(){
  charts.cDisc.setOption({
    backgroundColor:'transparent',
    grid:{left:46,right:42,top:26,bottom:46},
    tooltip:Object.assign({trigger:'axis'}, tooltipCommon),
    xAxis:Object.assign({type:'category',data:DISC.labels,axisTick:{show:false},
      axisLabel:{color:C.sub,fontSize:9.5,rotate:30}}, axisCommon),
    yAxis:[
      {type:'value',name:'毛利%',nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{lineStyle:{color:'rgba(34,48,76,.75)'}},
       axisLabel:{color:C.sub,fontSize:10}},
      {type:'value',name:'亏损%',max:100,nameTextStyle:{color:C.sub,fontSize:10},
       splitLine:{show:false},axisLabel:{color:C.violet,fontSize:10}}
    ],
    series:[
      {name:'毛利率',type:'bar',barWidth:'52%',data:DISC.margin,
       itemStyle:{borderRadius:[3,3,0,0],
         color:p=> p.value>=8?C.green : (p.value>=0?C.amber:C.coral)}},
      {name:'亏损占比',type:'line',yAxisIndex:1,data:DISC.loss,symbol:'circle',
       symbolSize:6,lineStyle:{color:C.violet,width:2},itemStyle:{color:C.violet}}
    ]
  }, true);
}

// ---------------- 明细表 ----------------
function renderTable(){
  const rows = fSub();
  const m = new Map();
  rows.forEach(d=>{
    const k=d[3];
    const cur = m.get(k)||{s:0,p:0};
    cur.s+=d[4]; cur.p+=d[5]; m.set(k,cur);
  });
  const arr=[...m.entries()].map(([k,v])=>({k,s:v.s,p:v.p,
    mg: v.s? v.p/v.s : 0})).sort((a,b)=>b.s-a.s).slice(0,10);
  const tb = document.querySelector('#tbl tbody');
  tb.innerHTML = arr.map(r=>{
    const cls = r.mg>=0.15? 'background:rgba(53,208,165,.14);color:#5FE3BB'
              : (r.mg>=0? 'background:rgba(255,177,61,.14);color:#FFC46B'
                        : 'background:rgba(255,107,107,.16);color:#FF8E8E');
    return '<tr><td>'+r.k+'</td><td>'+wan(r.s).toFixed(1)+' 万</td>'+
           '<td><span class="tag" style="'+cls+'">'+(r.mg*100).toFixed(1)+'%</span></td></tr>';
  }).join('');
}

// ---------------- 总调度 ----------------
function renderAll(){
  renderKPI(); renderTrend(); renderStruct(); renderRegion();
  renderPareto(); renderRfm(); renderCohort();
  renderForecast(); renderDisc(); renderTable();
}

function fillSelect(id, items, allLabel){
  const el = document.getElementById(id);
  el.innerHTML = '<option value="all">'+allLabel+'</option>' +
    items.map(v=>'<option value="'+v+'">'+v+'</option>').join('');
}

window.addEventListener('load', ()=>{
  init('cTrend'); init('cStruct'); init('cRegion'); init('cPareto');
  init('cRfm'); init('cCohort'); init('cFc'); init('cDisc');

  fillSelect('fy', YEARS.map(String), '全部年份');
  fillSelect('fr', REGIONS, '全部大区');
  fillSelect('fc', CATS, '全部品类');
  document.getElementById('fy').addEventListener('change', e=>{ F.y=e.target.value; renderAll(); });
  document.getElementById('fr').addEventListener('change', e=>{ F.r=e.target.value; renderAll(); });
  document.getElementById('fc').addEventListener('change', e=>{ F.c=e.target.value; renderAll(); });
  document.getElementById('reset').addEventListener('click', ()=>{
    F.y='all';F.r='all';F.c='all';
    document.getElementById('fy').value='all';
    document.getElementById('fr').value='all';
    document.getElementById('fc').value='all';
    renderAll();
  });

  renderAll();
  window.addEventListener('resize', ()=> Object.values(charts).forEach(c=>c.resize()));
});
</script>
</body>
</html>
"""


# ============================================================
# 3. 渲染
# ============================================================
def build_html(ds: dict) -> str:
    """把数据集注入 HTML 模板。"""
    return (TEMPLATE
            .replace("__MAIN__", json.dumps(ds["main"], ensure_ascii=False))
            .replace("__ORD__", json.dumps(ds["orders"], ensure_ascii=False))
            .replace("__SUB__", json.dumps(ds["sub"], ensure_ascii=False))
            .replace("__RFM__", json.dumps(ds["rfm"], ensure_ascii=False))
            .replace("__SEGC__", json.dumps(ds["seg_count"], ensure_ascii=False))
            .replace("__SEGN__", json.dumps(ds["seg_names"], ensure_ascii=False))
            .replace("__COH__", json.dumps(ds["cohort"], ensure_ascii=False))
            .replace("__DISC__", json.dumps(ds["disc"], ensure_ascii=False))
            .replace("__FC__", json.dumps(ds["forecast"], ensure_ascii=False))
            .replace("__YEARS__", json.dumps(ds["years"], ensure_ascii=False))
            .replace("__REGIONS__", json.dumps(ds["regions"], ensure_ascii=False))
            .replace("__CATS__", json.dumps(ds["cats"], ensure_ascii=False)))


def run() -> Path:
    """生成大屏 HTML 并返回路径。"""
    print("[05] 构建暗色交互大屏")
    d = load_data()
    ds = build_datasets(d)
    html = build_html(ds)

    out = DASH_DIR / "商业分析大屏.html"
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"      [√] 组件：5 KPI + 8 图表 + 1 明细表 + 3 筛选器")
    print(f"      [√] 数据点：主表 {len(ds['main'])} 行、子类 {len(ds['sub'])} 行、"
          f"RFM {len(ds['rfm'])} 点")
    print(f"      [√] 已生成 {out}（{size:,.0f} KB）")
    if not MAIN_JS.exists():
        print("      [!] 未找到 echarts.min.js，HTML 将无法离线渲染，请执行："
              "下载 echarts.min.js 到 dashboard/ 目录")
    return out


if __name__ == "__main__":
    run()
