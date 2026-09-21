"""阶段 12：把「未核实候选值」提升为「已验证参数」——仅当官方页面上确能检索到该数值时。

背景：2019—2025 年「北京市法人单位从业人员平均工资」目前只有二手来源（律所/媒体转述），
按项目规则禁止直接用于计算，暂存于 parameters.yaml 的 candidates_unverified。
本脚本提供一条可验证的提升路径：

    python stage12_promote_wage.py --year 2023 --annual 188413 \\\\
        --url "https://tjj.beijing.gov.cn/<官方页面>" --pubdate 2024-06-19

脚本会抓取该官方页面，校验页面上确实出现该数值（含千分位写法），校验通过才写回
parameters.yaml：数值从 candidates_unverified 移入 entries，并记录 source_url、抓取时间与页面 sha256。
校验失败即退出（exit 2），不做任何写入——避免把「看起来对」的数字变成「官方参数」。
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402
from common import fetch_text, save_binary, sha256  # noqa: E402

REPO = pathlib.Path("/Users/abaaba/workspace/projects/labor_lawyer")
REGION = "municipalities/beijing"
PARAMS = REPO / "regions" / REGION / "statistics" / "parameters.yaml"
DEFAULT_SERIES = "beijing_legal_entity_avg_wage"


def page_text(html: str) -> str:
    txt = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default=DEFAULT_SERIES)
    ap.add_argument("--year", type=int, required=True, help="数据年度，如 2023")
    ap.add_argument("--annual", type=int, required=True, help="年平均工资（元）")
    ap.add_argument("--url", required=True, help="官方页面 URL（须能取到该数值）")
    ap.add_argument("--monthly", type=int, default=None, help="官方公布的年平均月工资（元/月）")
    ap.add_argument("--pubdate", default=None, help="页面发布日期 YYYY-MM-DD")
    args = ap.parse_args()

    try:
        html = fetch_text(args.url)
    except Exception as exc:  # 网络失败/404 时明确退出，不写入
        print(f"[FAIL] 无法取得官方页面：{args.url}\n       {type(exc).__name__}: {exc}")
        return 3
    text = page_text(html)
    variants = {str(args.annual), f"{args.annual:,}", f"{args.annual / 10000:.2f}万"}
    hit = next((v for v in variants if v in text), None)
    if not hit:
        print(f"[FAIL] 页面文本中未检索到 {args.annual}（或其千分位/万元写法），拒绝写入。")
        print(f"       页面：{args.url}（长度 {len(text)} 字符）")
        return 2
    print(f"[OK] 页面检索到匹配写法：{hit!r}")

    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    series = next((s for s in params["series"] if s["id"] == args.series), None)
    if series is None:
        print(f"[FAIL] 参数表无序列 {args.series}")
        return 2
    if any(e.get("year") == args.year for e in series.get("entries", [])):
        print(f"[SKIP] {args.series} 已有 {args.year} 年已验证条目，未做修改。")
        return 0

    entry = {
        "year": args.year, "annual": args.annual,
        "monthly": args.monthly or round(args.annual / 12),
        "source_url": args.url,
        "published_at": args.pubdate,
        "retrieved_at": dt.datetime.now().strftime("%Y-%m-%d"),
        "verification": "官方页面文本命中数值（stage12_promote_wage.py）",
        "source_page_sha256": sha256(html.encode()),
    }
    series["entries"] = sorted(series["entries"] + [entry], key=lambda e: e["year"])
    before = series.get("candidates_unverified", [])
    series["candidates_unverified"] = [c for c in before if c.get("year") != args.year]
    gaps = series.get("gaps", [])
    series["gaps"] = [g for g in gaps if str(args.year) not in g] or ["（已全部补齐或待复核）"]

    content = ("# 北京劳动仲裁计算参数（由 tools/crawl 生成，勿手改数值；改数值请走 stage10/11/12）\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(
        "statistics/parameters.yaml", content,
        title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic="statistics",
        source_url=args.url, authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
        original_filename="parameters.yaml", region=REGION,
        notes=f"新增已验证条目 {args.series} {args.year}={args.annual}（页面数值命中校验通过）",
    )
    print(f"[DONE] {args.series} {args.year} = {args.annual} 元年（月 {entry['monthly']}）已写入 entries")
    print(f"       剩余候选值：{[c.get('year') for c in series['candidates_unverified']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
