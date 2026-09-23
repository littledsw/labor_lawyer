"""阶段 22：2025 年度封顶基数的「有校验的估算」（官方原件归档 + derived_estimates）。

背景（与 stage16 同源）：年鉴 2025/2026 都不再收录「全市法人单位从业人员年末人数及工资情况」表，
官方改发「城镇非私营、私营单位就业人员年末人数及工资情况」两行口径。2024 年度已由 stage16 估算。

2026 年度的官方取数路径由北京市统计局在 2026-01-05 的**年度统计资料发布计划**给出：
「统计数据 > 统计部门发布计划 > 年度统计资料 > 2026年度统计资料 > 6月份」链接到发布件 zip
（P020260625381701456879.zip，2026-06-25）。发布件内含 2025 年度两行数据：

    项目            就业人员年末人数(万人)  就业人员工资总额(亿元)  就业人员平均工资(元)
    城镇非私营单位        739.6                17300.1              232740
    城镇私营单位          327.1                 3638                110514

估算方法（与 2023 年官方表验证过的方法一致：两口径人数之和 = 法人单位全口径）：

    平均工资 ≈ (非私营工资总额 + 私营工资总额) ÷ (非私营人数 + 私营人数)
            = (17300.1 + 3638) 亿元 × 1e8 ÷ (739.6 + 327.1) 万人 × 1e4
            = 196289 元/年（月 16357、三倍封顶 49072.25 元/月）

状态一律 **estimate-not-official**：计算侧对该年度默认拒绝，需调用方显式指定基数。
本脚本幂等：重复执行只替换 2025 年度的估算条目，不产生重复。
"""
from __future__ import annotations

import pathlib
import re
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402
from common import REPO, fetch, html_to_md, save_binary, save_md, sha256  # noqa: E402

REGION = "municipalities/beijing"
BASE = "statistics"
PARAMS = REPO / "regions" / REGION / BASE / "parameters.yaml"
PLAN_PAGE = ("https://tjj.beijing.gov.cn/tjsj_31433/tjbmfbjh/ndtjzl_31437/"
             "2026ndtjzl/202601/t20260105_4400088.html")
ZIP_URL = ("https://tjj.beijing.gov.cn/tjsj_31433/tjbmfbjh/ndtjzl_31437/"
           "2026ndtjzl/202601/P020260625381701456879.zip")
DATA_YEAR = 2025
# 前缀匹配：发布件为「城镇非私营单位」，年鉴 2024 表为「城镇非私营」（无「单位」）
PREFIXES = ("城镇非私营", "城镇私营")
COLUMNS = ("年末人数万人", "工资总额亿元", "平均工资元")


# ------------------------------------------------------------------ xlsx 解析
def read_xlsx_rows(data: bytes, table_hint: str) -> dict[str, tuple[Decimal, Decimal, Decimal]]:
    """无第三方依赖地读 xlsx（zipfile + 正则），返回 {行名: (人数, 工资总额, 平均工资)}。

    只取数值单元格；表头行按「项 目」识别，行名取第一列文本。
    """
    with zipfile.ZipFile(BytesIO(data)) as z:
        names = z.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            raw = z.read("xl/sharedStrings.xml").decode("utf-8")
            shared = [re.sub(r"<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", raw, re.S)]
        sheet = z.read("xl/worksheets/sheet1.xml").decode("utf-8")

    def text(value: str, attrs: str) -> str:
        return shared[int(value)] if 't="s"' in attrs else value

    rows: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
    for row_xml in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        label, nums = "", []
        for ref, attrs, value in re.findall(
                r'<c r="([A-Z]+)\d+"([^>]*)>(?:<v>([^<]*)</v>)?', row_xml):
            if value is None:
                continue
            if ref == "A":
                label = re.sub(r"\s+", "", text(value, attrs))
            else:
                try:
                    nums.append(Decimal(text(value, attrs)))
                except Exception:  # noqa: BLE001  非数值单元格直接跳过
                    continue
        if label and len(nums) >= 3:
            rows[label] = (nums[0], nums[1], nums[-1])
    if not rows:
        raise SystemExit(f"未从发布件解析出数据行（{table_hint}）")
    return rows


def pick(rows: dict, prefix: str) -> tuple[str, tuple[Decimal, Decimal, Decimal]]:
    for name, values in rows.items():
        if name.startswith(prefix):
            return name, values
    raise KeyError(f"表中未找到以「{prefix}」开头的行：{list(rows)}")


