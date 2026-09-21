"""阶段 15：从北京统计年鉴取「全市法人单位从业人员年末人数及工资情况」表，补齐封顶基数序列。

路径（实测有效）：hgk.tjj.beijing.gov.cn/<年鉴年>tjnj/tjnj/zk/ 是在线版年鉴；
左栏框架页 lefte.htm 列出各表，链接形如 html/C03-14.xls（真实 BIFF Excel，用 xlrd 解析）。

两年对比表的坑：年鉴2019/2020 的表 3-13 是**两年对比表**，列头形如
「2018 | 2017 | 2018 | 2017」（人数 | 工资各两年），「合计」行因此有 4 个数，
其中 > 10000 的才是年平均工资。本脚本按表头年份逐列对号入座，不再取「最后一个数」。

口径：经济补偿三倍封顶基数 = 北京市法人单位从业人员平均工资 ÷ 12 × 3。
表只在数据年次年鉴中收录到 2023 年（年鉴2025 已不再收录该表），2024 年度需另找官方来源。
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import xlrd  # noqa: E402
import yaml  # noqa: E402
from common import fetch, save_binary, sha256  # noqa: E402

REPO = pathlib.Path("/Users/abaaba/workspace/projects/labor_lawyer")
REGION = "municipalities/beijing"
BASE = "statistics"
PARAMS = REPO / "regions" / REGION / BASE / "parameters.yaml"
YB_BASE = "https://hgk.tjj.beijing.gov.cn/{year}tjnj/tjnj/zk/"
YEARS = list(range(2019, 2026))            # 年鉴年
WAGE_MIN = 10000                            # 年平均工资（元）不可能低于此值，用于区分人数（万人）


def page_text(url: str) -> str:
    return fetch(url).decode("gb18030", errors="ignore")


def find_table(book_year: int) -> tuple[str, str]:
    """返回 (表名, xls 绝对 URL)。优先「全市法人单位从业人员…工资情况」。"""
    base = YB_BASE.format(year=book_year)
    html = page_text(base + "lefte.htm")
    best = None
    for href, label in re.findall(r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", html, flags=re.S | re.I):
        text = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", label))
        if "法人单位" in text and "工资" in text and "从业人员" in text:
            score = (text.startswith("3-"), "年末人数" in text, -len(text))
            if best is None or score > best[0]:
                best = (score, text, base + href)
    if best is None:
        raise LookupError(f"年鉴{book_year} 未收录「全市法人单位从业人员…工资」表")
    return best[1], best[2]


def parse_table(data: bytes, book_year: int) -> list[dict]:
    """按表头年份解析各年平均工资；返回 [{year, wage_avg_yuan, employees_10k}]。"""
    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as fh:
        fh.write(data)
        path = fh.name
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    title = re.sub(r"\s+", " ", str(sheet.cell_value(0, 0))).strip()
    title_year = None
    m = re.search(r"\((\d{4})年?\)", title)
    if m:
        title_year = int(m.group(1))

    total_row = None
    year_header: dict[int, int] = {}
    for r in range(sheet.nrows):
        first = re.sub(r"\s+", "", str(sheet.cell_value(r, 0)))
        values = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        numeric = [v for v in values if isinstance(v, float)]
        if first in ("合计", "全市合计", "总计") and total_row is None:
            total_row = (r, values)
        # 表头年份行：非空单元格都是 1990—2100 的整数
        non_empty = [v for v in values[1:] if v != ""]
        if (len(non_empty) >= 2 and all(isinstance(v, float) and 1990 <= v <= 2100 for v in non_empty)
                and not year_header):
            year_header = {c: int(values[c]) for c in range(1, sheet.ncols)
                           if isinstance(values[c], float) and 1990 <= values[c] <= 2100}
    if total_row is None:
        raise RuntimeError("表格中未找到「合计」行")

    row_index, values = total_row
    # 平均工资列 = 合计行中 > 10000 的数值列：
    #  · 两年对比表（年鉴2019/2020）：人数列 < 10000 被排除，工资列按表头年份对号入座；
    #  · 单年表（年鉴2021+）：合计行形如 [人数, 工资总额(亿元), 平均工资(元)]，
    #    工资总额也 > 10000，故此时只取最后一个数值列（平均工资）。
    candidates = [(c, values[c]) for c in range(1, sheet.ncols)
                  if isinstance(values[c], float) and values[c] >= WAGE_MIN]
    if not candidates:
        raise RuntimeError("合计行中没有可识别的工资数值列")
    picked = []
    if year_header:
        for c, v in candidates:
            if year_header.get(c):
                picked.append((c, v, year_header[c]))
    if not picked:
        c, v = candidates[-1]
        picked.append((c, v, title_year or book_year - 1))

    result, seen = [], set()
    for c, value, year in picked:
        if year in seen:
            continue
        seen.add(year)
        employees = None
        if c - 2 >= 1 and isinstance(values[c - 2], float) and 0 < values[c - 2] < WAGE_MIN:
            employees = values[c - 2]
        result.append({"year": year, "wage_avg_yuan": int(round(value)),
                       "employees_10k": employees, "title": title, "row": row_index,
                       "column": c})
    if not result:
        raise RuntimeError(f"未能从表头/标题确定年份（title={title!r}）")
    return sorted(result, key=lambda e: e["year"], reverse=True)


def main() -> int:
    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    series = next(s for s in params["series"] if s["id"] == "beijing_legal_entity_avg_wage")
    by_year = {e["year"]: e for e in series["entries"]}
    candidates = {c["year"]: c for c in series.get("candidates_unverified", [])}
    notice_2018 = 127107                     # 人社局 2019-08-16 通告所载 2018 年数值，用于交叉校验

    print(f"{'年鉴':<6}{'数据年':<7}{'平均工资(元/年)':<16}来源列          交叉校验")
    years_done, problems = [], []
    for book_year in YEARS:
        try:
            label, xls_url = find_table(book_year)
        except LookupError as exc:
            problems.append(f"年鉴{book_year}: {exc}")
            print(f"{book_year:<6}—      未收录该表：{exc}")
            continue
        try:
            data = fetch(xls_url, referer=YB_BASE.format(year=book_year) + "lefte.htm")
            rows = parse_table(data, book_year)
            code = xls_url.rsplit("/", 1)[-1]
            save_binary(
                f"{BASE}/yearbook/{book_year}-{code}", data,
                title=f"北京统计年鉴{book_year} · {label}", topic=BASE,
                source_url=xls_url, download_url=xls_url, published_at=f"{book_year}年",
                authority="北京市统计局、国家统计局北京调查总队",
                original_filename=code, region=REGION,
                notes="；".join(f"{r['year']}年 = {r['wage_avg_yuan']} 元/年" for r in rows)
                      + f"；年鉴索引页 {YB_BASE.format(year=book_year)}indexce.htm",
            )
            for row in rows:
                year = row["year"]
                cross = "—"
                if year == 2018 and row["wage_avg_yuan"] == notice_2018:
                    cross = "✓与人社局通告一致"
                elif year == 2018:
                    cross = f"✗通告为 {notice_2018}"
                cand = candidates.get(year)
                if cand and not cross.startswith("✓"):
                    delta = row["wage_avg_yuan"] - int(cand["annual"])
                    cross = f"候选 {cand['annual']} → {'✓一致' if delta == 0 else f'✗差 {delta:+d}'}"
                by_year[year] = {
                    "year": year, "annual": row["wage_avg_yuan"],
                    "monthly": round(row["wage_avg_yuan"] / 12),
                    "source_url": xls_url,
                    "source_page": YB_BASE.format(year=book_year) + "indexce.htm",
                    "source_file": f"{book_year}-{code}",
                    "source_file_sha256": sha256(data),
                    "table": label, "table_title": row["title"], "column": row["column"],
                    "published_at": f"{book_year}年（北京统计年鉴）",
                    "verification": "年鉴原表按表头年份逐列解析（xlrd），值所在列与年份一一对应",
                }
                years_done.append(year)
                flag = "★" if year in (2018, 2019) else " "
                print(f"{book_year:<6}{year:<7}{row['wage_avg_yuan']:<16}列{row['column']}  {row['title'][:28]:<30}{flag}{cross}")
        except Exception as exc:
            problems.append(f"年鉴{book_year}: {type(exc).__name__}: {exc}")
            print(f"{book_year:<6}FAIL {type(exc).__name__}: {exc}")

    series["entries"] = sorted(by_year.values(), key=lambda e: e["year"])
    series["candidates_unverified"] = [c for c in series.get("candidates_unverified", [])
                                      if c["year"] not in by_year]
    max_year = max(by_year)
    series["gaps"] = [
        f"年鉴在线版已收录到数据年度 {max_year}（北京统计年鉴 {max_year + 1} 表 3-14）；"
        f"年鉴{max_year + 2} 起不再收录「全市法人单位从业人员年末人数及工资情况」，"
        f"{max_year + 1} 年度数值需另找官方来源（统计局「统计部门发布计划」栏目，约每年 6 月）。",
        "取数依据：北京统计年鉴「全市法人单位从业人员年末人数及工资情况」表「合计」行的从业人员平均工资列；"
        "两年对比表须按表头年份对号入座（年鉴2019 列头为 2018|2017）。",
    ] + problems
    series["use"] = ("经济补偿三倍封顶基数 = 该序列 ÷ 12 × 3（2019-08-16 起口径）；"
                     "数值取自北京统计年鉴「全市法人单位从业人员年末人数及工资情况」合计行。")

    content = ("# 北京劳动仲裁计算参数（由 tools/crawl 生成，勿手改数值）\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(f"{BASE}/parameters.yaml", content,
                title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic=BASE,
                source_url=YB_BASE.format(year=max(YEARS)) + "indexce.htm",
                authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
                original_filename="parameters.yaml", region=REGION,
                notes=f"阶段 15：年鉴表格补齐法人单位从业人员平均工资 {len(series['entries'])} 个数据年度"
                      f"（{min(by_year)}—{max_year}）")
    print(f"\nentries {len(series['entries'])} 条（{min(by_year)}—{max_year}）；"
          f"剩余候选 {[c['year'] for c in series['candidates_unverified']]}；问题 {len(problems)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
