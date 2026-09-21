"""阶段 11：归档工伤待遇参数（北京标准 + 全国标准表）并并入 parameters.yaml。

来源（均为官方）：
- 《工伤保险条例》（国务院令第375号公布、第586号修订）→ 已归档于 regions/national/regulations/administrative-regulations/
- 《关于北京市工伤保险基金支出项目标准及相关问题的通知》（京人社工发〔2011〕384号，首都之窗 现行有效）
- 《北京市实施〈工伤保险条例〉若干规定》（北京市人民政府令第242号）

本阶段在 stage10 生成的 parameters.yaml 基础上追加 series/decisions（幂等：同 id 覆盖）。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402
from common import fetch_text, html_to_md, save_binary, save_md, sha256  # noqa: E402

REPO = pathlib.Path("/Users/abaaba/workspace/projects/labor_lawyer")
REGION = "municipalities/beijing"
TOPIC = "statistics"
BASE = "statistics"
PARAMS = REPO / "regions" / REGION / BASE / "parameters.yaml"

INJURY_NOTICE = ("京人社工发〔2011〕384号 关于北京市工伤保险基金支出项目标准及相关问题的通知",
                 "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_57148.html",
                 "北京市人力资源和社会保障局、北京市财政局")

# 《工伤保险条例》第三十五至三十七条：一次性伤残补助金月数（本人工资）
LUMP_SUM_MONTHS = {1: 27, 2: 25, 3: 23, 4: 21, 5: 18, 6: 16, 7: 13, 8: 11, 9: 9, 10: 7}
# 第三十五条、第三十六条：伤残津贴（本人工资比例）
ALLOWANCE_RATE = {1: "0.90", 2: "0.85", 3: "0.80", 4: "0.75", 5: "0.70", 6: "0.60"}
# 第三十四条：生活护理费（统筹地区上年度职工月平均工资比例）
NURSING_RATE = [("完全生活自理障碍", "0.50"), ("大部分生活自理障碍", "0.40"), ("部分生活自理障碍", "0.30")]
# 京人社工发〔2011〕384号 第五条：北京一次性工伤医疗补助金 / 伤残就业补助金（本市上年度职工月平均工资月数）
BEIJING_MEDICAL_EMPLOYMENT = {5: (18, 18), 6: (15, 15), 7: (12, 12), 8: (9, 9), 9: (6, 6), 10: (3, 3)}


def main() -> None:
    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))

    # 归档 384 号通知原文
    title, url, authority = INJURY_NOTICE
    html = fetch_text(url)
    _, date, md = html_to_md(html, url)
    save_md(
        f"{BASE}/sources/injury-benefits-notice-384.md", title,
        f"> 来源：{url}\n> 发布机关：{authority}\n> 说明：《工伤保险条例》与《北京市实施〈工伤保险条例〉若干规定》"
        f"（市政府第242号令）配套的北京工伤待遇标准\n\n{md}\n",
        topic=TOPIC, source_url=url, published_at=date, authority=authority, region=REGION,
        notes="工伤待遇标准来源页面原文",
    )

    injury_series = [
        {
            "id": "injury_lump_sum_months",
            "name": "一次性伤残补助金月数（× 本人工资）",
            "authority": "国务院（《工伤保险条例》第35—37条）",
            "source_url": "regions/national/regulations/administrative-regulations/工伤保险条例.md",
            "use": "一次性伤残补助金 = 本人工资 × 月数；本人工资指受伤前 12 个月平均月缴费工资",
            "entries": [{"grade": g, "months": m} for g, m in sorted(LUMP_SUM_MONTHS.items())],
        },
        {
            "id": "injury_disability_allowance_rate",
            "name": "伤残津贴比例（× 本人工资）",
            "authority": "国务院（《工伤保险条例》第35、36条）",
            "source_url": "regions/national/regulations/administrative-regulations/工伤保险条例.md",
            "use": "一至四级由工伤保险基金按月支付；五至六级由用人单位在难以安排工作时按月支付",
            "entries": [{"grade": g, "rate": r} for g, r in sorted(ALLOWANCE_RATE.items())],
        },
        {
            "id": "injury_nursing_rate",
            "name": "生活护理费比例（× 统筹地区上年度职工月平均工资）",
            "authority": "国务院（《工伤保险条例》第34条）",
            "source_url": "regions/national/regulations/administrative-regulations/工伤保险条例.md",
            "entries": [{"level": lv, "rate": r} for lv, r in NURSING_RATE],
        },
        {
            "id": "injury_beijing_medical_employment_months",
            "name": "北京一次性工伤医疗补助金 / 一次性伤残就业补助金月数（× 本市上年度职工月平均工资）",
            "authority": "北京市人力资源和社会保障局、北京市财政局",
            "source_url": url,
            "use": "解除或终止劳动关系时支付；医疗补助金由工伤保险基金支付，就业补助金由用人单位支付",
            "entries": [{"grade": g, "medical_months": mm, "employment_months": em}
                        for g, (mm, em) in sorted(BEIJING_MEDICAL_EMPLOYMENT.items())],
        },
        {
            "id": "injury_death_benefits",
            "name": "因工死亡待遇构成（《工伤保险条例》第39条）",
            "authority": "国务院",
            "source_url": "regions/national/regulations/administrative-regulations/工伤保险条例.md",
            "entries": [
                {"item": "丧葬补助金", "formula": "统筹地区上年度职工月平均工资 × 6"},
                {"item": "一次性工亡补助金", "formula": "上年度全国城镇居民人均可支配收入 × 20"},
                {"item": "供养亲属抚恤金", "formula": "本人工资 × 配偶 40% / 其他亲属每人 30%（孤寡老人或孤儿每人再加 10%），"
                                                    "各供养亲属合计不超过本人工资"},
            ],
            "gaps": ["「上年度全国城镇居民人均可支配收入」序列尚未归档（来源：国家统计局年度统计公报），"
                     "计算时需显式传入并注明来源"],
        },
    ]
    decision = {
        "id": "injury_wage_base",
        "title": "工伤待遇中「本市上年度职工月平均工资」的取值序列",
        "status": "pending-official-confirmation",
        "rule": "京人社工发〔2011〕384号等文件仅表述为「本市上年度职工月平均工资」，未指明采用哪一组统计序列",
        "candidates": [
            {"series": "beijing_full_caliber_avg_wage", "note": "人社局发布的社保经办口径，社保系统常用"},
            {"series": "beijing_legal_entity_avg_wage", "note": "统计局法人单位口径，经济补偿封顶使用"},
        ],
        "note": "计算时**必须显式选择序列**并输出提示；正式出具意见前建议向社保经办机构/12333 确认本地口径",
    }

    by_id = {s["id"]: i for i, s in enumerate(params["series"])}
    for s in injury_series:
        if s["id"] in by_id:
            params["series"][by_id[s["id"]]] = s
        else:
            params["series"].append(s)
    decisions = {d["id"]: i for i, d in enumerate(params["decisions"])}
    if decision["id"] in decisions:
        params["decisions"][decisions[decision["id"]]] = decision
    else:
        params["decisions"].append(decision)
    params["series_updated_at"] = params.get("updated_at")

    content = (
        "# 北京劳动仲裁计算参数（由 tools/crawl/stage10/stage11 生成）\n"
        "# 每条数值均需可追溯至官方页面；candidates_unverified 禁止直接用于计算；\n"
        "# gaps 表示尚未取得官方来源，需补齐后写入 entries。\n"
        + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)
    ).encode()
    save_binary(
        f"{BASE}/parameters.yaml", content,
        title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic=TOPIC,
        source_url=params["decisions"][0]["source_url"],
        authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
        original_filename="parameters.yaml", region=REGION,
        notes="参数台账：series（含工伤对照表）、decisions（含工伤社平口径待确认项）、gaps",
    )
    print(f"parameters.yaml 更新：series {len(params['series'])} 组 / decisions {len(params['decisions'])} 项 "
          f"/ sha256 {sha256(content)[:12]}")


if __name__ == "__main__":
    main()
