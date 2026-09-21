"""阶段 19：山西省社保参数补档（首个非北京地区）。

背景：为「确认劳动关系 + 社保补缴」类案件建立山西地区的社保缴费基数与参数台账。
此前事实层只有北京 + 国家层面，山西完全空白。

脱敏要求：本阶段产出进入 git，**不得写入任何当事人信息**（姓名、身份证号、联系方式、
具体用人单位、案号）。地区只到市/县一级的通用表述（如「属地社保经办机构」）。

归档原则（沿用本项目纪律）：
- **只把官方页面登记的数值放进 `entries`**（可参与计算）；
- 官方页面已不保留、只能从二手转载页取得的数值，一律进 `candidates_unverified` 并在
  notes 写明来源层级，**不得静默用于计算**；
- 取不到的年度进 `gaps`，绝不推算填充。

已知的取数边界（本次查证的结论）：
- 山西省人社厅官网「通知公告」栏目**只保留现行年度**的缴费基数通知，历年通知已下线；
- 山西省统计局官网「统计数据/数据信息」栏目只列最新年份，统计年鉴为 JS 渲染页，无法直取；
- 中国统计年鉴在线版 `stats.gov.cn/sj/ndsj/<年>/indexch.htm` 为 JS 渲染，纯 HTTP 抓取拿到 0 个链接；
- 因此 2005—2013 各年度社平工资/缴费基数上下限**未取得官方来源**，列入 gaps。
"""
from __future__ import annotations

import datetime
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import REPO, fetch_text, html_to_md, save_md, sha256  # noqa: E402

REGION = "municipalities/shanxi"
BASE = "statistics"
PARAMS_REL = f"{BASE}/parameters.yaml"

# ---------------------------------------------------------------- 待归档页面
DOCS = [
    # ① 官方：山西人社厅等四部门 2026 年缴费基数通知（现行有效）
    dict(
        rel="regulations/2026-08-21-关于公布2026年缴纳社会保险费基数标准等有关问题的通知.md",
        topic="regulations", region=REGION,
        url="https://rst.shanxi.gov.cn/zwyw/tzgg/202608/t20260826_10207826.shtml",
        authority="山西省人力资源和社会保障厅、山西省财政厅、国家税务总局山西省税务局、山西省医疗保障局",
        published_at="2026-08-21",
        notes="晋人社厅发〔2026〕27号；自2026年1月1日起执行。**官方页面（省人社厅官网）**。"
              "2025年全口径城镇单位就业人员平均工资84881元（月7073元）；"
              "2026年全省职工个人月缴费基数下限4244元、上限21219元。"
              "文内引用《山西省人民政府办公厅关于印发山西省降低社会保险费率实施方案的通知》"
              "（晋政办发〔2019〕26号）为费率依据。",
    ),
    # ② 官方：山西省统计局 2025 年三组工资数据
    dict(
        rel=f"{BASE}/sources/2025-山西省城镇非私营单位就业人员年平均工资.md",
        topic="statistics", region=REGION,
        url="https://tjj.shanxi.gov.cn/tjsj/sjxx/202606/t20260626_10160880.shtml",
        authority="山西省统计局", published_at="2026-06-26",
        notes="官方页面。用于核定缴费基数上下限的「城镇非私营单位」一侧口径。",
    ),
    dict(
        rel=f"{BASE}/sources/2025-山西省城镇私营单位就业人员年平均工资.md",
        topic="statistics", region=REGION,
        url="https://tjj.shanxi.gov.cn/tjsj/sjxx/202606/t20260626_10160875.shtml",
        authority="山西省统计局", published_at="2026-06-26",
        notes="官方页面。全口径平均工资 = 城镇非私营与城镇私营加权计算，两侧数据均需归档。",
    ),
    dict(
        rel=f"{BASE}/sources/2025-山西省规模以上企业就业人员年平均工资.md",
        topic="statistics", region=REGION,
        url="https://tjj.shanxi.gov.cn/tjsj/sjxx/202606/t20260626_10160884.shtml",
        authority="山西省统计局", published_at="2026-06-26",
        notes="官方页面。规模以上企业口径，与社保缴费基数口径不同，仅供参照。",
    ),
    # ③ 二手转载（官方页已下线）——仅作锚点，数值进 candidates_unverified
    dict(
        rel=f"{BASE}/sources/2014-缴费基数上下限-二手转载页.md",
        topic="statistics", region=REGION,
        url="https://www.cpic.com.cn/c/2021-05-31/1775348.shtml",
        authority="山西省人力资源和社会保障厅（归档来源：太平洋保险转载页，非政府网站）",
        published_at="2021-05-31",
        notes="**来源层级：二手转载（商业网站）**。载明 2014 年度全省在岗职工平均工资 48969 元，"
              "2014 年度养老缴费基数下限 2448 元、上限 12242 元；个体工商户/灵活就业三档 4081/2448/1632 元。"
              "数值仅作锚点，已登记为 candidates_unverified，未取得官方原文前不得用于计算。",
    ),
    dict(
        rel=f"{BASE}/sources/2019-缴费基数上下限-二手转载页.md",
        topic="statistics", region=REGION,
        url="https://zc.51shebao.com/detail/800162",
        authority="山西省人力资源和社会保障厅（归档来源：51社保HR政策库，非政府网站）",
        published_at="2019-06-06",
        notes="**来源层级：二手转载（商业网站）**。载明 2018 年全省全口径城镇单位就业人员平均工资 54783 元"
              "（月 4565 元），2019 年缴费基数下限 2739 元、上限 13695 元；"
              "并载「2018 年全省城镇非私营单位在岗职工月平均工资为 5639 元」。"
              "转载页附有省人社厅官方 .doc 链接（rst.shanxi.gov.cn），但该直链未验证可达。"
              "数值登记为 candidates_unverified。",
    ),
]

