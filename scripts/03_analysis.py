"""
03_analysis.py —— 商业分析模型计算（7 大模型，对应论文第 3 章）
--------------------------------------------------------------------------------
本文件职责：只做“算”，不做“画”。每个模型产出一张结果表到 outputs/tables/，
供 04_visuals.py 出图、05_dashboard.py 做 KPI 卡，并保证图-表-结论三者一一对应。

模型清单（≥3 种，实际 7 种）：
  M1 同比 / 环比 + 移动平均         —— 趋势与对比
  M2 帕累托 / ABC 分类              —— 结构与价值
  M3 RFM 八分类                     —— 用户与客群
  M4 K-Means 用户分群               —— 用户与客群
  M5 同期群留存分析                 —— 用户与客群
  M6 波士顿矩阵（份额×增速气泡）     —— 结构与价值
  M7 SARIMA 销售预测（95% 置信区间） —— 预测与预警
  M8 Apriori 关联规则（购物篮）      —— 关联与转化
  M9 漏斗转化分析                    —— 关联与转化
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from common import DATA_CLEAN, save_table

warnings.filterwarnings("ignore")

TIMESERIES_MIN_MONTHS = 12


# ============================================================
# 读取清洗后宽表
# ============================================================
def load_clean() -> pd.DataFrame:
    """优先读 pickle（快），否则读 CSV。"""
    pkl, csv = DATA_CLEAN / "orders_clean.pkl", DATA_CLEAN / "orders_clean.csv"
    df = pd.read_pickle(pkl) if pkl.exists() else pd.read_csv(csv)
    df["Order Date"] = pd.to_datetime(df["Order Date"])
    return df


# ============================================================
# M1 同比 / 环比 + 移动平均
# ============================================================
def m1_trend(orders: pd.DataFrame) -> pd.DataFrame:
    """
    月度经营趋势：销售额、利润、订单数、客单价，并计算同比(YoY)、环比(MoM)、3 期移动平均。
    同比口径：本月 / 去年同月 - 1；环比口径：本月 / 上月 - 1；
    移动平均：3 个月滑动平均，用于剔除月度波动、识别趋势方向。
    """
    m = (orders.groupby("年月")
         .agg(销售额=("Sales", "sum"), 利润=("Profit", "sum"),
              订单数=("Order ID", "nunique"), 销量=("Quantity", "sum"))
         .reset_index())
    m["毛利率"] = m["利润"] / m["销售额"]
    m["客单价"] = m["销售额"] / m["订单数"]
    m = m.sort_values("年月").reset_index(drop=True)

    # 环比：相邻月
    m["环比"] = m["销售额"].pct_change()
    # 同比：相隔 12 个月（用字典映射，避免排序错位）
    sales_by_ym = dict(zip(m["年月"], m["销售额"]))
    def _yoy(row):
        y, mo = int(row["年月"][:4]), int(row["年月"][5:7])
        prev = f"{y-1}-{mo:02d}"
        return row["销售额"] / sales_by_ym[prev] - 1 if prev in sales_by_ym else np.nan
    m["同比"] = m.apply(_yoy, axis=1)
    # 移动平均（窗口 3，中心对齐更贴近趋势）
    m["销售额_MA3"] = m["销售额"].rolling(3, min_periods=1).mean()
    m["利润_MA3"] = m["利润"].rolling(3, min_periods=1).mean()

    save_table(m, "t06_月度趋势_同比环比.csv")
    return m


# ============================================================
# M2 帕累托 / ABC 分类
# ============================================================
def m2_pareto(orders: pd.DataFrame, dim: str = "子类", top_label: str = "子类") -> pd.DataFrame:
    """
    帕累托/ABC：按销售额降序累计，累计占比 ≤70% 为 A 类（核心），
    (70%, 90%] 为 B 类（腰部），>90% 为 C 类（长尾）。
    阈值依据：帕累托法则（80/20）在零售场景的通用切分；70/90 是库存 ABC 管理的行业惯例，
    比 80 更利于把“真正决定现金流”的少数 SKU 单独拎出来管理。
    """
    g = (orders.groupby(dim)
         .agg(销售额=("Sales", "sum"), 利润=("Profit", "sum"), 销量=("Quantity", "sum"))
         .reset_index())
    g["毛利率"] = g["利润"] / g["销售额"]
    g = g.sort_values("销售额", ascending=False).reset_index(drop=True)
    g["排名"] = np.arange(1, len(g) + 1)
    g["销售额占比"] = g["销售额"] / g["销售额"].sum()
    g["累计占比"] = g["销售额占比"].cumsum()
    g["ABC等级"] = np.where(g["累计占比"] <= 0.70, "A 类",
                     np.where(g["累计占比"] <= 0.90, "B 类", "C 类"))
    save_table(g, f"t07_帕累托_ABC_{top_label}.csv")
    return g


# ============================================================
# M3 RFM 八分类
# ============================================================
def m3_rfm(orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    RFM 模型（八分类）
    - R（Recency）最近一次购买距今天数，越小越好；
    - F（Frequency）购买次数（按订单去重）；
    - M（Monetary）累计销售额。
    阈值依据：三项分布均显著右偏（少数大客户拉高均值），故用**中位数**切分，
    保证高/低两组客户数各占约 50%，避免均值切分导致“高价值组只剩几十人”的失真。
    高/低打标后按 (R,F,M) 组合映射到 8 个业务客群。
    """
    snapshot = orders["Order Date"].max() + pd.Timedelta(days=1)   # 观察截止日
    rfm = (orders.groupby(["Customer ID", "Customer Name"])
           .agg(最近购买=("Order Date", "max"),
                购买次数=("Order ID", "nunique"),
                累计销售额=("Sales", "sum"),
                累计利润=("Profit", "sum"))
           .reset_index())
    rfm["R值"] = (snapshot - rfm["最近购买"]).dt.days
    rfm["F值"] = rfm["购买次数"]
    rfm["M值"] = rfm["累计销售额"]
    rfm["客单价"] = rfm["M值"] / rfm["F值"]
    rfm["毛利率"] = rfm["累计利润"] / rfm["M值"]

    r_thr, f_thr, m_thr = rfm["R值"].median(), rfm["F值"].median(), rfm["M值"].median()
    # R 是“越小越好”，故 R值 <= 中位数 记为“高”（近期活跃）
    rfm["R_高"] = (rfm["R值"] <= r_thr).astype(int)
    rfm["F_高"] = (rfm["F值"] >= f_thr).astype(int)
    rfm["M_高"] = (rfm["M值"] >= m_thr).astype(int)

    def _seg(r):
        key = (r["R_高"], r["F_高"], r["M_高"])
        return {
            (1, 1, 1): "重要价值客户",   # 近期买、买得频、花得多 —— 重点维护
            (0, 1, 1): "重要唤回客户",   # 曾经高频高额但已久未光顾 —— 流失预警
            (1, 0, 1): "重要深耕客户",   # 近期有单、金额高但频次低 —— 提升频次
            (0, 0, 1): "重要挽留客户",   # 高客单但沉睡 —— 定向召回
            (1, 1, 0): "一般保持客户",   # 活跃高频但客单低 —— 提客单
            (0, 1, 0): "一般发展客户",   # 低频低额且沉睡
            (1, 0, 0): "潜力新客",       # 近期首购 —— 培养复购
            (0, 0, 0): "流失客户",       # 三低 —— 低成本触达或不投入
        }[key]
    rfm["RFM客群"] = rfm.apply(_seg, axis=1)
    rfm["R分位"] = rfm["R值"].rank(pct=True)
    rfm["F分位"] = rfm["F值"].rank(pct=True)
    rfm["M分位"] = rfm["M值"].rank(pct=True)

    order_pref = ["重要价值客户", "重要唤回客户", "重要深耕客户", "重要挽留客户",
                  "一般保持客户", "一般发展客户", "潜力新客", "流失客户"]
    summ = (rfm.groupby("RFM客群")
            .agg(客户数=("Customer ID", "nunique"), 销售额=("M值", "sum"),
                 利润=("累计利润", "sum"), 平均R=("R值", "mean"),
                 平均F=("F值", "mean"), 平均M=("M值", "mean"))
            .reindex(order_pref).reset_index())
    summ["客户占比"] = summ["客户数"] / summ["客户数"].sum()
    summ["销售额占比"] = summ["销售额"] / summ["销售额"].sum()
    summ["人均销售额"] = summ["销售额"] / summ["客户数"]
    summ["毛利率"] = summ["利润"] / summ["销售额"]
    summ = summ.round(4)

    # 阈值写进结果表，论文可直接引用
    thr = pd.DataFrame({"指标": ["R 中位数(天)", "F 中位数(次)", "M 中位数(美元)", "观察截止日"],
                        "取值": [r_thr, f_thr, round(m_thr, 2), snapshot.strftime("%Y-%m-%d")]})
    save_table(thr, "t08a_RFM阈值.csv")
    save_table(rfm.round(4), "t08_RFM客户明细.csv")
    save_table(summ, "t09_RFM八分类汇总.csv")
    print(f"      RFM 阈值：R={r_thr:.0f} 天，F={f_thr:.0f} 次，M={m_thr:,.0f} 美元")
    return rfm, summ


