"""阶段 16：用年鉴2025 的城镇非私营/私营两行，对 2024 年度封顶基数做「有校验的估算」。

背景：年鉴2025 起不再收录「全市法人单位从业人员年末人数及工资情况」表，
3-13 改为「城镇非私营、私营单位就业人员年末人数及工资情况(2024年)」，只有两行、没有合计行。

但 2023 年的官方表（年鉴2024 表 3-14）显示：城镇非私营 + 城镇私营 = 法人单位全口径
（人数 755.6 + 271.9 = 1027.5 万 = 合计 1027.4658706 万）。因此可用同样方法对 2024 年估算：

    平均工资 ≈ (城镇非私营工资总额 + 城镇私营工资总额) ÷ (城镇非私营人数 + 城镇私营人数)
            = (17426.3407 + 3476.25151) 亿元 × 1e8 ÷ (763.6452 + 320.4169) 万人 × 1e4

本脚本同时用 2023 年的官方数据验证该方法的误差（官方 188413 元），把方法、输入与偏差一起写入
parameters.yaml 的 derived_estimates —— **状态为 estimate-not-official**，仅供试算参考，
不得作为官方参数参与正式计算（计算侧仍需调用方显式指定基数）。
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import xlrd  # noqa: E402
import yaml  # noqa: E402
from common import fetch, save_binary, sha256  # noqa: E402

REPO = pathlib.Path("/Users/abaaba/workspace/projects/labor_lawyer")
REGION = "municipalities/beijing"
BASE = "statistics"
PARAMS = REPO / "regions" / REGION / BASE / "parameters.yaml"
YB = "https://hgk.tjj.beijing.gov.cn/{year}tjnj/tjnj/zk/"


def read_rows(data: bytes) -> dict[str, tuple[float, float, float]]:
    """返回 {行名: (年末人数万人, 工资总额亿元, 平均工资元)}。"""
    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as fh:
        fh.write(data)
        path = fh.name
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    out = {}
    for r in range(sheet.nrows):
        name = re.sub(r"\s+", "", str(sheet.cell_value(r, 0)))
        nums = [sheet.cell_value(r, c) for c in range(1, sheet.ncols)]
        nums = [n for n in nums if isinstance(n, float)]
        if name and len(nums) >= 3:
            out[name] = (nums[0], nums[1], nums[-1])
    return out


def pick(rows: dict, prefix: str) -> tuple[float, float, float]:
    """按行名前缀取值：年鉴2025 为「城镇非私营单位」，年鉴2024 为「城镇非私营」（无「单位」）。"""
    for name, values in rows.items():
        if name.startswith(prefix):
            return values
    raise KeyError(f"表中未找到以「{prefix}」开头的行：{list(rows)}")


def estimate(rows: dict, prefixes: tuple[str, str]) -> Decimal:
    wage_total = sum(Decimal(str(pick(rows, k)[1])) for k in prefixes)     # 亿元
    headcount = sum(Decimal(str(pick(rows, k)[0])) for k in prefixes)      # 万人
    return (wage_total * Decimal(10 ** 8) / (headcount * Decimal(10 ** 4))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)


def main() -> int:
    keys = ("城镇非私营", "城镇私营")     # 前缀匹配，兼容两种行名写法
    # ① 年鉴2025 表 3-13（2024 年）——归档并估算
    url_2025 = YB.format(year=2025) + "html/C0313.xls"
    data_2025 = fetch(url_2025, referer=YB.format(year=2025) + "lefte.htm")
    save_binary(f"{BASE}/yearbook/2025-C0313.xls", data_2025,
                title="北京统计年鉴2025 · 3-13 城镇非私营、私营单位就业人员年末人数及工资情况(2024年)",
                topic=BASE, source_url=url_2025, download_url=url_2025,
                published_at="2025年", authority="北京市统计局、国家统计局北京调查总队",
                original_filename="C0313.xls", region=REGION,
                notes="年鉴2025 起法人单位口径表不再收录，本表为城镇非私营/私营两行口径")
    rows_2025 = read_rows(data_2025)
    print("年鉴2025 表 3-13 行名:", list(rows_2025))
    est_2024 = estimate(rows_2025, keys)

    # ② 用 2023 年官方表校验方法偏差
    path_2023 = REPO / "regions" / REGION / BASE / "yearbook/2024-C03-14.xls"
    official_2023 = None
    if path_2023.exists():
        rows_2023 = read_rows(path_2023.read_bytes())
        est_2023 = estimate(rows_2023, keys)
        official_2023 = int(rows_2023.get("合计", (0, 0, 0))[2])
        deviation = ((est_2023 - Decimal(official_2023)) / Decimal(official_2023) * 100).quantize(
            Decimal("0.01"))
        print(f"方法校验（2023 年）：估算 {est_2023} vs 官方 {official_2023} → 偏差 {deviation}%")
    else:
        est_2023, deviation = None, None
        print("未找到 2024-C03-14.xls，跳过方法校验")

    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    series = next(s for s in params["series"] if s["id"] == "beijing_legal_entity_avg_wage")
    series["derived_estimates"] = [{
        "year": 2024,
        "annual": int(est_2024),
        "monthly": int((est_2024 / 12).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "status": "estimate-not-official",
        "method": "（城镇非私营单位工资总额 + 城镇私营单位工资总额）÷（两口径年末人数之和）；"
                  "2023 年官方表显示两者人数之和等于法人单位全口径",
        "inputs": {
            "城镇非私营单位": dict(zip(("年末人数万人", "工资总额亿元", "平均工资元"), rows_2025["城镇非私营单位"])),
            "城镇私营单位": dict(zip(("年末人数万人", "工资总额亿元", "平均工资元"), rows_2025["城镇私营单位"])),
            "source_url": url_2025,
            "source_file": "2025-C0313.xls",
            "source_file_sha256": sha256(data_2025),
        },
        "validation": ({
            "year": 2023, "estimated": int(est_2023), "official": official_2023,
            "deviation_pct": str(deviation),
            "source_file": "2024-C03-14.xls",
        } if official_2023 else None),
        "caveat": "估算值，非官方发布；正式出具意见前应以统计部门发布的数据为准"
                  "（或向社保经办/12333核实）。计算侧对该年度默认拒绝，需调用方显式指定基数。",
    }]
    series.setdefault("gaps", []).append(
        f"2024 年度官方数值未发布；参数表提供估算 {int(est_2024)} 元/年"
        f"（方法经 2023 年数据校验，偏差 {deviation}%），状态 estimate-not-official，不得直接用于正式计算。")

    content = ("# 北京劳动仲裁计算参数（由 tools/crawl 生成，勿手改数值）\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(f"{BASE}/parameters.yaml", content,
                title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic=BASE,
                source_url=url_2025,
                authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
                original_filename="parameters.yaml", region=REGION,
                notes=f"阶段 16：新增 2024 年度估算 {int(est_2024)} 元/年（estimate-not-official）")
    print(f"2024 年度估算：{est_2024} 元/年（月 {int((est_2024 / 12).quantize(Decimal('1')))}）"
          f"→ 三倍封顶 {(est_2024 / 12 * 3).quantize(Decimal('0.01'))} 元/月")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