def estimate(rows: dict) -> Decimal:
    wage_total = sum(pick(rows, k)[1][1] for k in PREFIXES)      # 亿元
    headcount = sum(pick(rows, k)[1][0] for k in PREFIXES)       # 万人
    return (wage_total * Decimal(10 ** 8) / (headcount * Decimal(10 ** 4))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)


def validation_from_yearbook() -> dict | None:
    """沿用 stage16 的方法校验：用 2023 年官方表（年鉴2024 表 3-14）反算偏差。

    该表同时含两行口径与「合计」行（法人单位口径官方值 188413），可量化方法误差。
    """
    path = REPO / "regions" / REGION / BASE / "yearbook/2024-C03-14.xls"
    if not path.exists():
        print("  ! 缺少 yearbook/2024-C03-14.xls，跳过方法校验")
        return None
    import xlrd

    sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
    rows: dict[str, tuple[Decimal, Decimal, Decimal]] = {}
    for r in range(sheet.nrows):
        name = re.sub(r"\s+", "", str(sheet.cell_value(r, 0)))
        nums = [Decimal(str(v)) for v in (sheet.cell_value(r, c) for c in range(1, sheet.ncols))
                if isinstance(v, float)]
        if name and len(nums) >= 3:
            rows[name] = (nums[0], nums[1], nums[-1])
    official = int(rows["合计"][2])
    got = int(estimate(rows))
    deviation = ((Decimal(got) - Decimal(official)) / Decimal(official) * 100).quantize(Decimal("0.01"))
    print(f"  方法校验（2023 年官方表）：估算 {got} vs 官方 {official} → 偏差 {deviation}%")
    return {"year": 2023, "estimated": got, "official": official,
            "deviation_pct": str(deviation), "source_file": "2024-C03-14.xls"}


def plan_page_table(md: str) -> str:
    """从发布计划页的转换结果里截出「年度统计资料发布计划」表格段（含各发布件链接）。

    官方页含大量导航；这里只保留与本阶段取数路径相关的片段，并注明为摘录。
    """
    lines, keep, grab = md.splitlines(), [], False
    for line in lines:
        if "年度统计资料发布计划" in line:
            grab = True
        if grab:
            keep.append(line)
        if grab and line.strip().startswith("注：2"):
            break
    return "\n".join(keep).strip() if keep else md.strip()