# ---------------------------------------------------------------- 参数台账
# 官方来源可直接登记为已验证条目；二手来源一律 candidates_unverified。
DECISIONS = [
    {
        "id": "shanxi_social_insurance_base_caliber",
        "title": "山西社保缴费基数的社平工资口径切换",
        "effective_from": "2019-01-01",
        "rule": "2019 年 1 月 1 日前，按上年度全省「城镇非私营单位在岗职工平均工资」的 60%—300% 核定"
                "缴费基数上下限；自 2019 年 1 月 1 日起，改按「全口径城镇单位就业人员平均工资」"
                "（城镇非私营与城镇私营加权）的 60%—300% 核定。",
        "legal_basis": "国办发〔2019〕13 号《降低社会保险费率综合方案》；晋政办发〔2019〕26 号"
                       "《山西省人民政府办公厅关于印发山西省降低社会保险费率实施方案的通知》",
        "note": "因口径切换，跨 2019 年的补缴需分段适用不同的社平工资序列，不能用一个基数贯穿。"
                "官方 2026 年基数通知本身即引用晋政办发〔2019〕26 号，可作为口径链条的第一环。",
    },
    {
        "id": "shanxi_pension_rates",
        "title": "山西企业职工基本养老保险缴费比例",
        "effective_from": "2019-05-01",
        "rule": "单位 16%、个人 8%。2019 年 5 月 1 日前单位比例为 20%。",
        "legal_basis": "国办发〔2019〕13 号；晋政办发〔2019〕26 号（**该文件原文尚未归档，待补**）",
        "status": "pending-official-confirmation",
        "note": "单位 20%→16% 的适用时点、以及医疗/失业/工伤/生育各险种的单位与个人费率，"
                "均未见官方原文归档；测算时按 20%（2005—2019.4）与 16%（2019.5 起）区间使用，需经办机构确认。",
    },
    {
        "id": "shanxi_backpayment_lookback",
        "title": "山西社保历史欠费补缴的可追溯年限与经办口径",
        "status": "pending-official-confirmation",
        "rule": "未检索到山西省关于用人单位历史欠费补缴可追溯年限的公开文件。"
                "全国层面：《社会保险费征缴暂行条例》《社会保险稽核办法》均未对清缴企业欠费设追诉期；"
                "《劳动保障监察条例》第 20 条的 2 年为行政执法时效，社保欠缴有连续状态的自行终了之日起算。",
        "evidence_chain": [
            "人社部《人社建字〔2017〕105 号》答复：地方经办机构追缴历史欠费并未限定追诉期；"
            "经办机构接到超过 2 年追诉期的投诉，一般也按程序受理",
            "《最高人民法院行政法官专业会议纪要（七）》：不得仅以《劳动保障监察条例》第 20 条 2 年为由不再查处",
            "《实施〈中华人民共和国社会保险法〉若干规定》（人社部令第 13 号）第 29 条："
            "2011-07-01 后的按社会保险法执行；**之前的按地方人民政府有关规定执行**",
        ],
        "note": "「2011-07-01 之前」这一段是否可补缴，取决于山西地方规定，必须到经办机构书面问询；"
                "**该答复同时决定后续走「补缴」还是「赔偿损失」两条完全不同的路径**，是本案最关键的未知项。",
    },
]

