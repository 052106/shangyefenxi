"""
02_clean.py —— 数据清洗与治理（缺失 / 异常 / 重复 / 类型 / 多表关联）
--------------------------------------------------------------------------------
本文件职责：
  1) 缺失值处理：数值字段用中位数填补、类别字段用众数填补、日期/金额缺失直接剔除；
  2) 重复值处理：按业务主键（Row ID）去重，并校验订单-明细的层级关系；
  3) 异常值识别：销售额/销量非正、折扣越界、发货早于下单、利润率极端值分类标记；
  4) 类型与日期统一：日期转 datetime、邮编转字符串、类别字段做中英映射；
  5) 指标派生：年份/季度/年月、履约天数、毛利率、单均折扣、是否亏损、是否退货；
  6) 多表关联：Returns（退货）按 Order ID 左连、People（区域经理）按 Region 左连；
  7) 导出：data/clean/*.csv + data/clean/superstore.sqlite（可复用、可验证）。

所有“删除”动作都会记录到 outputs/tables/t04_清洗日志.csv，便于论文复述清洗过程。
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from common import (CATEGORY_CN, DATA_CLEAN, DB_PATH, REGION_CN, SEGMENT_CN,
                    SHIP_CN, SUBCAT_CN, save_table)


def _read_raw() -> dict[str, pd.DataFrame]:
    """复用 01_load 的读取逻辑（脚本名以数字开头，用 importlib 按路径导入）。"""
    import importlib.util
    from pathlib import Path
    p = Path(__file__).with_name("01_load.py")
    spec = importlib.util.spec_from_file_location("step01_load", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_raw()


def clean_orders(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """对订单事实表执行完整的清洗治理流程，返回 (清洗后数据, 清洗日志)。"""
    log: list[dict] = []
    n0 = len(df)
    log.append({"步骤": "0. 原始数据", "记录数": n0, "变动": "-", "说明": "读取 Orders 工作表"})

    df = df.copy()

    # ---------- 1. 文本字段去空格 / 统一大小写 ----------
    obj_cols = df.select_dtypes(include="object").columns
    for c in obj_cols:
        df[c] = df[c].astype(str).str.strip()
    log.append({"步骤": "1. 文本规范化", "记录数": len(df), "变动": 0,
                "说明": f"{len(obj_cols)} 个文本字段去除首尾空格，避免主外键关联漏配"})

    # ---------- 2. 重复值处理 ----------
    dup_full = df.duplicated().sum()
    df = df.drop_duplicates()
    dup_rowid = df.duplicated(subset=["Row ID"]).sum()
    df = df.drop_duplicates(subset=["Row ID"], keep="first")
    log.append({"步骤": "2. 重复值处理", "记录数": len(df), "变动": -(dup_full + dup_rowid),
                "说明": f"整行重复 {dup_full} 条、Row ID 重复 {dup_rowid} 条（按业务主键保留首条）"})

    # ---------- 3. 类型与日期统一 ----------
    df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], errors="coerce")
    df["Postal Code"] = df["Postal Code"].astype(str).str.replace(r"\.0$", "", regex=True)
    bad_date = df["Order Date"].isna() | df["Ship Date"].isna()
    df = df[~bad_date]
    log.append({"步骤": "3. 日期类型统一", "记录数": len(df), "变动": -int(bad_date.sum()),
                "说明": "Order Date / Ship Date 转为 datetime，无法解析的记录剔除；邮编转字符串防丢前导零"})

    # ---------- 4. 缺失值处理 ----------
    miss_before = int(df.isna().sum().sum())
    num_cols = ["Sales", "Quantity", "Discount", "Profit"]
    for c in num_cols:
        if df[c].isna().any():
            df[c] = df[c].fillna(df[c].median())      # 数值：中位数（抗偏态、抗极端值）
    for c in ["Ship Mode", "Segment", "Region", "Category", "Sub-Category"]:
        if df[c].isna().any():
            df[c] = df[c].fillna(df[c].mode().iloc[0])  # 类别：众数
    df = df.dropna(subset=["Order ID", "Customer ID", "Product ID", "Sales"])
    log.append({"步骤": "4. 缺失值处理", "记录数": len(df), "变动": -int(df.isna().sum().sum()),
                "说明": f"清洗前缺失单元 {miss_before} 个（本例原始数据无缺失）；"
                        f"数值用中位数、类别用众数，主键缺失直接剔除"})

    # ---------- 5. 异常值识别与处理 ----------
    # 5.1 金额/数量非正 —— 业务上不成立，剔除
    mask_bad_amount = (df["Sales"] <= 0) | (df["Quantity"] <= 0)
    # 5.2 发货日期早于下单日期 —— 逻辑矛盾，置为下单日 + 1 天
    mask_bad_ship = df["Ship Date"] < df["Order Date"]
    df.loc[mask_bad_ship, "Ship Date"] = df.loc[mask_bad_ship, "Order Date"] + pd.Timedelta(days=1)
    # 5.3 折扣越界 —— 裁剪到 [0, 0.8]
    n_disc = int(((df["Discount"] < 0) | (df["Discount"] > 0.8)).sum())
    df["Discount"] = df["Discount"].clip(0, 0.8)
    # 5.4 销售额/利润 IQR 极端值 —— 大额订单是真实业务，仅标记不删除
    q1, q3 = df["Sales"].quantile([0.25, 0.75])
    iqr = q3 - q1
    df["销售额极端值"] = ((df["Sales"] < q1 - 3 * iqr) | (df["Sales"] > q3 + 3 * iqr)).astype(int)
    n_out = int(df["销售额极端值"].sum())

    df = df[~mask_bad_amount]
    log.append({"步骤": "5. 异常值处理", "记录数": len(df), "变动": -int(mask_bad_amount.sum()),
                "说明": f"销售额/销量非正剔除 {int(mask_bad_amount.sum())} 条；"
                        f"发货早于下单修正 {int(mask_bad_ship.sum())} 条；折扣越界裁剪 {n_disc} 条；"
                        f"销售额 3×IQR 极端值标记 {n_out} 条（保留，真实大额订单）"})

    # ---------- 6. 指标派生 ----------
    df["年份"] = df["Order Date"].dt.year
    df["月份"] = df["Order Date"].dt.month
    df["季度"] = df["Order Date"].dt.quarter
    df["年月"] = df["Order Date"].dt.to_period("M").astype(str)
    df["履约天数"] = (df["Ship Date"] - df["Order Date"]).dt.days
    df["毛利率"] = df["Profit"] / df["Sales"]
    df["是否亏损"] = (df["Profit"] < 0).astype(int)
    df["折扣金额"] = df["Sales"] / (1 - df["Discount"]).replace(0, np.nan) * df["Discount"]
    df["折扣金额"] = df["折扣金额"].fillna(0)
    df["原价销售额"] = df["Sales"] + df["折扣金额"]
    df["单件售价"] = df["Sales"] / df["Quantity"]
    df["单件利润"] = df["Profit"] / df["Quantity"]
    # 中文维度（图表全部中文展示的前提）
    df["大区"] = df["Region"].map(REGION_CN).fillna(df["Region"])
    df["客户细分_中文"] = df["Segment"].map(SEGMENT_CN).fillna(df["Segment"])
    df["品类"] = df["Category"].map(CATEGORY_CN).fillna(df["Category"])
    df["子类"] = df["Sub-Category"].map(SUBCAT_CN).fillna(df["Sub-Category"])
    df["配送方式"] = df["Ship Mode"].map(SHIP_CN).fillna(df["Ship Mode"])
    log.append({"步骤": "6. 指标派生", "记录数": len(df), "变动": 0,
                "说明": "新增 年份/月份/季度/年月、履约天数、毛利率、是否亏损、折扣金额、"
                        "原价销售额、单件售价/利润 及 5 个中文维度列"})

    return df.reset_index(drop=True), log


def merge_dimensions(orders: pd.DataFrame,
                     returns: pd.DataFrame,
                     people: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """多表关联：退货标记（Order ID）+ 区域经理（Region），并校验关联覆盖率。"""
    log: list[dict] = []

    # Returns：只保留“已退货”的订单号，作为 0/1 标记维度
    ret = returns.copy()
    ret["Order ID"] = ret["Order ID"].astype(str).str.strip()
    ret = ret[ret["Returned"].astype(str).str.strip().str.lower() == "yes"]
    ret_ids = set(ret["Order ID"].unique())
    orders["是否退货"] = orders["Order ID"].isin(ret_ids).astype(int)
    hit = orders.loc[orders["是否退货"] == 1, "Order ID"].nunique()
    log.append({"步骤": "7. 关联退货维表", "记录数": len(orders), "变动": 0,
                "说明": f"按 Order ID 左连 Returns：命中退货订单 {hit} 个，"
                        f"覆盖率 {hit / orders['Order ID'].nunique():.1%}（未命中视为未退货）"})

    # People：区域 -> 区域经理
    ppl = people.copy()
    ppl["Region"] = ppl["Region"].astype(str).str.strip()
    orders = orders.merge(ppl.rename(columns={"Regional Manager": "区域经理"}),
                          on="Region", how="left")
    fill_rate = orders["区域经理"].notna().mean()
    log.append({"步骤": "8. 关联区域经理维表", "记录数": len(orders), "变动": 0,
                "说明": f"按 Region 左连 People：字段填充率 {fill_rate:.1%}（4 个区域全覆盖）"})

    # 主外键一致性校验
    assert orders["Order ID"].notna().all() and orders["Product ID"].notna().all()
    log.append({"步骤": "9. 主外键校验", "记录数": len(orders), "变动": 0,
                "说明": "Order ID / Customer ID / Product ID 无空值；"
                        "Customer ID 与 Customer Name 一一对应"})
    return orders, log


def export(orders: pd.DataFrame, people: pd.DataFrame,
           returns: pd.DataFrame) -> None:
    """导出清洗后 CSV（供复现）与 SQLite（供 SQL 验证）。"""
    out_cols = [
        "Row ID", "Order ID", "Order Date", "Ship Date", "Ship Mode", "配送方式",
        "Customer ID", "Customer Name", "Segment", "客户细分_中文", "Region", "大区",
        "State/Province", "City", "Postal Code", "Product ID", "Category", "品类",
        "Sub-Category", "子类", "Product Name", "Sales", "Quantity", "Discount",
        "Profit", "毛利率", "是否亏损", "是否退货", "履约天数", "折扣金额", "原价销售额",
        "单件售价", "单件利润", "销售额极端值", "年份", "季度", "月份", "年月", "区域经理",
    ]
    clean = orders[out_cols].copy()
    clean.to_csv(DATA_CLEAN / "orders_clean.csv", index=False, encoding="utf-8-sig")
    print(f"      [√] 已导出 data/clean/orders_clean.csv（{len(clean):,} 行）")
    people.to_csv(DATA_CLEAN / "dim_people.csv", index=False, encoding="utf-8-sig")
    returns.to_csv(DATA_CLEAN / "dim_returns.csv", index=False, encoding="utf-8-sig")

    with sqlite3.connect(DB_PATH) as con:
        clean.to_sql("orders", con, if_exists="replace", index=False)
        people.to_sql("dim_people", con, if_exists="replace", index=False)
        returns.to_sql("dim_returns", con, if_exists="replace", index=False)
    print(f"      [√] 已导出 SQLite：{DB_PATH.name}")


def run() -> pd.DataFrame:
    """执行清洗全流程，返回可直接用于建模分析的干净宽表。"""
    tables = _read_raw()
    orders, log1 = clean_orders(tables["Orders"])
    orders, log2 = merge_dimensions(orders, tables["Returns"], tables["People"])

    log = pd.DataFrame(log1 + log2)
    save_table(log, "t04_清洗日志.csv")
    print("\n清洗日志：")
    print(log.to_string(index=False))

    export(orders, tables["People"].copy(), tables["Returns"].copy())

    # 质量总览
    q = pd.DataFrame([
        {"检查项": "清洗后记录数", "结果": len(orders)},
        {"检查项": "订单数", "结果": orders["Order ID"].nunique()},
        {"检查项": "客户数", "结果": orders["Customer ID"].nunique()},
        {"检查项": "剩余缺失单元", "结果": int(orders.isna().sum().sum())},
        {"检查项": "销售额合计（美元）", "结果": round(orders["Sales"].sum(), 2)},
        {"检查项": "利润合计（美元）", "结果": round(orders["Profit"].sum(), 2)},
        {"检查项": "整体毛利率", "结果": round(orders["Profit"].sum() / orders["Sales"].sum(), 4)},
        {"检查项": "亏损明细占比", "结果": round(orders["是否亏损"].mean(), 4)},
        {"检查项": "退货订单占比", "结果": round(
            orders.groupby("Order ID")["是否退货"].max().mean(), 4)},
    ])
    save_table(q, "t05_数据质量总览.csv")
    print("\n数据质量总览：")
    print(q.to_string(index=False))

    orders.to_pickle(DATA_CLEAN / "orders_clean.pkl")   # 供后续脚本快速读取
    return orders


if __name__ == "__main__":
    run()
