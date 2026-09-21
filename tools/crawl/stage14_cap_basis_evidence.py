"""阶段 14：归档「经济补偿封顶基数」口径链条的官方证据，并更新参数表缺口说明。

背景（本轮实证）：
- 北京市人力资源和社会保障局《关于经济补偿封顶基数的通告》（2020-07-02）确认：
  我市将「北京市法人单位从业人员平均工资」作为计算经济补偿的封顶基数，**数据由统计部门发布**，
  通告本身不载数值，指引到北京市统计局/国家统计局北京调查总队网站查询。
- 北京市统计局「政民互动·统计咨询」答复确认：统计局对外发布的是「城镇非私营单位就业人员平均工资」
  与「城镇私营单位就业人员平均工资」两个口径；经济补偿封顶基数的计算依据需咨询市人社局；
  劳动工资年度数据经国家统计局审核评估后，**大约每年 6 月**上传至统计局官网「统计部门发布计划」栏目。

结论：2019—2025 年「法人单位从业人员平均工资」数值未出现在两个网站可检索的公开页面中，
需在统计局「统计部门发布计划」栏目（每年 6 月）取数或电话核实；因此 candidates_unverified 继续隔离。
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import yaml  # noqa: E402
from common import fetch_text, html_to_md, save_binary, save_md  # noqa: E402

REPO = pathlib.Path("/Users/abaaba/workspace/projects/labor_lawyer")
REGION = "municipalities/beijing"
BASE = "statistics"
PARAMS = REPO / "regions" / REGION / BASE / "parameters.yaml"

SOURCES = [   # (归档文件名, 标题, URL, 发布机关, 说明)
    ("cap-basis-notice-2020.md", "经济补偿封顶基数通告（2020-07-02）",
     "https://rsj.beijing.gov.cn/xxgk/tzgg/202007/t20200702_1937157.html",
     "北京市人力资源和社会保障局",
     "确认封顶基数采用「法人单位从业人员平均工资」，数据由统计部门发布"),
    ("tjj-faq-cap-basis-publish-time.md", "统计局答复：2024年北京法人单位从业人员平均工资统计结果公布时间",
     "https://tjj.beijing.gov.cn/hudong/xinxiang/tjj/sindex/bjah-index-dept!detail.action?originalId=AH25021301385",
     "北京市统计局",
     "口径说明：劳动工资年度数据约每年 6 月上传至「统计部门发布计划」栏目；含咨询电话"),
    ("tjj-faq-cap-basis-2024.md", "统计局答复：咨询2024年北京法人单位从业人员平均工资",
     "https://tjj.beijing.gov.cn/hudong/xinxiang/tjj/sindex/bjah-index-dept!detail.action?originalId=AH25070400999",
     "北京市统计局",
     "口径说明：统计局公开序列为城镇非私营/私营单位就业人员平均工资；封顶基数请咨询市人社局"),
    ("tjj-faq-cap-basis-2025.md", "统计局答复：2025年法人单位从业人员平均工资",
     "https://tjj.beijing.gov.cn/hudong/xinxiang/tjj/sindex/bjah-index-dept!detail.action?originalId=AH26012801058",
     "北京市统计局",
     "口径说明：截至答复时 2024、2025 年法人单位从业人员平均工资尚未公布"),
]


def clean(title: str, md: str) -> str:
    body = re.sub(r"\n{3,}", "\n\n", md)
    body = "\n".join(l for l in body.split("\n") if l.strip())
    return f"# {title}\n\n{body}\n"


def main() -> None:
    archived = []
    for filename, title, url, authority, note in SOURCES:
        html = fetch_text(url)
        _, published, md = html_to_md(html, url)
        save_md(f"{BASE}/sources/{filename}",
                f"{title}（原页面归档）", clean(title, md),
                topic=BASE, source_url=url, published_at=published, authority=authority,
                region=REGION, notes=note)
        archived.append((title, url))
        print(f"  archived: {title}")

    params = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    series = next(s for s in params["series"] if s["id"] == "beijing_legal_entity_avg_wage")
    series["gaps"] = [
        "2019—2025 年度官方数值未出现在统计局与人社局网站可检索的公开页面中："
        "人社局通告仅确认口径（「法人单位从业人员平均工资」）并要求到统计局网站查询数值；"
        "统计局公开序列仅「城镇非私营单位就业人员平均工资」「城镇私营单位就业人员平均工资」，"
        "且答复称劳动工资年度数据约每年 6 月上传至官网「统计部门发布计划」栏目。",
        f"取数路径（待执行）：统计局官网「统计数据 → 统计部门发布计划」栏目每年 6 月发布；"
        f"或电话核实：北京市统计局 010-55529938 / 政府信息公开咨询 010-55533848 / "
        f"国家统计局北京调查总队 010-55533513。",
        "candidates_unverified 中的数值来自律所/媒体转述，仅供人工核对，禁止直接用于计算；"
        "取得官方页面后用 tools/crawl/stage12_promote_wage.py 提升为已验证条目。",
    ]
    decisions = {d["id"]: i for i, d in enumerate(params["decisions"])}
    cap = params["decisions"][decisions["economic_compensation_cap_basis"]]
    cap["evidence_chain"] = [
        "北京市人力资源和社会保障局《关于按照法人单位从业人员平均工资计算经济补偿封顶基数的通告》"
        "（2019-08-16，载 2018 年数值 127107 元/年）",
        "北京市人力资源和社会保障局《关于经济补偿封顶基数的通告》（2020-07-02）：口径不变，"
        "数值由统计部门发布，指引到统计局网站查询",
        "北京市统计局统计咨询答复（2024/2025 年度）：统计局公开序列为城镇非私营/私营单位；"
        "劳动工资年度数据约每年 6 月上传「统计部门发布计划」栏目",
    ]
    cap["data_location_unverified"] = ("统计局官网「统计数据 → 统计部门发布计划」栏目"
                                       "（每年 6 月），需人工或电话核实后入库")

    content = ("# 北京劳动仲裁计算参数（由 tools/crawl 生成，勿手改数值）\n"
               + yaml.safe_dump(params, allow_unicode=True, sort_keys=False, width=200)).encode()
    save_binary(f"{BASE}/parameters.yaml", content,
                title="北京劳动仲裁计算参数表（工资口径、最低工资、工伤待遇）", topic=BASE,
                source_url=SOURCES[0][2],
                authority="北京市人力资源和社会保障局 / 北京市统计局 / 国务院（按条目）",
                original_filename="parameters.yaml", region=REGION,
                notes="更新：封顶基数的口径链条证据与取数路径（阶段 14）")
    print(f"parameters.yaml 已更新（封顶口径证据 {len(cap['evidence_chain'])} 条，缺口 {len(series['gaps'])} 条）")


if __name__ == "__main__":
    main()