CANDIDATES = [
    {"data_year": 2012, "caliber": "城镇非私营单位在岗职工年平均工资", "annual": 44943,
     "source_note": "人社通（m12333.cn）转载，非政府网站；原表述「山西省2012年度全省城镇非私营单位在岗职工平均工资为44943元」",
     "derived_floor_monthly": 2247},
    {"data_year": 2014, "caliber": "全省在岗职工年平均工资", "annual": 48969,
     "source_note": "太平洋保险转载省人社厅发布，非政府网站；官方公布同口径缴费基数下限2448元、上限12242元",
     "derived_floor_monthly": 2448, "published_ceiling_monthly": 12242},
    {"data_year": 2018, "caliber": "全口径城镇单位就业人员年平均工资", "annual": 54783,
     "source_note": "51社保转载省人社厅发布，非政府网站；官方公布同口径2019年缴费基数下限2739元、上限13695元",
     "derived_floor_monthly": 2739, "published_ceiling_monthly": 13695},
    {"data_year": 2018, "caliber": "城镇非私营单位在岗职工月平均工资", "annual": 5639 * 12,
     "source_note": "51社保转载页原文「2018年全省城镇非私营单位在岗职工月平均工资为5639元」，"
                    "用于养老保险待遇计发（计发口径未随缴费基数口径同步调整）",
     "monthly": 5639},
]


