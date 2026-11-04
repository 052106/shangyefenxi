"""
run_all.py —— 一键复现入口
--------------------------------------------------------------------------------
本文件作用：按依赖顺序依次执行 01~06 全部脚本，从原始 Excel 一路复现到
            清洗数据、模型结果表、25 张图表、2 个交互大屏与期末论文。

用法：
    conda activate business_analysis
    python run_all.py            # 全流程（约 3 分钟，含 SARIMA 网格搜索）
    python run_all.py --fast     # 跳过 SARIMA 网格，仅用已有结果表重绘图表

复现结果：
    data/clean/*.csv|*.sqlite     清洗数据
    outputs/tables/t*.csv         17 张模型结果表
    outputs/figures/fig*.png      25 张图表（fig01–fig25）
    dashboard/*.html              2 个交互大屏
    docs/*.docx                   期末论文
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

STEPS = [
    ("01_load.py", "读取原始 Excel 三表 + 数据体检 + 合规声明"),
    ("02_clean.py", "清洗治理 + 多维派生 + 导出 CSV/SQLite"),
    ("03_analysis.py", "7 类商业分析模型（9 个模型）"),
    ("04_visuals.py", "14 张模板复现 + 10 张业务模型图"),
    ("05_dashboard.py", "暗色交互大屏（ECharts 联动版，单文件离线可用）"),
    ("06_paper.py", "期末论文 docx + 大屏布局示意图"),
]


def run_step(filename: str, desc: str) -> None:
    """按文件路径加载并执行脚本的 run()/run_all()。"""
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"step_{filename[:2]}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    t0 = time.time()
    if filename.startswith("03"):
        mod.run_all()
    elif callable(getattr(mod, "run", None)):
        mod.run()
    elif callable(getattr(mod, "run_all", None)):
        mod.run_all()
    # 06_paper.py 在模块导入时即完成生成，无需再调用具体函数
    print(f"  ✓ {filename:<18} 完成，用时 {time.time() - t0:.1f}s —— {desc}\n")


def main() -> None:
    fast = "--fast" in sys.argv
    print("=" * 74)
    print(" Sample–Superstore 商业数据分析项目 · 一键复现")
    print(f" 项目根目录：{ROOT}")
    print("=" * 74)
    total = time.time()
    for filename, desc in STEPS:
        if fast and filename.startswith("03"):
            print(f"  - 跳过 {filename}（--fast 模式，直接复用已有结果表）\n")
            continue
        run_step(filename, desc)

    # 汇总产物
    figs = sorted((ROOT / "outputs" / "figures").glob("*.png"))
    tabs = sorted((ROOT / "outputs" / "tables").glob("*.csv"))
    dash = sorted((ROOT / "dashboard").glob("*.html"))
    docs = sorted((ROOT / "docs").glob("*.docx"))
    print("=" * 74)
    print(f" 完成！总用时 {time.time() - total:.1f}s")
    print(f" 图表 {len(figs)} 张 → outputs/figures/")
    print(f" 结果表 {len(tabs)} 张 → outputs/tables/")
    print(f" 交互大屏 {len(dash)} 个 → dashboard/")
    print(f" 论文 {len(docs)} 份 → docs/")
    print("=" * 74)


if __name__ == "__main__":
    main()
