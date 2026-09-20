"""阶段 7：归档国家层面劳动法律法规（法律 / 行政法规 / 司法解释 / 部门规章）。

来源：
- 人力资源和社会保障部「政策法规」法律、行政法规栏目与「国家规章库」（www.mohrss.gov.cn）
- 最高人民法院（www.court.gov.cn / gongbao.court.gov.cn，司法解释公报）
页面正文抓取为 Markdown，页面附带的官方 PDF/DOCX 附件一并归档。
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch, fetch_text, html_to_md, save_binary, save_md  # noqa: E402
from stage4_regs import attachments  # noqa: E402

REGION = "national"
TOPIC = "regulations"
LEVEL = "national"
MOHRSS = "https://www.mohrss.gov.cn"
MP = MOHRSS + "/xxgk2020/fdzdgknr/zcfg"
GZ = MOHRSS + "/xxgk2020/gzk/gz"

# (子目录, 标题, URL, 文号/效力说明)
DOCS: list[tuple[str, str, str, str]] = [
    # ---------------- 法律 ----------------
    ("laws", "中华人民共和国劳动法", f"{MP}/fl/202011/t20201102_394625.html",
     "1994年7月5日通过，2018年12月29日修正；现行有效"),
    ("laws", "中华人民共和国劳动合同法", f"{MP}/fl/202011/t20201102_394622.html",
     "2007年6月29日通过，2012年12月28日修正；现行有效"),
    ("laws", "中华人民共和国劳动争议调解仲裁法", f"{MP}/fl/202011/t20201102_394628.html",
     "2007年12月29日通过，2008年5月1日施行；现行有效"),
    ("laws", "中华人民共和国社会保险法", f"{MP}/fl/202011/t20201102_394629.html",
     "2010年10月28日通过，2018年12月29日修正；现行有效"),
    ("laws", "中华人民共和国就业促进法", f"{MP}/fl/202011/t20201102_394626.html",
     "2007年8月30日通过，2015年4月24日修正；现行有效"),
    ("laws", "中华人民共和国工会法", f"{MP}/fl/202011/t20201102_394624.html",
     "1992年4月3日通过，2021年12月24日修正；现行有效"),
    ("laws", "全国人民代表大会常务委员会关于实施渐进式延迟法定退休年龄的决定",
     f"{MP}/fl/202411/t20241125_530761.html", "2024年9月13日通过，2025年1月1日施行"),

    # ---------------- 行政法规 ----------------
    ("administrative-regulations", "中华人民共和国劳动合同法实施条例",
     f"{MP}/fg/202011/t20201103_394939.html", "国务院令第535号，2008年9月18日公布施行"),
    ("administrative-regulations", "工伤保险条例", f"{MP}/fg/202011/t20201103_394950.html",
     "国务院令第375号公布，国务院令第586号修订，2011年1月1日施行"),
    ("administrative-regulations", "职工带薪年休假条例", f"{MP}/fg/202011/t20201103_394938.html",
     "国务院令第514号，2008年1月1日施行"),
    ("administrative-regulations", "女职工劳动保护特别规定", f"{MP}/fg/202011/t20201103_394947.html",
     "国务院令第619号，2012年4月28日公布施行"),
    ("administrative-regulations", "失业保险条例", f"{MP}/fg/202011/t20201103_394936.html",
     "国务院令第258号，1999年1月22日施行"),
    ("administrative-regulations", "保障农民工工资支付条例", f"{MP}/fg/202011/t20201103_394928.html",
     "国务院令第724号，2020年5月1日施行"),
    ("administrative-regulations", "国务院关于职工工作时间的规定",
     f"{MP}/fg/202011/t20201103_394935.html", "国务院令第174号修订，1995年5月1日施行"),
    ("administrative-regulations", "事业单位人事管理条例", f"{MP}/fg/202011/t20201103_394930.html",
     "国务院令第652号，2014年7月1日施行"),
    ("administrative-regulations", "社会保险费征缴暂行条例", f"{MP}/fg/202011/t20201103_394934.html",
     "国务院令第259号，1999年1月22日施行"),
    ("administrative-regulations", "劳动保障监察条例", f"{MP}/fg/202011/t20201103_394944.html",
     "国务院令第423号，2004年12月1日施行"),
    ("administrative-regulations", "全国年节及纪念日放假办法", f"{MP}/fg/202011/t20201103_394937.html",
     "国务院令第644号修订，2014年1月1日施行"),
    ("administrative-regulations", "社会保险经办条例", f"{MP}/fg/202312/t20231201_509829.html",
     "国务院令第765号，2023年12月1日施行"),

    # ---------------- 司法解释 ----------------
    ("judicial-interpretations", "最高人民法院关于审理劳动争议案件适用法律问题的解释（一）",
     "https://www.court.gov.cn/fabu/xiangqing/282121.html", "法释〔2020〕26号，2021年1月1日施行"),
    ("judicial-interpretations", "最高人民法院关于审理劳动争议案件适用法律问题的解释（二）",
     "http://gongbao.court.gov.cn/Details/bb72019c45453f84d920bd6375573e.html",
     "最高人民法院公报发布，2025年施行"),

    # ---------------- 部门规章 ----------------
    ("department-rules", "劳动人事争议仲裁办案规则", f"{GZ}/202112/t20211228_431661.html",
     "人社部令第33号，2017年7月1日施行"),
    ("department-rules", "劳动人事争议仲裁组织规则", f"{GZ}/202112/t20211228_431665.html",
     "人社部令第34号，2017年7月1日施行"),
    ("department-rules", "企业劳动争议协商调解规定", f"{GZ}/202112/t20211228_431626.html",
     "人社部令第17号，2012年1月1日施行"),
    ("department-rules", "企业职工带薪年休假实施办法", f"{GZ}/202112/t20211228_431596.html",
     "人社部令第1号，2008年9月18日施行"),
    ("department-rules", "最低工资规定", f"{GZ}/202112/t20211228_431587.html",
     "劳动和社会保障部令第21号，2004年3月1日施行"),
    ("department-rules", "工资支付暂行规定", f"{GZ}/202112/t20211228_431557.html",
     "劳部发〔1994〕489号"),
    ("department-rules", "劳务派遣暂行规定", f"{GZ}/202112/t20211228_431639.html",
     "人社部令第22号，2014年3月1日施行"),
    ("department-rules", "劳动能力鉴定管理办法", f"{GZ}/202505/t20250523_542492.html",
     "人社部规章（工伤劳动能力鉴定）"),
    ("department-rules", "超龄劳动者基本权益保障暂行规定", f"{GZ}/202605/t20260525_576849.html",
     "人社部规章，涉及超龄劳动者权益保障"),
]

BAD = re.compile(r'[\\/:*?"<>|\s]+')


def attach_local_name(title: str, name: str) -> str:
    safe = re.sub(r"[/\\]+", "-", name)
    return f"{BAD.sub('-', title)[:60]}-{safe}"


def main() -> None:
    for sub, title, url, note in DOCS:
        try:
            html = fetch_text(url)
            _, date, md = html_to_md(html, url)
        except Exception as exc:  # noqa: BLE001
            print("  FAIL", title, exc)
            continue
        if len(md) < 300:
            print("  SKIP(short)", title, len(md), url)
            continue
        fname = f"{BAD.sub('-', title).strip('-')}.md"
        body = (
            f"> 效力层级：{sub}\n> 来源：{url}\n> 发布信息：{note}\n\n{md}\n"
        )
        save_md(
            f"regulations/{sub}/{fname}", title, body, topic=TOPIC, source_url=url,
            published_at=date, authority="人力资源和社会保障部 / 最高人民法院（按来源）",
            notes=f"{note}；正文来源页面发布时间 {date or '未标注'}",
            region=REGION, level=LEVEL,
        )
        for abs_url, name in attachments(html, url):
            try:
                data = fetch(abs_url, referer=url)
            except Exception as exc:  # noqa: BLE001
                print("  ATT FAIL", abs_url, exc)
                continue
            save_binary(
                f"regulations/files/{attach_local_name(title, name)}", data,
                title=f"{title} · 附件 {name}", topic=TOPIC, source_url=url,
                download_url=abs_url, published_at=date, original_filename=name,
                notes="官方页面附件（PDF/DOCX 原件）", region=REGION, level=LEVEL,
            )


if __name__ == "__main__":
    main()
