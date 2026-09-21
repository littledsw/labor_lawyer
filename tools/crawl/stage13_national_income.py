"""阶段 13：归档「全国城镇居民人均可支配收入」序列（国家统计局年度统计公报）。

用途：一次性工亡补助金 = 上年度全国城镇居民人均可支配收入 × 20（《工伤保险条例》第三十九条）。
官方口径来源：国家统计局《中华人民共和国XXXX年国民经济和社会发展统计公报》「居民收入消费」一节，
原文表述为「城镇居民人均可支配收入XXXXX元」。

归档策略：公报全文页面体积较大（单份约 6 万字符），本阶段归档**该指标所在小节的完整文本**，
并在文件与参数台账中记录完整页面 URL、发布时间、页面 sha256 与公报原句，保证可回溯核验。
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402
from common import fetch_text, html_to_md, save_binary, save_md, sha256  # noqa: E402

BASE = "statistics"
REGION = "national"   # 注意：必须传给 common.save_* 的 region 参数，level 不能替代 region
PARAMS_REL = f"{BASE}/parameters.yaml"

# 数据年度 → 统计公报 URL（国家统计局年度统计公报栏目）
COMMUNIQUES = {
    2013: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1898455.html",
    2014: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1898704.html",
    2015: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1899041.html",
    2016: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1899428.html",
    2017: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1899855.html",
    2018: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900241.html",
    2019: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900640.html",
    2020: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901004.html",
    2021: "https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901393.html",
    2022: "https://www.stats.gov.cn/sj/zxfb/202302/t20230228_1919011.html",
    2023: "https://www.stats.gov.cn/sj/zxfb/202402/t20240228_1947915.html",
    2024: "https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html",
    2025: "https://www.stats.gov.cn/sj/zxfb/202602/t20260228_1962662.html",
}

# 公报正文的分节标题是纯文本行（如「九、居民收入消费和社会保障」），不是 markdown 标题
SECTION_RE = re.compile(r"^[\s\u3000]*(?:#{1,6}\s*)?(?:\*\*|__)?[一二三四五六七八九十]+、[^\n]*(?:居民收入|人民生活|居民生活)", re.M)
NEXT_SECTION_RE = re.compile(r"^[\s\u3000]*(?:#{1,6}\s*)?(?:\*\*|__)?[一二三四五六七八九十]+、", re.M)
VALUE_RE = re.compile(r"城镇居民人均可支配收入\s*([\d,，]+)\s*元")


def extract_section(md: str) -> str:
    m = SECTION_RE.search(md)
    if not m:
        return ""
    nxt = NEXT_SECTION_RE.search(md, m.end())
    return md[m.start(): nxt.start() if nxt else len(md)].strip()


def extract_value(md: str) -> tuple[int, str]:
    flat = re.sub(r"\[[\d,\s]+\]", "", md)             # 去脚注编号
    flat = re.sub(r"[*_`>#]", "", flat)                # 去 markdown 强调符（数字常被 ** 包裹）
    for m in VALUE_RE.finditer(flat):
        # 「城镇居民人均可支配收入中位数为X元」不会命中 VALUE_RE（收入与数字之间有「中位数」），
        # 故直接取首个命中即可；此处仅做一次紧邻前缀的保险检查。
        if flat[max(0, m.start() - 3):m.start()].endswith("中位数"):
            continue
        sentence = flat[max(0, m.start() - 40): m.end() + 60].replace("\n", " ")
        value = int(m.group(1).replace(",", "").replace("，", ""))
        stmt = re.search(r"城镇居民人均可支配收入\s*[\d,，]+\s*元[^。]*。", flat)
        return value, (stmt.group(0).strip() if stmt else sentence.strip())
    probe = flat[flat.find("城镇居民人均可支配收入"):][:120] if "城镇居民人均可支配收入" in flat else flat[:120]
    raise ValueError(f"未在公报中检索到「城镇居民人均可支配收入X元」；样本：{probe!r}")


def main() -> None:
    entries, problems = [], []
    for year, url in sorted(COMMUNIQUES.items()):
        try:
            html = fetch_text(url)
            _, published, md = html_to_md(html, url)
            value, statement = extract_value(md)
            section = extract_section(md) or statement
            save_md(
                f"{BASE}/sources/annual-statistical-communique-{year}.md",
                f"{year}年国民经济和社会发展统计公报（居民收入相关小节）",
                f"> 完整页面：{url}\n> 发布机关：国家统计局\n> 发布时间：{published}\n"
                f"> 页面 sha256（原文）：{sha256(html.encode())}\n"
                f"> 说明：仅归档「城镇居民人均可支配收入」指标所在小节；完整公报见上方链接。\n\n"
                f"{section}\n",
                topic="statistics", source_url=url, published_at=published,
                authority="国家统计局", region=REGION,
                notes=f"提取值：{value} 元（数据年度 {year}）；原句：{statement}",
            )
            entries.append({
                "year": year, "amount": value, "source_url": url, "published_at": published,
                "statement": statement, "source_page_sha256": sha256(html.encode()),
                "use": "一次性工亡补助金 = 上年度该值 × 20（《工伤保险条例》第三十九条）",
            })
            print(f"  {year}: {value} 元（公报 {published}）")
        except Exception as exc:
            problems.append(f"{year}: {type(exc).__name__}: {exc}")
            print(f"  {year}: FAIL {exc}")

    params = {
        "region": "national",
        "topic": "statistics",
        "note": "国家层面计算参数。数值均来自官方页面（见 series[].source_url），未取到官方来源的年份列入 gaps。"
                "工亡案件按「死亡时点的上年度」取值。",
        "series": [{
            "id": "national_urban_per_capita_disposable_income",
            "name": "全国城镇居民人均可支配收入（元/年）",
            "authority": "国家统计局",
            "source_page": "https://www.stats.gov.cn/sj/tjgb/ndtjgb/",
            "use": "一次性工亡补助金 = 上年度全国城镇居民人均可支配收入 × 20",
            "entries": entries,
        }],
        "decisions": [],
        "gaps": ([] if not problems else [f"抓取失败：{p}" for p in problems]),
        "updated_at": __import__("datetime").date.today().isoformat(),
    }
    content = ("# 国家层面计算参数（由 tools/crawl/stage13_national_income.py 生成）\n"
               "# 每条数值均来自官方页面并可回溯；未取得官方来源的年份留在 gaps。\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(
        PARAMS_REL, content,
        title="国家层面计算参数表（全国城镇居民人均可支配收入）", topic="statistics",
        source_url="https://www.stats.gov.cn/sj/tjgb/ndtjgb/", authority="国家统计局",
        original_filename="parameters.yaml", region=REGION,
            notes=(f"{len(entries)} 个数据年度（{min(e['year'] for e in entries)}—{max(e['year'] for e in entries)}）"
               if entries else "本次未取得任何年度数值"),
    )
    print(f"regions/{REGION}/{PARAMS_REL} 已生成：{len(entries)} 条，失败 {len(problems)} 条")
    if problems:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
