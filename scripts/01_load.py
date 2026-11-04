"""
01_load.py —— 数据获取与加载（合规：官方 XLSX 一次性下载文件，非爬虫）
--------------------------------------------------------------------------------
本文件职责：
  1) 从 data/raw/sample_-_superstore.xls 读取 3 张工作表（Orders 事实表、
     People 区域经理维表、Returns 退货维表），全程只读，不修改原始文件；
  2) 输出「数据源体检报告」：行数/列数/字段类型/缺失率/重复行，写入 outputs/tables/；
  3) 输出字段字典 data_dictionary.csv（论文第 2 章字段说明直接引用）；
  4) 供 02_clean.py 与 notebook 调用。

合规声明：数据为 Tableau 官方公开示例数据集，通过官网一次性文件下载获得，
         未使用 Scrapy/Selenium/requests 等任何网页抓取手段。
"""

from __future__ import annotations

import pandas as pd

from common import DATA_CLEAN, OUT_TAB, RAW_XLS, save_table

# 字段中文说明（论文与 README 共用）
FIELD_DICT = {
    "Row ID": ("行号", "整数", "记录唯一序号，1~10194"),
    "Order ID": ("订单号", "字符串", "订单主键，一单可含多行明细"),
    "Order Date": ("下单日期", "日期", "订单创建日期，2023-01-03 至 2026-12-30"),
    "Ship Date": ("发货日期", "日期", "订单发货日期，用于计算履约时长"),
    "Ship Mode": ("配送方式", "类别", "标准/二级/一级/当日达四种"),
    "Customer ID": ("客户编号", "字符串", "客户主键，共 804 位客户"),
    "Customer Name": ("客户姓名", "字符串", "客户名称"),
    "Segment": ("客户细分", "类别", "消费者/企业客户/家庭办公"),
    "Country/Region": ("国家/地区", "类别", "全量为美国"),
    "City": ("城市", "字符串", "542 个城市"),
    "State/Province": ("州/省", "字符串", "59 个州，可用于地理分析"),
    "Postal Code": ("邮编", "字符串", "邮寄编码"),
    "Region": ("销售大区", "类别", "东部/西部/中部/南部"),
    "Product ID": ("产品编号", "字符串", "产品主键，共 1862 个 SKU"),
    "Category": ("产品大类", "类别", "办公用品/家具/技术产品"),
    "Sub-Category": ("产品子类", "类别", "17 个子类，用于结构分析"),
    "Product Name": ("产品名称", "字符串", "商品全称"),
    "Sales": ("销售额", "浮点", "该行折后销售额（美元），已扣折扣"),
    "Quantity": ("销量", "整数", "该行购买件数"),
    "Discount": ("折扣率", "浮点", "0~0.8 的折扣比例"),
    "Profit": ("利润", "浮点", "该行利润（美元），可为负"),
}


def load_raw() -> dict[str, pd.DataFrame]:
    """读取原始 Excel 的 3 张表，返回 {'Orders':df, 'People':df, 'Returns':df}。"""
    if not RAW_XLS.exists():
        raise FileNotFoundError(f"未找到原始数据文件：{RAW_XLS}")
    xls = pd.ExcelFile(RAW_XLS)
    tables = {name: xls.parse(name) for name in xls.sheet_names}
    print(f"[1/3] 已读取原始文件：{RAW_XLS.name}")
    for name, df in tables.items():
        print(f"      - 工作表 {name:<9} 规模 {df.shape[0]:>6} 行 × {df.shape[1]:>2} 列")
    return tables


