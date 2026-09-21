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
    "unemployment-benefit-2025": (
        "北京市人力资源和社会保障局关于调整失业保险金发放标准的通告",
        "https://www.beijing.gov.cn/zhengce/zhengcefagui/202509/t20250926_4211356.html",
        "北京市人力资源和社会保障局",
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


def parse_unemployment_benefit(md: str) -> dict:
    """从失业保险金发放标准通告解析分档标准、13 个月起的兜底档与执行日期。

    档位结构（北京）：累计缴费时间满 1 年不满 5 年 / 满 5 年不满 10 年 / 满 10 年不满 15 年 /
    满 15 年不满 20 年 / 满 20 年以上；从第 13 个月起一律按第一档发放。
    """
    tiers = [
        {"min_years": int(a), "max_years": int(b), "monthly": int(v)}
        for a, b, v in re.findall(
            r"累计缴费时间满(\d+)年不满(\d+)年的，失业保险金月发放标准为(\d+)元", md)
    ]
    for a, v in re.findall(r"累计缴费时间满(\d+)年以上的，失业保险金月发放标准为(\d+)元", md):
        tiers.append({"min_years": int(a), "max_years": None, "monthly": int(v)})
    after12 = re.search(r"从第(\d+)个月起，失业保险金月发放标准一律按(\d+)元发放", md)
    eff = re.search(r"自(\d{4})年(\d{1,2})月(\d{1,2})日起执行", md)
    doc_no = re.search(r"(京人社发〔\s?\d{4}\s?〕\s?\d+\s?号)", md)
    return {
        "tiers": tiers,
        "tier_after_month": int(after12.group(1)) if after12 else None,
        "tier_after_monthly": int(after12.group(2)) if after12 else None,
        "effective_from": f"{eff.group(1)}-{int(eff.group(2)):02d}-{int(eff.group(3)):02d}" if eff else None,
        "doc_no": doc_no.group(1).replace(" ", "") if doc_no else None,
    }


def main() -> None:
    texts = fetch_all()
    full = parse_full_caliber(texts["full-caliber-avg-wage"])
    legacy = parse_employee_wage(texts["employee-avg-wage-archive"])
    cap_md = texts["compensation-cap-notice"]
    cap_date = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", cap_md)
    mw2025 = parse_min_wage_2025(texts["min-wage-2025"])
    mw2023 = parse_min_wage_2023(texts["min-wage-2023-qa"])
    unemp = parse_unemployment_benefit(texts["unemployment-benefit-2025"])

    print("全口径社平行数:", len(full), full[:3], "...")
    print("职工年平均工资行数:", len(legacy), legacy[:2], "...")
    print("2025 最低工资:", mw2025)
    print("2023 最低工资:", mw2023)
    print("失业保险金分档:", unemp)
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
            {
                "id": "beijing_unemployment_benefit_standard",
                "name": "北京市失业保险金月发放标准（分档）",
                "authority": "北京市人力资源和社会保障局",
                "source_url": PAGES["unemployment-benefit-2025"][1],
                "use": "计算「未依法缴纳失业保险费导致不能享受失业保险待遇」的损失赔偿"
                       "（赔偿责任依据：《北京市失业保险规定》第三十一条——用人单位不按规定缴纳失业保险费"
                       "或不按规定及时转移档案关系，致使失业人员不能享受失业保险待遇或影响其再就业的，应当赔偿损失）；"
                       "计发月数按《北京市失业保险规定》第十七条（见 months_table），"
                       "标准按失业前累计缴费年限取档，从第 13 个月起一律按第一档发放",
                "entries": [
                    {
                        "effective_from": unemp["effective_from"],
                        "doc_no": unemp["doc_no"],
                        "tiers": unemp["tiers"],
                        "tier_after_month": unemp["tier_after_month"],
                        "tier_after_monthly": unemp["tier_after_monthly"],
                        "source_url": PAGES["unemployment-benefit-2025"][1],
                    }
                ],
                "months_table": {
                    "legal_basis": "《北京市失业保险规定》第十七条（1999 年市政府令第 38 号发布，"
                                   "经 2007 年市政府令第 190 号修改）",
                    "source_url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56688.html",
                    "rules": [
                        {"min_years": 1, "max_years": 2, "months": 3},
                        {"min_years": 2, "max_years": 3, "months": 6},
                        {"min_years": 3, "max_years": 4, "months": 9},
                        {"min_years": 4, "max_years": 5, "months": 12},
                        {"min_years": 5, "max_years": None,
                         "months_formula": "每满 1 年增发 1 个月；领取期限最长不超过 24 个月"},
                    ],
                    "note": "领取失业保险金的实体条件见《北京市失业保险规定》第十三条与《社会保险法》第四十五条"
                            "（缴费满 1 年、非因本人意愿中断就业、已办理失业登记并有求职要求）；"
                            "依《劳动合同法》第三十八条解除劳动合同属于「非因本人意愿中断就业」",
                },
                "gaps": ["2025-09-01 之前的历年分档标准（逐年调整通告）尚未归档，"
                         "历史案件按案件时点取值时须先补档当年通告原件"],
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
            {
                "id": "unemployment_benefit_months_over_5y",
                "title": "失业保险金计发月数在「累计缴费 5 年以上」段的起算口径",
                "rule": "《北京市失业保险规定》第十七条第（五）项仅表述「按每满一年增发一个月失业保险金的"
                        "办法计算，确定增发的月数」，未给出增发的起算基数。本表通过（采用值）："
                        "月数 = 12（对应「4 年以上不满 5 年」档） + （满整年数 − 4），24 个月封顶"
                        "（即满 16 年达到封顶）",
                "candidates": [
                    {"id": "base_12_plus_one_per_year",
                     "rule": "12 +（满整年数 − 4），封顶 24",
                     "note": "与 1—5 年段「每满 1 年 3 个月」的档位（4—5 年 = 12 个月）衔接；采用值"},
                    {"id": "years_times_3_continued",
                     "rule": "满整年数 × 3，封顶 24",
                     "note": "若把「增发」理解为延续 1—5 年段每年 3 个月的口径"},
                ],
                "status": "pending-official-confirmation",
                "source_url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56688.html",
                "note": "官方页面（首都之窗失业保险金热点问答、海淀/门头沟问答）均只复述条文，未给算例；"
                        "计算侧命中时输出待核实提示，正式文书前向 12333 或经办机构确认",
            },
            {
                "id": "maternity_benefit_days",
                "title": "生育津贴计发天数（是否含生育奖励假）",
                "rule": "京人社医发〔2011〕334号第三条只写「按职工所在用人单位月缴费平均工资除以 30 天"
                        "再乘以产假天数计发」，未列明天数。北京实务中同时存在 98 天（国家产假）与 128 天"
                        "（98 天 + 30 天生育奖励假）两种口径，且各期政策不同",
                "candidates": [
                    {"id": "98", "days": 98, "note": "《女职工劳动保护特别规定》第七条国家产假天数"},
                    {"id": "128", "days": 128,
                     "note": "98 天产假 + 30 天生育奖励假；见于经办实务与媒体解读，未定位到官方原文页，须核实"},
                ],
                "status": "pending-official-confirmation",
                "source_url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56936.html",
                "note": "计算侧要求调用方显式传入计发天数，不设默认值；《北京市企业职工生育保险规定》"
                        "（2005 年市政府令第 154 号）原文尚未归档",
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
        title="北京劳动仲裁计算参数表（社平工资口径、最低工资标准、失业保险金标准）", topic=TOPIC,
        source_url=PAGES["compensation-cap-notice"][1],
        authority="北京市人力资源和社会保障局 / 北京市统计局（按条目）",
        original_filename="parameters.yaml", region=REGION,
        notes="参数台账：series 为时间序列（含生效区间/数据年度与来源 URL），decisions 为口径决定（含法条与生效日期），"
              "gaps 为尚未取得官方来源的年份",
    )
    print("SHA-256:", sha256(content)[:16])


if __name__ == "__main__":
    main()