def decode_zip_name(name: str) -> str:
    """还原 ZIP 内文件名编码。

    北京统计局的发布件用传统编码（GBK）存文件名，zipfile 对未置 UTF-8 标志位的条目按 cp437 解码，
    直接读会得到乱码，故按 cp437 → GBK 还原；已是 UTF-8 的名称原样返回。
    """
    try:
        return name.encode("cp437").decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def main() -> int:
    # ① 归档发布计划页（摘录）与发布件（zip 原件 + 解出的官方 xlsx）
    plan_html = fetch(PLAN_PAGE).decode("utf-8", "ignore")
    _, _, plan_md = html_to_md(plan_html, PLAN_PAGE)
    body = ("## 2026 年度统计资料发布计划（摘录）\n\n"
            f"{plan_page_table(plan_md)}\n\n"
            "> 本页由 `stage22_beijing_2025_estimate.py` 归档：2025 年度「城镇非私营、私营单位就业人员"
            "年末人数及工资情况」的官方取数路径来源（发布件下载地址见同目录 zip 的 `.meta.yaml`）。\n"
            "> 上方为官方页面正文摘录；全文以来源页为准。\n")
    save_md(f"{BASE}/sources/annual-publish-plan-2026.md",
            "北京市统计局、国家统计局北京调查总队年度统计资料发布计划（2026年度）",
            body, topic=BASE, source_url=PLAN_PAGE, published_at="2026-01-05",
            authority="北京市统计局、国家统计局北京调查总队",
            notes="发布计划页摘录（保留“人口与就业（6月份）”发布件链接）；全文以官方页面为准")

    zip_bytes = fetch(ZIP_URL)
    save_binary(f"{BASE}/publish-plan/2026-06-population-employment.zip", zip_bytes,
                title="北京市统计局 2026 年度统计资料发布件（人口与就业，2026-06-25）",
                topic=BASE, source_url=PLAN_PAGE, download_url=ZIP_URL,
                published_at="2026-06-25", authority="北京市统计局、国家统计局北京调查总队",
                original_filename="P020260625381701456879.zip", region=REGION, level="municipality",
                notes="官方发布件（含 2025 年度两行口径工资数据）；表内数值转出后见同目录 xlsx")

    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        entries = [(decode_zip_name(n), n) for n in z.namelist()]
        inner = [orig for dec, orig in entries
                 if "城镇非私营" in dec and "工资情况" in dec and str(DATA_YEAR) in dec]
        if not inner:
            raise SystemExit("发布件内未找到 %d 年度两行口径表：%s"
                             % (DATA_YEAR, [dec for dec, _ in entries]))
        table_orig = inner[0]
        table_name = decode_zip_name(table_orig)
        table_bytes = z.read(table_orig)
        print(f"  发布件内数据表：{table_name}")
    rows = read_xlsx_rows(table_bytes, table_name)
    for prefix in PREFIXES:
        print(f"  {pick(rows, prefix)[0]}: {pick(rows, prefix)[1]}")
    est = estimate(rows)
    monthly = (est / 12).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    print(f"{DATA_YEAR} 年度估算：{est} 元/年（月 {monthly}）→ 三倍封顶 {(est / 12 * 3).quantize(Decimal('0.01'))} 元/月")

    save_binary(f"{BASE}/publish-plan/{DATA_YEAR}-table-population-employment.xlsx", table_bytes,
                title=f"城镇非私营、私营单位就业人员年末人数及工资情况（{DATA_YEAR}年）",
                topic=BASE, source_url=PLAN_PAGE, download_url=ZIP_URL,
                published_at="2026-06-25", authority="北京市统计局、国家统计局北京调查总队",
                original_filename=table_name.split("/")[-1], region=REGION, level="municipality",
                notes=f"取自 2026-06-25 官方发布件；{DATA_YEAR} 年度法人单位口径封顶基数的估算输入")

    # ② 方法校验（2023 年官方表）+ 写入 derived_estimates
    validation = validation_from_yearbook()
    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    series = next(s for s in params["series"] if s["id"] == "beijing_legal_entity_avg_wage")
    entry = {
        "year": DATA_YEAR,
        "annual": int(est),
        "monthly": int(monthly),
        "status": "estimate-not-official",
        "method": "（城镇非私营单位工资总额 + 城镇私营单位工资总额）÷（两口径年末人数之和）；"
                  "2023 年官方表显示两者人数之和等于法人单位全口径",
        "inputs": {
            pick(rows, prefix)[0]: dict(zip(COLUMNS, [str(v) for v in pick(rows, prefix)[1]]))
            for prefix in PREFIXES
        } | {
            "source_url": PLAN_PAGE,
            "source_file": "2026-06-population-employment.zip",
            "source_file_sha256": sha256(zip_bytes),
            "inner_file": table_name,
        },
        "validation": validation,
        "caveat": f"估算值，非官方发布。{DATA_YEAR} 年度发布件的「工资总额」仅到亿元整数，"
                  "精度低于 2024 年度发布件，偏差可能扩大；正式出具意见前应以统计部门发布的数据为准"
                  "（或向社保经办/12333 核实）。计算侧对该年度默认拒绝，需调用方显式指定基数。",
    }
    others = [e for e in series.get("derived_estimates", []) if e.get("year") != DATA_YEAR]
    series["derived_estimates"] = sorted(others + [entry], key=lambda e: e["year"])
    gap = (f"{DATA_YEAR} 年度官方数值未发布（年鉴2026 未上线、年鉴2025 起已无「法人单位」表）；"
           f"参数表提供估算 {int(est)} 元/年（方法经 2023 年数据校验，偏差 "
           f"{validation['deviation_pct'] if validation else '未知'}%），状态 estimate-not-official，"
           f"不得直接用于正式计算。")
    stale = f"{DATA_YEAR} 年度官方数值未发布"
    series["gaps"] = [g for g in series.get("gaps", []) if stale not in g] + [gap]

    content = ("# 北京劳动仲裁计算参数（由 tools/crawl 生成，勿手改数值）\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(f"{BASE}/parameters.yaml", content,
                title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic=BASE,
                source_url=PLAN_PAGE,
                authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
                original_filename="parameters.yaml", region=REGION, level="municipality",
                notes=f"阶段 22：新增 {DATA_YEAR} 年度估算 {int(est)} 元/年（estimate-not-official）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
