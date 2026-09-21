"""阶段 9：归档计算所需参数（日历参数 + 北京工资/最低工资参数）。

原则（与仓库归档约定一致）：
- 只采纳官方信源（国务院办公厅、北京市人社局、北京市统计局等），逐条记录 source_url、发布时间、抓取时间；
- 参数按「生效区间」存储，历史案件按当时口径取值；
- 官方页面原文一并归档为 Markdown，派生参数单独落 JSON/YAML，便于程序读取。

日历参数口径：
- 法定节假日（statutory，3 倍工资日）：按《全国年节及纪念日放假办法》确定，农历/节气日期由 cnlunar 计算，
  并与国务院办公厅当年放假安排通知交叉校验；
- 休息日（rest，2 倍工资或安排补休）：通知中的放假调休日中非法定节假日的部分；
- 调休上班日（makeup，按正常工作日计）：通知明确要求上班的周六/周日。
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import cnlunar  # noqa: E402
from common import fetch_text, html_to_md, save_binary, save_md  # noqa: E402

REGION = "national"
TOPIC = "statistics"
CAL = "statistics/calendar"   # 相对 region 根目录（regions/national/）
REPO_PATH = str(REPO / "regions" / "national")

# 国务院办公厅节假日安排通知（官方 URL 取自中国政府网政策文件库）
NOTICES: dict[int, tuple[str, str]] = {
    2016: ("国办发明电〔2015〕18号", "https://www.gov.cn/zhengce/zhengceku/2015-12/10/content_10394.htm"),
    2017: ("国办发明电〔2016〕17号", "https://www.gov.cn/zhengce/zhengceku/2016-12/01/content_5141603.htm"),
    2018: ("国办发明电〔2017〕12号", "https://www.gov.cn/zhengce/zhengceku/2017-11/30/content_5243579.htm"),
    2019: ("国办发明电〔2018〕15号", "https://www.gov.cn/zhengce/zhengceku/2018-12/06/content_5346276.htm"),
    2020: ("国办发明电〔2019〕16号", "https://www.gov.cn/zhengce/zhengceku/2019-11/21/content_5454164.htm"),
    2021: ("国办发明电〔2020〕27号", "https://www.gov.cn/zhengce/zhengceku/2020-11/25/content_5564127.htm"),
    2022: ("国办发明电〔2021〕11号", "https://www.gov.cn/zhengce/zhengceku/2021-10/25/content_5644835.htm"),
    2023: ("国办发明电〔2022〕16号", "https://www.gov.cn/zhengce/zhengceku/2022-12/08/content_5730844.htm"),
    2024: ("国办发明电〔2023〕7号", "https://www.gov.cn/zhengce/zhengceku/202310/content_6911528.htm"),
    2025: ("国办发明电〔2024〕12号", "https://www.gov.cn/zhengce/zhengceku/202411/content_6986383.htm"),
    2026: ("国办发明电〔2025〕7号", "https://www.gov.cn/zhengce/zhengceku/202511/content_7047091.htm"),
}
# 2020 年春节假期延长（国办通知），用作 2020 年的覆盖修正
EXT_2020 = ("国务院办公厅关于延长2020年春节假期的通知",
            "http://app.www.gov.cn/govdata/gov/202001/27/453442/article.html")

FESTIVALS = ["元旦", "春节", "清明节", "劳动节", "端午节", "中秋节", "国庆节"]
DATE = re.compile(r"(\d{1,2})月(\d{1,2})日")


def solar(d: dt.date) -> str:
    return d.isoformat()


def lunar_date(year: int, month: int, day: int) -> dt.date:
    """农历 → 公历（用于除夕/端午/中秋；跨年情况下按提示年份处理）。"""
    import lunardate
    return lunardate.LunarDate(year, month, day).toSolarDate()


def qingming(year: int) -> dt.date:
    for d in (3, 4, 5, 6):
        if cnlunar.Lunar(dt.datetime(year, 4, d), godType="8char").todaySolarTerms == "清明":
            return dt.date(year, 4, d)
    raise RuntimeError(f"未找到 {year} 年清明")


def chuxi_chunjie(year: int) -> tuple[dt.date, dt.date]:
    """返回该年春节的（除夕, 正月初一）。"""
    for m, dmax in ((1, 31), (2, 29)):
        for d in range(1, dmax + 1):
            try:
                a = cnlunar.Lunar(dt.datetime(year, m, d), godType="8char")
            except Exception:  # noqa: BLE001
                continue
            if a.lunarMonth == 1 and a.lunarDay == 1:
                first = dt.date(year, m, d)
                return first - dt.timedelta(days=1), first
    raise RuntimeError(f"未找到 {year} 年正月初一")


def statutory_days(year: int) -> dict[str, list[str]]:
    """按《全国年节及纪念日放假办法》算当年法定节假日（3 倍工资日）。"""
    chuxi, chuyi = chuxi_chunjie(year)
    out = {
        "元旦": [dt.date(year, 1, 1)],
        "春节": ([chuxi, chuyi] if year >= 2025 else [chuyi])
                + [chuyi + dt.timedelta(days=n) for n in (1, 2)],
        "清明节": [qingming(year)],
        "劳动节": [dt.date(year, 5, 1)] + ([dt.date(year, 5, 2)] if year >= 2025 else []),
        "端午节": [lunar_date(year, 5, 5)],
        "中秋节": [lunar_date(year, 8, 15)],
        "国庆节": [dt.date(year, 10, 1), dt.date(year, 10, 2), dt.date(year, 10, 3)],
    }
    return {k: [solar(x) for x in v] for k, v in out.items()}


def split_segments(md: str) -> dict[str, str]:
    """把通知正文按节日切段。"""
    marks = []
    for f in FESTIVALS:
        m = re.search(rf"(?:[一二三四五六七八九十]+、\s*)?{f}\s*[：:]", md)
        if m:
            marks.append((m.start(), f))
    marks.sort()
    segs = {}
    for i, (pos, f) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else min(len(md), pos + 600)
        segs[f] = md[pos:end]
    return segs


FULL_DATE = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日")


def parse_segment(seg: str, year: int) -> tuple[list[dt.date], list[dt.date]]:
    """从单个节日段落解析 (放假日期, 调休上班日期)。

    支持跨年区间（如「2022年12月31日至2023年1月2日放假调休」），显式年份优先。
    """
    holidays: list[dt.date] = []
    makeup: list[dt.date] = []
    for sentence in re.split(r"[。；;]", seg):
        if "放假" in sentence and not holidays:
            span = re.search(
                r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日[^至]{0,30}至[^0-9]{0,30}"
                r"(?:(\d{4})年)?(?:(\d{1,2})月)?(\d{1,2})日", sentence)
            if span:
                y1, m1, d1, y2, m2, d2 = span.groups()
                start = dt.date(int(y1) if y1 else year, int(m1), int(d1))
                em = int(m2) if m2 else int(m1)
                end_year = int(y2) if y2 else (start.year if em >= int(m1) else start.year + 1)
                end = dt.date(end_year, em, int(d2))
                cur = start
                while cur <= end:
                    holidays.append(cur)
                    cur += dt.timedelta(days=1)
            else:
                single = FULL_DATE.search(sentence)
                if single:
                    y, m, d = single.groups()
                    holidays.append(dt.date(int(y) if y else year, int(m), int(d)))
        if "上班" in sentence:
            for y, m, d in FULL_DATE.findall(sentence):
                makeup.append(dt.date(int(y) if y else year, int(m), int(d)))
    return holidays, makeup


def fetch_notice(year: int, notice_no: str, url: str) -> tuple[str, str, set[dt.date], set[dt.date]]:
    """抓取并归档某年通知，返回 (原标题, 发布日期, 放假日期集合, 调休上班日集合)。

    放假日期可能跨越年度（如 2019 年通知里的元旦假期自 2018年12月30日 起），
    因此这里返回的是全局集合，稍后统一切片，保证跨年日期在所属年份的日历里也正确归类。
    """
    html = fetch_text(url)
    title, date, md = html_to_md(html, url)
    title = title or f"国务院办公厅关于{year}年部分节假日安排的通知"
    safe_title = re.sub(r'[\\/:*?"<>|\s]+', "-", title).strip("-")
    save_md(
        f"{CAL}/notices/{year}-{safe_title}.md", title,
        f"> 文号：{notice_no}\n> 发布机关：国务院办公厅\n> 来源：{url}\n\n{md}\n",
        topic=TOPIC, source_url=url, published_at=date,
        authority="国务院办公厅", region=REGION, level="national",
        notes="计算参数来源：年度节假日安排通知（提供放假调休与调休上班日）",
    )
    segs = split_segments(md)
    holidays: set[dt.date] = set()
    makeup: set[dt.date] = set()
    for _f, seg in segs.items():
        hol, mk = parse_segment(seg, year)
        holidays.update(hol)
        makeup.update(mk)
    missing = [f for f in FESTIVALS if f not in md]  # 合并表述（如「中秋节、国庆节」）只算一次段落，按名称覆盖判断
    if missing:
        print(f"    ! {year} 通知未覆盖节日：{missing}")
    return title, date, holidays, makeup


def build_year(year: int, notice_no: str, url: str, published: str,
               holidays: set[dt.date], makeup: set[dt.date]) -> dict:
    statutory = statutory_days(year)
    statutory_set = {dt.date.fromisoformat(d) for v in statutory.values() for d in v}
    problems: list[str] = []
    for f, days in statutory.items():
        for sd in days:
            if dt.date.fromisoformat(sd) not in holidays:
                problems.append(f"{f} 法定节假日 {sd} 不在任一通知的放假区间内")

    days_map: dict[str, str] = {}
    cur = dt.date(year, 1, 1)
    while cur.year == year:
        s = solar(cur)
        if cur in makeup:
            days_map[s] = "makeup_workday"
        elif cur in statutory_set:
            days_map[s] = "statutory_holiday"
        elif cur in holidays:
            days_map[s] = "rest_day"
        elif cur.weekday() >= 5:
            days_map[s] = "weekend"
        else:
            days_map[s] = "workday"
        cur += dt.timedelta(days=1)

    rec = {
        "year": year,
        "region": REGION,
        "notice": notice_no,
        "source_url": url,
        "published_at": published,
        "retrieved_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "statutory_total": len(statutory_set),
        "statutory_holidays": sorted(solar(d) for d in statutory_set),
        "statutory_by_festival": statutory,
        "rest_days_non_statutory": sorted(solar(d) for d in (holidays & {
            dt.date(year, m, d) for m in range(1, 13) for d in range(1, 32)
            if _valid(year, m, d)}) - statutory_set),
        "makeup_workdays": sorted(solar(d) for d in makeup
                                  if dt.date(year, 1, 1) <= d <= dt.date(year, 12, 31)),
        "days": days_map,
        "problems": problems,
    }
    return rec


def _valid(y: int, m: int, d: int) -> bool:
    try:
        dt.date(y, m, d)
        return True
    except ValueError:
        return False


def main() -> None:
    meta: dict[int, tuple[str, str, str, set[dt.date], set[dt.date]]] = {}
    for year, (no, url) in sorted(NOTICES.items()):
        try:
            title, date, holidays, makeup = fetch_notice(year, no, url)
        except Exception as exc:  # noqa: BLE001
            print(f"{year} FAIL {exc}")
            continue
        meta[year] = (no, url, date, holidays, makeup)

    all_holidays: set[dt.date] = set()
    all_makeup: set[dt.date] = set()
    for _no, _url, _date, hol, mk in meta.values():
        all_holidays |= hol
        all_makeup |= mk
    # 国务院办公厅关于延长 2020 年春节假期的通知：1月31日—2月2日 放假
    for d in (dt.date(2020, 1, 31), dt.date(2020, 2, 1), dt.date(2020, 2, 2)):
        all_holidays.add(d)
        all_makeup.discard(d)

    summary = []
    for year, (no, url, date, _hol, _mk) in sorted(meta.items()):
        rec = build_year(year, no, url, date, all_holidays, all_makeup)
        summary.append(rec)
        print(f"{year}: 法定 {rec['statutory_total']} 天 / 调休上班 {len(rec['makeup_workdays'])} 天 "
              f"/ 问题 {len(rec['problems'])}")
        for p in rec["problems"]:
            print("    -", p)
        save_binary(
            f"{CAL}/calendar-{year}.json", json.dumps(rec, ensure_ascii=False, indent=1).encode(),
            title=f"{year} 年日历参数（法定节假日/休息日/调休上班日）", topic=TOPIC, source_url=url,
            download_url=url, published_at=date, authority="国务院办公厅",
            region=REGION, level="national", original_filename=f"{year}-calendar.json",
            notes="由国办节假日安排通知派生；法定节假日按《全国年节及纪念日放假办法》与农历/节气计算"
                  "（2020 年另计春节假期延长）",
        )
    index = json.dumps([{k: r[k] for k in ("year", "notice", "source_url", "statutory_total",
                                           "makeup_workdays", "problems")} for r in summary],
                       ensure_ascii=False, indent=1).encode()
    save_binary(f"{CAL}/calendar-index.json", index,
                title="节假日日历参数索引（2016—2026）", topic=TOPIC,
                source_url="https://www.gov.cn/zhengce/zhengceku/", published_at=None,
                authority="国务院办公厅", region=REGION, level="national",
                original_filename="calendar-index.json",
                notes="各年度日历参数文件的汇总索引（法定节假日天数、调休上班日、校验问题）")
    print("年份数:", len(summary))


if __name__ == "__main__":
    main()