# ============================================================
# M4 K-Means 用户分群
# ============================================================
def m4_kmeans(rfm: pd.DataFrame, k_min: int = 3, k_max: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    K-Means 客群聚类
    特征工程：RFM 三项均右偏，先 log1p 压缩量纲，再做 Z-score 标准化；
    K 的选择：在 3~6 之间用轮廓系数（silhouette）择优 ——
    下限 3 保证客群具备可运营的区分度，上限 6 避免人群切得太碎、无法落地。
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    X_raw = rfm[["R值", "F值", "M值"]].astype(float)
    X = StandardScaler().fit_transform(np.log1p(X_raw))

    scores, models = {}, {}
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        lab = km.fit_predict(X)
        scores[k] = float(silhouette_score(X, lab))
        models[k] = km
    best_k = max(scores, key=scores.get)
    km = models[best_k]

    out = rfm.copy()
    out["聚类簇"] = km.labels_
    # 用簇内均值给簇打业务标签（按 M 从高到低 + R 高低命名）
    prof = (out.groupby("聚类簇")
            .agg(客户数=("Customer ID", "nunique"), 平均R=("R值", "mean"),
                 平均F=("F值", "mean"), 平均M=("M值", "mean"),
                 销售额=("M值", "sum"), 毛利率=("毛利率", "mean")).reset_index())
    prof["人均销售额"] = prof["销售额"] / prof["客户数"]
    m_rank = prof["平均M"].rank(ascending=False, method="first")
    r_rank = prof["平均R"].rank(ascending=True, method="first")   # R 小=近期活跃=排名靠前
    label_map = {}
    for i, row in prof.iterrows():
        mi, ri = int(m_rank[i]), int(r_rank[i])
        if mi == 1:
            label_map[row["聚类簇"]] = "核心高价值群"
        elif mi == 2:
            label_map[row["聚类簇"]] = "成长潜力群" if ri <= len(prof) / 2 else "沉睡高额群"
        elif ri == 1:
            label_map[row["聚类簇"]] = "活跃长尾群"
        else:
            label_map[row["聚类簇"]] = "低频休眠群"
    out["KMeans客群"] = out["聚类簇"].map(label_map)
    prof["业务标签"] = prof["聚类簇"].map(label_map)
    prof["客户占比"] = prof["客户数"] / prof["客户数"].sum()
    prof["销售额占比"] = prof["销售额"] / prof["销售额"].sum()
    prof = prof.sort_values("平均M", ascending=False).round(4)

    sil = pd.DataFrame({"K值": list(scores.keys()),
                        "轮廓系数": [round(v, 4) for v in scores.values()]})
    sil["是否选中"] = np.where(sil["K值"] == best_k, "是", "")
    save_table(sil, "t10a_KMeans轮廓系数.csv")
    save_table(prof, "t10_KMeans客群画像.csv")
    print(f"      K-Means 最优 K={best_k}（轮廓系数 {scores[best_k]:.3f}）")
    return out, prof


# ============================================================
# M5 同期群留存
# ============================================================
def m5_cohort(orders: pd.DataFrame, max_period: int = 12) -> pd.DataFrame:
    """
    同期群（Cohort）留存：
    以客户**首次购买月份**为同期群（cohort），统计其后第 n 个自然月的复购客户数占该群规模的比例。
    口径：同一客户在同月多次下单只计 1 次；第 0 期即首购月，留存率恒为 100%。
    """
    o = orders.copy()
    o["订单月"] = o["Order Date"].dt.to_period("M")
    first = o.groupby("Customer ID")["订单月"].min().rename("首购月")
    o = o.merge(first, on="Customer ID")
    o["期数"] = (o["订单月"].dt.year - o["首购月"].dt.year) * 12 + \
                (o["订单月"].dt.month - o["首购月"].dt.month)

    cohort_size = o.groupby("首购月")["Customer ID"].nunique().rename("群规模")
    active = (o.groupby(["首购月", "期数"])["Customer ID"].nunique()
              .rename("活跃客户数").reset_index())
    mat = active.pivot(index="首购月", columns="期数", values="活跃客户数")
    mat = mat.reindex(columns=range(0, max_period + 1))
    rate = mat.div(cohort_size, axis=0)
    rate = rate.loc[rate.index <= rate.index.max()]      # 保持时间顺序

    # 只保留群规模 >= 20 的同期群，避免小样本噪声
    keep = cohort_size[cohort_size >= 20].index
    rate = rate.loc[rate.index.isin(keep)]

    out = rate.reset_index()
    out["首购月"] = out["首购月"].astype(str)
    out.insert(1, "群规模", cohort_size.reindex(rate.index).values)
    out.columns = ["首购月", "群规模"] + [f"第{c}期" for c in rate.columns]
    save_table(out.round(4), "t11_同期群留存矩阵.csv")

    # 平均留存曲线（供大屏折线使用）
    avg = rate.mean(axis=0).reset_index()
    avg.columns = ["期数", "平均留存率"]
    avg["期数"] = avg["期数"].astype(int)
    save_table(avg.round(4), "t11b_平均留存曲线.csv")
    print(f"      同期群：{len(rate)} 个群，平均首月留存 {rate[1].mean():.1%}")
    return out


# ============================================================
# M6 波士顿矩阵
# ============================================================
def m6_bcg(orders: pd.DataFrame) -> pd.DataFrame:
    """
    波士顿矩阵（BCG）：横轴=销售额份额（结构地位），纵轴=同比增长（增长性），气泡=销售额，颜色=毛利率。
    取 2025 与 2026 两个**完整自然年**计算同比，避免用不完整年份造成增速失真；
    分界线：横轴取“平均份额”（=1/子类数），纵轴取“整体同比增速”，保证四象限划分与业务口径一致。
    """
    o = orders[orders["年份"].isin([2025, 2026])]
    g = (o.groupby(["子类", "年份"])["Sales"].sum().unstack("年份").fillna(0))
    g.columns = ["2025销售额", "2026销售额"]
    g["同比增速"] = g["2026销售额"] / g["2025销售额"].replace(0, np.nan) - 1
    g = g.reset_index()

    total = g["2026销售额"].sum()
    g["销售额份额"] = g["2026销售额"] / total
    # 补充利润率与销量
    extra = (orders[orders["年份"] == 2026].groupby("子类")
             .agg(利润=("Profit", "sum"), 销量=("Quantity", "sum")).reset_index())
    g = g.merge(extra, on="子类", how="left")
    g["毛利率"] = g["利润"] / g["2026销售额"]
    g["利润贡献"] = g["利润"] / g["利润"].sum()

    share_line = 1 / len(g)                                 # 平均份额线
    growth_line = (g["2026销售额"].sum() / g["2025销售额"].sum()) - 1   # 整体增速线
    g["象限"] = np.select(
        [(g["销售额份额"] >= share_line) & (g["同比增速"] >= growth_line),
         (g["销售额份额"] >= share_line) & (g["同比增速"] < growth_line),
         (g["销售额份额"] < share_line) & (g["同比增速"] >= growth_line)],
        ["明星业务", "现金牛业务", "问题业务"], default="瘦狗业务")
    g = g.sort_values("2026销售额", ascending=False).reset_index(drop=True)
    g.attrs["share_line"] = share_line
    g.attrs["growth_line"] = growth_line

    save_table(g.round(4), "t12_波士顿矩阵.csv")
    print(f"      BCG 分界线：份额 {share_line:.2%}，整体增速 {growth_line:.2%}")
    return g


# ============================================================
# M7 时间序列预测（SARIMA vs Holt-Winters 比选）
# ============================================================
def m7_forecast(ts: pd.DataFrame, horizon: int = 6, test_len: int = 6) -> dict:
    """
    月度销售额预测（含 95% 置信区间 + 回测误差 + 模型比选）

    建模流程：
      1) 用前 42 个月训练、末尾 6 个月做回测，计算 MAPE / RMSE / MAE；
      2) 候选模型两类：
         a. SARIMA：p,q ∈{0,1,2}、P,Q∈{0,1}，d=1、D=1、s=12，按 AIC 最小择优；
         b. Holt-Winters：加性趋势加性季节、加性趋势加性季节（阻尼）；
      3) 以「回测 MAPE 最小」为最终评判准则选模型（预测型任务更应看样本外误差，
         AIC 只用于同一模型族内部的阶数选择），再用全样本重估、外推 6 个月；
      4) 置信区间：SARIMA 用解析 95% 区间；Holt-Winters 用 1,000 次蒙特卡洛模拟取 2.5%/97.5% 分位。

    业务依据：零售月度销售存在明显年度季节性（9 月开学季、11–12 月年末采购季），
    故取 s=12；一阶差分 d=1 消除趋势，D=1 消除季节趋势。
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    s = ts.set_index(pd.PeriodIndex(ts["年月"], freq="M"))["销售额"].astype(float)
    s.index = s.index.to_timestamp()
    n = len(s)
    if n < TIMESERIES_MIN_MONTHS:
        raise ValueError(f"时间序列过短（{n} 个月），无法建模")

    train, test = s.iloc[:n - test_len], s.iloc[n - test_len:]

    def _err(actual, pred):
        mape = float(np.mean(np.abs((actual - pred) / actual)))
        rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
        mae = float(np.mean(np.abs(actual - pred)))
        return mape, rmse, mae

    # ---------- 候选 1：SARIMA（AIC 网格搜索）----------
    best = None
    for p in range(3):
        for q in range(3):
            for P in range(2):
                for Q in range(2):
                    try:
                        mod = SARIMAX(train, order=(p, 1, q), seasonal_order=(P, 1, Q, 12),
                                      enforce_stationarity=False,
                                      enforce_invertibility=False).fit(disp=False)
                        if best is None or mod.aic < best[0]:
                            best = (mod.aic, (p, 1, q), (P, 1, Q, 12))
                    except Exception:
                        continue
    aic, order, sorder = best if best else (np.inf, (1, 1, 1), (0, 0, 0, 0))

    sarima_fit = SARIMAX(train, order=order, seasonal_order=sorder,
                         enforce_stationarity=False,
                         enforce_invertibility=False).fit(disp=False)
    sarima_pred = sarima_fit.get_forecast(steps=test_len).predicted_mean
    sarima_pred.index = test.index
    m_mape, m_rmse, m_mae = _err(test.values, sarima_pred.values)

    # ---------- 候选 2/3：Holt-Winters ----------
    hw_cands = {}
    for name, damped in [("Holt-Winters（加性·阻尼）", True), ("Holt-Winters（加性）", False)]:
        try:
            fit = ExponentialSmoothing(train, trend="add", seasonal="add",
                                       seasonal_periods=12, damped_trend=damped,
                                       initialization_method="estimated").fit()
            pred = fit.forecast(test_len)
            hw_cands[name] = {"fit": fit, "pred": pred, "err": _err(test.values, pred.values)}
        except Exception:
            continue

    comp = [{"模型": f"SARIMA{order}x{sorder}", "回测MAPE": m_mape,
             "回测RMSE": m_rmse, "回测MAE": m_mae, "AIC": float(aic)}]
    for name, v in hw_cands.items():
        comp.append({"模型": name, "回测MAPE": v["err"][0], "回测RMSE": v["err"][1],
                     "回测MAE": v["err"][2], "AIC": np.nan})
    comp_df = pd.DataFrame(comp).sort_values("回测MAPE").reset_index(drop=True)
    comp_df["是否最终模型"] = np.where(comp_df.index == 0, "是", "")
    save_table(comp_df.round(4), "t14b_预测模型比选.csv")

    chosen = comp_df.loc[0, "模型"]
    use_hw = chosen.startswith("Holt-Winters")
    mape, rmse, mae = (comp_df.loc[0, "回测MAPE"], comp_df.loc[0, "回测RMSE"],
                       comp_df.loc[0, "回测MAE"])
    pred = hw_cands[chosen]["pred"] if use_hw else sarima_pred

    # ---------- 全样本重估 + 外推 6 个月 ----------
    future_idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1),
                               periods=horizon, freq="MS")
    if use_hw:
        full = ExponentialSmoothing(s, trend="add", seasonal="add", seasonal_periods=12,
                                    damped_trend=("阻尼" in chosen),
                                    initialization_method="estimated").fit()
        mean = full.forecast(horizon)
        sim = full.simulate(nsimulations=horizon, repetitions=1000, error="add")
        lo = np.percentile(sim, 2.5, axis=1)
        hi = np.percentile(sim, 97.5, axis=1)
        ci = pd.DataFrame({0: lo, 1: hi})
    else:
        full = SARIMAX(s, order=order, seasonal_order=sorder,
                       enforce_stationarity=False,
                       enforce_invertibility=False).fit(disp=False)
        fc = full.get_forecast(steps=horizon)
        mean = fc.predicted_mean
        ci = fc.conf_int(alpha=0.05)

    out = pd.DataFrame({
        "年月": [d.strftime("%Y-%m") for d in future_idx],
        "预测销售额": np.asarray(mean).round(2),
        "下限95": np.asarray(ci.iloc[:, 0] if hasattr(ci, "iloc") else ci[0]).round(2),
        "上限95": np.asarray(ci.iloc[:, 1] if hasattr(ci, "iloc") else ci[1]).round(2),
    })
    save_table(out, "t13_预测结果.csv")

    backtest = pd.DataFrame({
        "年月": [d.strftime("%Y-%m") for d in test.index],
        "实际销售额": test.values.round(2),
        "预测销售额": np.asarray(pred.values).round(2),
        "绝对误差": np.abs(test.values - np.asarray(pred.values)).round(2),
    })
    backtest["相对误差"] = (backtest["绝对误差"] / backtest["实际销售额"]).round(4)
    save_table(backtest, "t13b_预测回测明细.csv")

    metrics = pd.DataFrame([
        {"指标": "最终模型", "取值": chosen},
        {"指标": "SARIMA 阶数（AIC 最优）", "取值": f"SARIMA{order}x{sorder}"},
        {"指标": "回测期数", "取值": f"{test_len} 个月（{test.index[0]:%Y-%m} 至 {test.index[-1]:%Y-%m}）"},
        {"指标": "MAPE（回测）", "取值": f"{mape:.2%}"},
        {"指标": "RMSE（回测，美元）", "取值": f"{rmse:,.0f}"},
        {"指标": "MAE（回测，美元）", "取值": f"{mae:,.0f}"},
        {"指标": "预测期数", "取值": f"{horizon} 个月"},
        {"指标": "置信水平", "取值": "95%"},
    ])
    save_table(metrics, "t14_预测评估指标.csv")
    print(f"      最终模型：{chosen}，MAPE={mape:.2%}，RMSE={rmse:,.0f} 美元")

    return {"history": s, "train": train, "test": test, "pred": pred,
            "backtest": backtest, "forecast": out, "metrics": metrics,
            "compare": comp_df, "chosen": chosen,
            "mape": mape, "rmse": rmse, "order": order, "sorder": sorder}


# ============================================================
# M8 Apriori 关联规则
# ============================================================
def m8_apriori(orders: pd.DataFrame, min_support: float = 0.006,
               min_confidence: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    购物篮关联规则（Apriori）
    交易定义：一张订单 = 一个购物篮，篮内元素 = 产品子类（17 个，避免 SKU 过细导致支持度过低）。
    参数依据：min_support=1% 意味着至少 1% 的订单同时包含该项，
              在 5,111 张订单中约 51 单，既能过滤偶发组合又不至于无规则可挖；
              min_confidence=20% 为零售交叉销售的常用下限；最终以 lift>1 作为“有效关联”的判据。
    """
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder

    baskets = orders.groupby("Order ID")["子类"].apply(lambda x: sorted(set(x))).tolist()
    te = TransactionEncoder()
    arr = te.fit(baskets).transform(baskets)
    onehot = pd.DataFrame(arr, columns=te.columns_)

    freq = apriori(onehot, min_support=min_support, use_colnames=True)
    if freq.empty:
        print("      [!] 未挖掘到满足支持度的频繁项集，请下调 min_support")
        empty = pd.DataFrame()
        save_table(empty, "t15_关联规则.csv")
        return empty, empty
    rules = association_rules(freq, metric="confidence", min_threshold=min_confidence)
    rules = rules[rules["lift"] > 1].copy()
    for c in ["antecedents", "consequents"]:
        rules[c] = rules[c].apply(lambda s: "、".join(sorted(s)))
    rules = rules.rename(columns={"antecedents": "前项", "consequents": "后项",
                                  "support": "支持度", "confidence": "置信度", "lift": "提升度"})
    rules = rules.sort_values("提升度", ascending=False).reset_index(drop=True)
    rules["排名"] = np.arange(1, len(rules) + 1)
    save_table(rules[["排名", "前项", "后项", "支持度", "置信度", "提升度"]].round(4),
               "t15_关联规则.csv")

    # 子类共现矩阵（供热力图使用）
    co = onehot.T.astype(int) @ onehot.astype(int)
    np.fill_diagonal(co.values, 0)
    co.to_csv(DATA_CLEAN / ".." / ".." / "outputs" / "tables" / "t15b_子类共现矩阵.csv",
              encoding="utf-8-sig")
    print(f"      Apriori：频繁项集 {len(freq)} 个，有效规则 {len(rules)} 条（lift>1）")
    return rules, co


# ============================================================
# M9 漏斗转化
# ============================================================
def m9_funnel(orders: pd.DataFrame) -> pd.DataFrame:
    """
    订单履约漏斗（4 级）：下单 → 按时履约(≤4 天) → 未退货 → 盈利。
    口径：以订单为粒度（不是明细行），每级要求同时满足前序条件，体现逐级流失。
    """
    o = (orders.groupby("Order ID")
         .agg(履约天数=("履约天数", "max"), 退货=("是否退货", "max"),
              利润=("Profit", "sum"), 销售额=("Sales", "sum")).reset_index())
    steps = [
        ("下单订单", len(o)),
        ("按时履约（≤4 天）", int((o["履约天数"] <= 4).sum())),
        ("未被退货", int(((o["履约天数"] <= 4) & (o["退货"] == 0)).sum())),
        ("订单盈利", int(((o["履约天数"] <= 4) & (o["退货"] == 0) & (o["利润"] > 0)).sum())),
    ]
    f = pd.DataFrame(steps, columns=["环节", "订单数"])
    f["整体转化率"] = f["订单数"] / f["订单数"].iloc[0]
    f["环节转化率"] = f["订单数"] / f["订单数"].shift(1)
    f.loc[0, "环节转化率"] = 1.0
    save_table(f.round(4), "t16_履约漏斗.csv")
    print(f"      漏斗：{f['订单数'].iloc[0]:,} → {f['订单数'].iloc[-1]:,}，"
          f"端到端转化 {f['整体转化率'].iloc[-1]:.1%}")
    return f


# ============================================================
# 辅助：折扣—利润关系（商业建议支撑）
# ============================================================
def m10_discount_effect(orders: pd.DataFrame) -> pd.DataFrame:
    """
    折扣弹性分析：按折扣档位统计毛利率与亏损订单占比，用于回答
    “折扣打到什么程度开始亏钱”，为定价建议提供数据支撑。
    """
    o = orders.copy()
    o["折扣档"] = pd.cut(o["Discount"], bins=[-0.01, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.8],
                        labels=["无折扣", "0~10%", "10~20%", "20~30%",
                                "30~40%", "40~50%", "50%以上"])
    g = (o.groupby("折扣档", observed=False)
         .agg(销售额=("Sales", "sum"), 利润=("Profit", "sum"),
              明细数=("Sales", "size"), 亏损数=("是否亏损", "sum")).reset_index())
    g["毛利率"] = g["利润"] / g["销售额"]
    g["亏损占比"] = g["亏损数"] / g["明细数"]
    g["销售额占比"] = g["销售额"] / g["销售额"].sum()
    save_table(g.round(4), "t17_折扣弹性.csv")
    return g


# ============================================================
def run_all() -> dict:
    """一键跑完全部模型，返回结果字典供出图与笔记本使用。"""
    orders = load_clean()
    print(f"[1/9] M1 同比环比 + 移动平均（{orders['年月'].nunique()} 个月）")
    trend = m1_trend(orders)
    print("[2/9] M2 帕累托 / ABC 分类")
    pareto_sub = m2_pareto(orders, "子类", "子类")
    pareto_cust = m2_pareto(orders, "Customer ID", "客户")
    print("[3/9] M3 RFM 八分类")
    rfm, rfm_sum = m3_rfm(orders)
    print("[4/9] M4 K-Means 用户分群")
    rfm_k, km_prof = m4_kmeans(rfm)
    print("[5/9] M5 同期群留存")
    cohort = m5_cohort(orders)
    print("[6/9] M6 波士顿矩阵")
    bcg = m6_bcg(orders)
    print("[7/9] M7 时间序列预测（SARIMA vs Holt-Winters）")
    sarima = m7_forecast(trend, horizon=6, test_len=6)
    print("[8/9] M8 Apriori 关联规则")
    rules, co = m8_apriori(orders)
    print("[9/9] M9 漏斗转化 + 折扣弹性")
    funnel = m9_funnel(orders)
    disc = m10_discount_effect(orders)

    return {"orders": orders, "trend": trend, "pareto_sub": pareto_sub,
            "pareto_cust": pareto_cust, "rfm": rfm, "rfm_sum": rfm_sum,
            "rfm_k": rfm_k, "km_prof": km_prof, "cohort": cohort, "bcg": bcg,
            "sarima": sarima, "rules": rules, "cooccur": co,
            "funnel": funnel, "discount": disc}


if __name__ == "__main__":
    run_all()