def main() -> int:
    problems: list[str] = []
    fetched: dict[str, tuple[str, bytes]] = {}

    for doc in DOCS:
        url = doc["url"]
        try:
            raw = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{url}: {type(exc).__name__}: {exc}")
            print("  FAIL", url, exc)
            continue
        title, date, md = html_to_md(raw, url)
        if not md or len(md) < 200:
            problems.append(f"{url}: 正文过短({len(md)})")
            print("  FAIL(正文过短)", url)
            continue
        fetched[url] = (md, raw.encode())
        rec = save_md(
            doc["rel"], title or doc["rel"], md,
            topic=doc["topic"], source_url=url,
            published_at=doc.get("published_at") or date,
            authority=doc["authority"], notes=doc["notes"],
            region=doc["region"],
        )
        print(f"  saved {doc['rel']}  sha256={rec['content_hash'][:12]}…")

    entries_official = [
        {
            "series_id": "shanxi_social_insurance_base",
            "year": 2026,
            "document_no": "晋人社厅发〔2026〕27号",
            "effective_from": "2026-01-01",
            "full_caliber_annual": 84881,
            "full_caliber_monthly": 7073,
            "floor_monthly": 4244,
            "ceiling_monthly": 21219,
            "source_url": DOCS[0]["url"],
            "published_at": "2026-08-21",
            "statement": "2025年全口径城镇单位就业人员平均工资（全省城镇非私营单位就业人员平均工资和城镇私营单位"
                         "就业人员平均工资加权）为84881元，月平均工资为7073元。以此为依据，确定2026年全省参加企业"
                         "和机关事业单位社会保险职工个人缴纳社会保险费月缴费基数的下限为4244元，上限为21219元。",
            "source_page_sha256": sha256(fetched[DOCS[0]["url"]][1]) if DOCS[0]["url"] in fetched else None,
            "use": "社保缴费基数区间的确定（单位与个人）",
        },
    ]

    params = {
        "region": REGION,
        "topic": "statistics",
        "note": "山西省社保与工资参数台账。`entries` 只收录官方页面的数值；二手转载页数值一律进 "
                "`candidates_unverified` 且不得静默用于计算（计算侧需显式 allow_unverified）。"
                "取不到的年度列入 `gaps`，不得推算填充。"
                "**注意：计算层（legal-assistant）目前只读取北京与国家两张参数表，本表尚未接入计算模块。**",
        "series": [
            {
                "id": "shanxi_social_insurance_base",
                "name": "山西省社会保险费月缴费基数上下限（元/月）",
                "authority": "山西省人力资源和社会保障厅等四部门",
                "source_page": "https://rst.shanxi.gov.cn/zwyw/tzgg/",
                "use": "确定单位与个人社保缴费基数的上下限；本人工资低于下限的按下限缴、高于上限的按上限缴",
                "entries": entries_official,
                "candidates_unverified": CANDIDATES,
            },
            {
                "id": "shanxi_full_caliber_avg_wage",
                "name": "山西省全口径城镇单位就业人员平均工资（元/年）",
                "authority": "山西省统计局 → 山西省人力资源和社会保障厅核定发布",
                "source_page": "https://tjj.shanxi.gov.cn/tjsj/sjxx/",
                "use": "2019 年起核定社保缴费基数上下限的基准指标",
                "entries": [
                    {
                        "data_year": 2025, "caliber": "全口径城镇单位就业人员平均工资",
                        "annual": 84881, "monthly": 7073,
                        "source_url": DOCS[0]["url"], "published_at": "2026-08-26",
                        "statement": "2025年全口径城镇单位就业人员平均工资……为84881元，月平均工资为7073元。",
                        "note": "由省人社厅基数通知转述统计口径数值；分侧原始数据见 statistics/sources/ 三份统计局页面",
                    },
                ],
                "candidates_unverified": [c for c in CANDIDATES if "全口径" in c["caliber"]],
            },
            {
                "id": "shanxi_statistics_2025_wage",
                "name": "山西省 2025 年分口径就业人员年平均工资（元/年）",
                "authority": "山西省统计局",
                "source_page": "https://tjj.shanxi.gov.cn/tjsj/sjxx/",
                "use": "全口径平均工资的两侧原始数据；规模以上企业口径仅作参照",
                "entries": [
                    {"data_year": 2025, "caliber": "城镇非私营单位就业人员", "annual": 101538,
                     "source_url": DOCS[1]["url"], "published_at": "2026-06-26"},
                    {"data_year": 2025, "caliber": "城镇私营单位就业人员", "annual": 52113,
                     "source_url": DOCS[2]["url"], "published_at": "2026-06-26"},
                    {"data_year": 2025, "caliber": "规模以上企业就业人员", "annual": 94650,
                     "source_url": DOCS[3]["url"], "published_at": "2026-06-26",
                     "note": "与社保缴费基数口径无关，仅参照"},
                ],
            },
        ],
        "decisions": DECISIONS,
        "gaps": [
            "**2005—2013 各年度全省在岗职工年平均工资 / 缴费基数上下限：未取得官方来源。**"
            "省人社厅「通知公告」栏目只保留现行年度通知（历年通知已下线）；省统计局「统计数据/数据信息」"
            "只列最新年份；中国统计年鉴在线版为 JS 渲染页，纯 HTTP 抓取不可用。"
            "取数路径：省统计年鉴纸质/PDF 版；或向属地社保经办机构、市人社局调取历年基数文件。",
            "**晋政办发〔2019〕26 号（山西省降低社会保险费率实施方案）原文未归档**——"
            "它是山西养老单位 20%→16% 的费率依据，需补齐。",
            "**山西省关于用人单位历史欠费补缴可追溯年限的公开文件未检索到**（见 decisions.shanxi_backpayment_lookback）。",
            "**山西省裁审口径未归档**：确认劳动关系是否适用仲裁时效、养老保险待遇损失赔偿如何计算，"
            "均未检索到山西高院/山西省人社厅的公开解答。",
            "**各险种单位费率的市级差异未取得**（医疗/失业/工伤/生育）——各市费率不尽相同，测算时按「其他四险合计约 10%」笼统替代，误差直接进金额；须向属地经办机构核实当年费率。",
        ]
        + [f"页面抓取失败：{p}" for p in problems],
        "updated_at": datetime.date.today().isoformat(),
    }

    content = (
        "# 山西省社保参数台账（由 tools/crawl/stage18_shanxi_social_insurance.py 生成）\n"
        "# entries 只收官方页面数值；二手来源进 candidates_unverified；取不到的进 gaps。\n"
        + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)
    ).encode()

    from common import save_binary  # 局部导入，避免与 save_md 混淆

    # 注意：region 参数已负责 `regions/<region>/` 前缀，rel 只能是其下的相对路径，
    # 再带一遍 region 会写成 regions/municipalities/shanxi/municipalities/shanxi/...（实测踩过）。
    save_binary(
        PARAMS_REL, content,
        title="山西省社保参数台账（缴费基数上下限、全口径平均工资、费率与缺口）",
        topic="statistics",
        source_url="https://rst.shanxi.gov.cn/zwyw/tzgg/",
        authority="山西省人力资源和社会保障厅 / 山西省统计局",
        original_filename="parameters.yaml", region=REGION,
        notes=f"官方条目 {len(entries_official)} 条；候选（二手来源）{len(CANDIDATES)} 条；缺口 {len(params['gaps'])} 项",
    )
    print(f"\nregions/{REGION}/{PARAMS_REL} 已生成：官方条目 {len(entries_official)}、"
          f"候选 {len(CANDIDATES)}、口径决策 {len(DECISIONS)}、缺口 {len(params['gaps'])}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
