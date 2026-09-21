"""阶段 10：归档北京计算参数（社平工资口径、最低工资标准）并生成 parameters.yaml。

只采纳官方信源；每条参数带来源 URL、发布/生效信息与抓取时间；官方页面原文同时归档为 Markdown。
凡未能从官方页面取到的年份，一律写入 gaps 而不是凭记忆补数。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch_text, html_to_md, save_binary, save_md, sha256  # noqa: E402

REGION = "municipalities/beijing"
TOPIC = "statistics"
BASE = "statistics"

PAGES = {
    "full-caliber-avg-wage": (
        "历年北京市全口径城镇单位就业人员平均工资",
        "https://rsj.beijing.gov.cn/bm/ywml/202007/t20200717_1950961.html",
        "北京市人力资源和社会保障局",
    ),
    "employee-avg-wage-archive": (
        "历年北京市职工年平均工资（已归档）",
        "http://rsj.beijing.gov.cn/bm/ywml/201912/t20191206_873811.html",
        "北京市人力资源和社会保障局",
    ),
    "compensation-cap-notice": (
        "关于按照法人单位从业人员平均工资计算经济补偿封顶基数的通告",
        "https://rsj.beijing.gov.cn/xxgk/tzgg/201912/t20191207_951033.html",
        "北京市人力资源和社会保障局",
    ),
    "min-wage-2025": (
        "关于调整北京市2025年最低工资标准的通知",
        "https://rsj.beijing.gov.cn/xxgk/2024zcwj/202507/t20250725_4158456.html",
        "北京市人力资源和社会保障局",
    ),
    "min-wage-2023-qa": (
        "解读问答《关于调整北京市2023年最低工资标准的通知》",
        "https://www.beijing.gov.cn/zhengce/zcjd/202307/t20230714_3162840.html",
        "北京市人力资源和社会保障局（首都之窗发布）",
    ),
}


def fetch_all() -> dict[str, str]:
    texts = {}
    for key, (title, url, authority) in PAGES.items():
        html = fetch_text(url)
        t, date, md = html_to_md(html, url)
        texts[key] = md
        save_md(
            f"{BASE}/sources/{key}.md", title,
            f"> 来源：{url}\n> 发布机关：{authority}\n\n{md}\n",
            topic=TOPIC, source_url=url, published_at=date, authority=authority,
            region=REGION, notes="计算参数来源页面原文",
        )
    return texts


def parse_full_caliber(md: str) -> list[dict]:
    rows = []
    for m in re.finditer(r"\|\s*(\d{4})\s*\|\s*(\d{5,6})\s*\|\s*(\d{4,5})\s*\|", md):
        rows.append({"year": int(m.group(1)), "annual": int(m.group(2)), "monthly": int(m.group(3))})
    return sorted(rows, key=lambda r: r["year"])


def parse_employee_wage(md: str) -> list[dict]:
    rows = []
    for m in re.finditer(r"\|\s*(\d{4})\s*\|\s*(\d{5,6})\s*\|", md):
        rows.append({"year": int(m.group(1)), "annual": int(m.group(2))})
    return sorted(rows, key=lambda r: r["year"])


def parse_min_wage_2025(md: str) -> dict:
    """从 2025 年调整通知解析新旧标准与执行日期。"""
    nums = re.findall(r"每月不低于(\d{3,5})元", md)
    eff = re.search(r"自(\d{4})年(\d{1,2})月(\d{1,2})日起执行", md)
    hourly = re.findall(r"每小时不低于([\d.]+)元", md)
    part = re.search(r"非全日制从业人员小时最低工资标准确定为([\d.]+)元/小时", md)
    part_hol = re.search(r"法定节假日小时最低工资标准确定为([\d.]+)元/小时", md)
    code = re.search(r"（(京人社[^）]{2,20}号)）|^(京人社[^\s]{2,20}号)", md, re.M)
    return {
        "effective_from": f"{eff.group(1)}-{int(eff.group(2)):02d}-{int(eff.group(3)):02d}" if eff else None,
        "monthly": int(nums[-1]) if nums else None,
        "monthly_previous": int(nums[0]) if len(nums) > 1 else None,
        "hourly": hourly[-1] if hourly else None,
        "hourly_previous": hourly[0] if len(hourly) > 1 else None,
        "part_time_hourly": part.group(1) if part else None,
        "part_time_holiday_hourly": part_hol.group(1) if part_hol else None,
        "doc_no": (code.group(1) or code.group(2)) if code else None,
    }


def parse_min_wage_2023(md: str) -> dict:
    """从 2023 年调整解读问答解析新标准、执行日期与上一轮标准。"""
    new = re.search(r"月最低工资标准调整为(\d{3,5})元", md)
    eff = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日起", md)
    prev = re.search(r"(\d{4})年我市对最低工资标准为月最低工资标准为(\d{3,5})元", md)
    part = re.search(r"小时最低工资标准调整为([\d.]+)元/小时", md)
    return {
        "effective_from": f"{eff.group(1)}-{int(eff.group(2)):02d}-{int(eff.group(3)):02d}" if eff else None,
        "monthly": int(new.group(1)) if new else None,
        "part_time_hourly": part.group(1) if part else None,
        "previous_year": int(prev.group(1)) if prev else None,
        "previous_monthly": int(prev.group(2)) if prev else None,
    }


def main() -> None:
    texts = fetch_all()
    full = parse_full_caliber(texts["full-caliber-avg-wage"])
    legacy = parse_employee_wage(texts["employee-avg-wage-archive"])
    cap_md = texts["compensation-cap-notice"]
    cap_date = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cap_md)
    mw2025 = parse_min_wage_2025(texts["min-wage-2025"])
    mw2023 = parse_min_wage_2023(texts["min-wage-2023-qa"])

    print("全口径社平行数:", len(full), full[:3], "...")
    print("职工年平均工资行数:", len(legacy), legacy[:2], "...")
    print("2025 最低工资:", mw2025)
    print("2023 最低工资:", mw2023)
    print("封顶通告日期:", cap_date.groups() if cap_date else None)

    params = {
        "region": REGION,
        "topic": "计算参数",
        "note": "所有数值均来自官方页面（见 series[].source_url）；未取到官方来源的年份列入 gaps，"
                "不得凭记忆填写。历史案件请按“案件相关时点”取值（生效区间/数据年度）。",
        "series": [
            {
                "id": "beijing_full_caliber_avg_wage",
                "name": "北京市全口径城镇单位就业人员平均工资",
                "authority": "北京市人力资源和社会保障局（依据《北京统计年鉴》）",
                "source_url": PAGES["full-caliber-avg-wage"][1],
                "use": "核定社会保险个人缴费基数上下限；官方页面明确注明“仅用于核定社保缴费基数上下限”，"
                       "不作为经济补偿封顶基数",
                "entries": full,
            },
            {
                "id": "beijing_employee_avg_wage_legacy",
                "name": "北京市职工年平均工资（已归档序列）",
                "authority": "北京市人力资源和社会保障局",
                "source_url": PAGES["employee-avg-wage-archive"][1],
                "use": "2019 年 8 月 16 日之前的经济补偿封顶口径；亦为财税〔2001〕157 号免税额度基数口径",
                "entries": legacy,
            },
            {
                "id": "beijing_legal_entity_avg_wage",
                "name": "北京市法人单位从业人员平均工资",
                "authority": "北京市统计局（口径由北京市人社局通告确认）",
                "source_url": PAGES["compensation-cap-notice"][1],
                "use": "《劳动合同法》第四十七条第二款“本地区上年度职工月平均工资”的北京口径，"
                       "用于计算经济补偿三倍封顶基数",
                "entries": [{"year": 2018, "annual": 127107, "monthly": 10592,
                             "source_note": "取自人社局通告页面及 2019 年典型案例（2018 年数据）"}],
                "gaps": ["2019—2025 年度数值待补：需从北京市统计局年度数据/统计公报取得与通告口径一致的数值"],
            },
            {
                "id": "beijing_min_wage",
                "name": "北京市最低工资标准（月）",
                "authority": "北京市人力资源和社会保障局",
                "source_url": PAGES["min-wage-2025"][1],
                "use": "病假工资下限、竞业限制补偿下限、差额类计算、二倍工资下限参照等",
                "entries": [
                    {"effective_from": mw2025["effective_from"], "monthly": mw2025["monthly"],
                     "part_time_hourly": mw2025["part_time_hourly"],
                     "part_time_holiday_hourly": mw2025["part_time_holiday_hourly"],
                     "doc_no": mw2025["doc_no"], "source_url": PAGES["min-wage-2025"][1]},
                    {"effective_from": mw2023["effective_from"], "monthly": mw2023["monthly"],
                     "part_time_hourly": mw2023["part_time_hourly"],
                     "source_url": PAGES["min-wage-2023-qa"][1]},
                    {"effective_from": f"{mw2023['previous_year']}-08-01" if mw2023["previous_year"] else None,
                     "monthly": mw2023["previous_monthly"],
                     "source_url": PAGES["min-wage-2023-qa"][1],
                     "source_note": "由 2023 年官方解读的“新旧政策差异”推出，建议补充当年调整通知原件后复核"},
                ],
                "gaps": ["2016—2020 各次调整的官方通知尚未定位（需逐年在 rsj.beijing.gov.cn 政策文件栏目检索）；"
                         "2021 年标准目前仅有 2023 年官方解读的引用，待补当年通知原件"],
            },
        ],
        "decisions": [
            {
                "id": "economic_compensation_cap_basis",
                "title": "经济补偿三倍封顶基数口径",
                "rule": "封顶基数 = 上年度北京市法人单位从业人员平均工资 × 3；月工资高于该基数的，"
                        "按封顶基数计算且补偿年限最高 12 年（《劳动合同法》第四十七条）",
                "effective_from": "2019-08-16",
                "source_url": PAGES["compensation-cap-notice"][1],
                "note": "2019 年 8 月 16 日前按原「北京市职工年平均工资」口径；"
                        "人社局与统计局原联合发布职工平均工资的做法已终止",
            },
            {
                "id": "economic_compensation_tax_exemption",
                "title": "经济补偿个税免税额度基数",
                "rule": "一次性补偿收入在当地上年职工平均工资 3 倍数额以内的部分免征个人所得税",
                "legal_basis": "财税〔2001〕157 号第一条",
                "note": "北京 2019 年前按「职工年平均工资」；口径切换后需以税务/统计局公布口径复核",
            },
        ],
    }
    import yaml
    content = (
        "# 北京劳动仲裁计算参数（由 tools/crawl/stage10_beijing_params.py 生成）\n"
        "# 每条数值均需可追溯至官方页面；gaps 表示尚未取得官方来源，禁止凭记忆补数。\n"
        + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)
    ).encode()
    save_binary(
        f"{BASE}/parameters.yaml", content,
        title="北京劳动仲裁计算参数表（社平工资口径、最低工资标准）", topic=TOPIC,
        source_url=PAGES["compensation-cap-notice"][1],
        authority="北京市人力资源和社会保障局 / 北京市统计局（按条目）",
        original_filename="parameters.yaml", region=REGION,
        notes="参数台账：series 为时间序列（含生效区间/数据年度与来源 URL），decisions 为口径决定（含法条与生效日期），"
              "gaps 为尚未取得官方来源的年份",
    )
    print("SHA-256:", sha256(content)[:16])


if __name__ == "__main__":
    main()
