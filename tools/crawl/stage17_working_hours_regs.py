"""阶段 17：加班与工时口径的折算依据、加班工资规范性文件补档。

补档动机：这几份文件此前只被「案例评述引用」或「计算模块注释」间接提到，
事实层没有归档原文，导致：
- 21.75 天 / 174 小时的折算依据在计算模块中被直接使用，却无原文可追溯；
- 北京加班工资的 150%/200%/300% 与基数三级顺序只见于案例转述；
- 劳社部发〔2008〕3号 已被人社部发〔2025〕2号 废止，但归档中查不到这条沿革。

归档内容（全部为官方页面）：
- 人社部发〔2025〕2号   现行折算依据（月工作日 20.67 / 月计薪天数 21.75）
- 劳社部发〔2008〕3号   已废止的旧折算依据（月工作日 20.83），保留沿革
- 人社厅函〔2020〕135号 假期加班工资计算问题的复函（假期内 300%/200% 分段）
- 北京市工资支付规定    2003 年市政府令第 142 号（加班工资与基数口径的北京落地）
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch_text, html_to_md, save_md  # noqa: E402

NATIONAL = "national"
BEIJING = "municipalities/beijing"

DOCS = [
    {
        "rel": "regulations/department-rules/人力资源社会保障部关于职工全年月平均工作时间和工资折算问题的通知.md",
        "title": "人力资源社会保障部关于职工全年月平均工作时间和工资折算问题的通知",
        "region": NATIONAL,
        "topic": "regulations",
        "url": "https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/zcfg/gfxwj/ldgx/202501/t20250101_533693.html",
        "authority": "人力资源和社会保障部",
        "published_at": "2025-01-01",
        "notes": "人社部发〔2025〕2号；自2025年1月1日起施行；现行有效。"
                 "制度工作时间：年工作日248天、月工作日20.67天（原文）；"
                 "工资折算：日工资=月工资收入÷月计薪天数，月计薪天数21.75天（未变）。"
                 "本通知第三条明令废止劳社部发〔2008〕3号。",
    },
    {
        "rel": "regulations/department-rules/劳动和社会保障部关于职工全年月平均工作时间和工资折算问题的通知.md",
        "title": "劳动和社会保障部关于职工全年月平均工作时间和工资折算问题的通知",
        "region": NATIONAL,
        "topic": "regulations",
        "url": "https://rsj.yueyang.gov.cn/7719/7725/content_472965.html",
        "authority": "劳动和社会保障部（归档来源：岳阳市人力资源和社会保障局转载页）",
        "published_at": "2008-01-03",
        "notes": "劳社部发〔2008〕3号；已废止（人社部发〔2025〕2号第三条，自2025年1月1日起废止），"
                 "保留归档用于沿革与旧口径核对：年工作日250天、月工作日20.83天；月计薪天数21.75天（未变）。"
                 "**来源层级说明**：人社部原刊载页 "
                 "https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/zcfg/gfxwj/ldgx/202011/t20201102_394696.html "
                 "已 404，人社部「规范性文件·劳动关系」栏目亦只保留现行 2025 年通知；"
                 "故本件以地方人社局（政府网站）转载页归档，正文与官方表述一致，但属转载来源。"
                 "页面正文另含其废止的劳社部发〔2000〕8号（20.92天口径），一并保留。",
        "status": "superseded",
    },
    {
        "rel": "regulations/department-rules/人力资源社会保障部办公厅关于2020年国庆节、中秋节假期加班工资计算问题的复函.md",
        "title": "人力资源社会保障部办公厅关于2020年国庆节、中秋节假期加班工资计算问题的复函",
        "region": NATIONAL,
        "topic": "regulations",
        "url": "https://www.mohrss.gov.cn/xxgk2020/fdzdgknr/zcfg/gfxwj/ldgx/202401/t20240131_513082.html",
        "authority": "人力资源和社会保障部办公厅",
        "published_at": "2020-09-18",
        "notes": "人社厅函〔2020〕135号；现行有效。"
                 "明确假期内分段：10月1日至4日（含国庆与中秋重叠日）按300%，"
                 "10月5日至8日先安排补休、不能补休按200%。"
                 "未涉及「调休上班日（补班日）」的加班费定性——归档中亦无任何文件涉及该口径。",
    },
    {
        "rel": "regulations/2003-12-22-北京市工资支付规定.md",
        "title": "北京市工资支付规定",
        "region": BEIJING,
        "topic": "regulations",
        "url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56550.html",
        "authority": "北京市人民政府",
        "published_at": "2003-12-22",
        "notes": "2003年12月22日北京市人民政府令第142号公布，2004年1月22日施行；"
                 "2007年11月23日市政府令第200号修改（页面末尾附注）。"
                 "本规定第十四条=加班工资150%/200%/300%，第十六条=综合计算工时视为延长工作时间，"
                 "第十七条=不定时工作制不适用第十四条，第四十四条=加班工资基数三级顺序（合同约定→集体合同→正常劳动应得工资）"
                 "且不得低于最低工资。第四十三条「每月以平均工作时间20.92天折算」为旧口径，"
                 "现行应按人社部发〔2025〕2号以月计薪天数21.75天折算。",
    },
]


def main() -> None:
    for doc in DOCS:
        url = doc["url"]
        try:
            html = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            print("  FAIL", url, exc)
            continue
        title, date, md = html_to_md(html, url)
        if not md:
            print("  FAIL(空正文)", url)
            continue
        extra = {}
        if doc.get("status"):
            extra["status"] = doc["status"]
        save_md(
            doc["rel"], doc.get("title") or title or doc["rel"], md,
            topic=doc["topic"], source_url=url,
            published_at=doc.get("published_at") or date,
            authority=doc["authority"], notes=doc["notes"],
            region=doc["region"], extra_meta=extra or None,
        )


if __name__ == "__main__":
    main()