def profile(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """生成数据体检报告：每张表逐个字段统计类型、缺失率、唯一值数。"""
    rows = []
    for name, df in tables.items():
        for col in df.columns:
            s = df[col]
            rows.append({
                "工作表": name,
                "字段": col,
                "数据类型": str(s.dtype),
                "非空数": int(s.notna().sum()),
                "缺失数": int(s.isna().sum()),
                "缺失率": round(float(s.isna().mean()), 4),
                "唯一值数": int(s.nunique(dropna=True)),
            })
    return pd.DataFrame(rows)


def data_dictionary() -> pd.DataFrame:
    """输出字段字典（中文名、类型、业务含义），供论文与 README 引用。"""
    return pd.DataFrame(
        [{"字段": k, "中文名称": v[0], "类型": v[1], "业务含义": v[2]}
         for k, v in FIELD_DICT.items()]
    )


def run() -> dict[str, pd.DataFrame]:
    """完整执行加载环节：读表 -> 体检 -> 导出报告与字段字典 -> 返回内存 DataFrame。"""
    tables = load_raw()
    orders = tables["Orders"]

    print("[2/3] 数据体检")
    rep = profile(tables)
    save_table(rep, "t01_数据体检报告.csv")

    # 关键规模指标（论文“数据规模”小节引用）
    kpi = pd.DataFrame([
        {"指标": "订单明细行数", "数值": f"{len(orders):,}", "单位": "行"},
        {"指标": "唯一订单数", "数值": f"{orders['Order ID'].nunique():,}", "单位": "单"},
        {"指标": "唯一客户数", "数值": f"{orders['Customer ID'].nunique():,}", "单位": "位"},
        {"指标": "唯一产品数", "数值": f"{orders['Product ID'].nunique():,}", "单位": "个"},
        {"指标": "产品子类数", "数值": str(orders["Sub-Category"].nunique()), "单位": "类"},
        {"指标": "城市数", "数值": str(orders["City"].nunique()), "单位": "个"},
        {"指标": "州/省数", "数值": str(orders["State/Province"].nunique()), "单位": "个"},
        {"指标": "时间跨度", "数值": str((orders["Order Date"].max()
                                        - orders["Order Date"].min()).days), "单位": "天"},
        {"指标": "退货订单数", "数值": str(len(tables["Returns"])), "单位": "单"},
        {"指标": "销售总额", "数值": f"{orders['Sales'].sum():,.2f}", "单位": "美元"},
        {"指标": "利润总额", "数值": f"{orders['Profit'].sum():,.2f}", "单位": "美元"},
        {"指标": "整体毛利率", "数值": f"{orders['Profit'].sum() / orders['Sales'].sum():.2%}",
         "单位": "%"},
    ])
    save_table(kpi, "t02_数据规模指标.csv")
    print(kpi.to_string(index=False))

    print("[3/3] 导出字段字典")
    save_table(data_dictionary(), "t03_字段字典.csv")

    # 合规声明（2.1 第 6 条要求：名称、URL、获取方式、日期、授权）
    notice = f"""# 数据来源合规声明

| 项目 | 说明 |
| --- | --- |
| 数据源名称 | Sample – Superstore（Tableau 官方示例数据集） |
| 提供方 | Tableau Software (Salesforce) |
| 官方地址 | https://www.tableau.com/products/trial/sample-data （官方示例工作簿随附 XLSX） |
| 获取方式 | 官方一次性文件下载（white-list 第 1 类：官方提供的下载文件），**未使用任何爬虫技术** |
| 本地文件 | data/raw/sample_-_superstore.xls |
| 获取日期 | 2026-11-04 |
| 数据规模 | 订单明细 {len(orders):,} 行 × {orders.shape[1]} 列；订单 {orders['Order ID'].nunique():,} 个；客户 {orders['Customer ID'].nunique()} 位 |
| 时间范围 | {orders['Order Date'].min():%Y-%m-%d} 至 {orders['Order Date'].max():%Y-%m-%d} |
| 授权 / License | Tableau 官方示例数据，允许用于学习、教学与演示；原始数据仅作分析用途，未再分发原始文件 |
| 使用限制 | 本项目全部图表由 Python（Matplotlib / Seaborn / Pyecharts）生成，**未使用 Tableau、Power BI、FineBI 等 BI 软件** |

> 说明：该数据集为公开教学示例数据，客户姓名为脱敏示例值，不含真实个人隐私信息。
"""
    (DATA_CLEAN.parent / ".." / "docs" / "数据来源合规声明.md").resolve().write_text(
        notice, encoding="utf-8")
    print("      [√] 已生成 docs/数据来源合规声明.md")
    return tables


if __name__ == "__main__":
    run()
