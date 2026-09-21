"""阶段 18：社会保险（失业保险、生育保险）赔偿口径的三份依据补档。

补档动机：算「未依法缴纳社会保险不能补缴造成的损失赔偿」时，事实层缺三份关键原文——
- 《北京市失业保险规定》：第 31 条是失业保险待遇损失的**赔偿责任依据**，
  第 17 条是**计发月数表**（1—2 年 3 个月、2—3 年 6 个月、3—4 年 9 个月、4—5 年 12 个月、
  5 年以上每满 1 年增发 1 个月，最长 24 个月），第 23 条是领取期间的医疗补助金比例；
- 京人社评发〔2024〕17号《北京市失业保险金申领发放实施办法（试行）》：
  第 21 条把「用人单位导致失业人员无法领取失业保险金」的待遇损失明确落在用人单位，
  第 19 条给出「领金期间补缴社保费须先退回失业保险金」的处理顺序；
- 京人社医发〔2011〕334号：生育津贴的北京计发公式（用人单位月缴费平均工资 ÷ 30 × 产假天数），
  以及「津贴低于本人产假工资标准的，差额由用人单位补足」。

（失业保险金分档标准由 stage10 归档为参数来源页并写入 parameters.yaml 的
 beijing_unemployment_benefit_standard 序列。）
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch_text, html_to_md, save_md  # noqa: E402

BEIJING = "municipalities/beijing"

DOCS = [
    {
        "rel": "regulations/2007-06-14-北京市失业保险规定.md",
        "title": "北京市失业保险规定（1999年市政府令第38号发布，2007年市政府令第190号修改后重新公布）",
        "url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56688.html",
        "authority": "北京市人民政府",
        "published_at": "2007-06-14",
        "notes": "现行有效。第13条领取条件；第17条计发月数（1—2年3个月、2—3年6个月、"
                 "3—4年9个月、4—5年12个月，5年以上每满1年增发1个月，最长24个月）；"
                 "第19条标准确定原则；第22条农民合同制工人一次性生活补助；"
                 "第23条领取期间医疗补助金比例（60%—80%）；"
                 "**第31条：用人单位不按规定缴纳失业保险费或不按规定及时为失业人员转移档案关系，"
                 "致使失业人员不能享受失业保险待遇或影响其再就业的，用人单位应当赔偿损失。**",
    },
    {
        "rel": "regulations/2024-12-27-北京市失业保险金申领发放实施办法（试行）.md",
        "title": "北京市失业保险金申领发放实施办法（试行）",
        "url": "https://rsj.beijing.gov.cn/xxgk/2024zcwj/202412/t20241227_3974931.html",
        "authority": "北京市人力资源和社会保障局",
        "published_at": "2024-12-27",
        "notes": "京人社评发〔2024〕17号；2024年12月23日印发，自2025年1月1日起施行。"
                 "**第21条：用人单位不按规定缴纳失业保险费或不如实申报失业保险减员原因等，"
                 "导致失业人员无法领取失业保险金的，由用人单位承担失业人员失业保险待遇损失。**"
                 "第5条列明「非因本人意愿中断就业」的情形（含劳动者依《劳动合同法》第三十八条解除）；"
                 "第19条：领金期间单位为失业人员补缴社会保险费的，须先退回失业保险金及待遇。",
    },
    {
        "rel": "regulations/2011-12-12-关于调整本市职工生育保险政策有关问题的通知.md",
        "title": "关于调整本市职工生育保险政策有关问题的通知",
        "url": "https://www.beijing.gov.cn/zhengce/zhengcefagui/201905/t20190522_56936.html",
        "authority": "北京市人力资源和社会保障局",
        "published_at": "2011-12-12",
        "notes": "京人社医发〔2011〕334号。第三条给出北京生育津贴计发口径："
                 "生育津贴＝职工所在用人单位月缴费平均工资 ÷ 30 × 产假天数；"
                 "生育津贴即为产假工资，高于本人产假工资标准的单位不得克扣，"
                 "低于本人产假工资标准的差额部分由用人单位补足。"
                 "参保依据为《北京市企业职工生育保险规定》（2005年市政府令第154号，尚未归档）。",
    },
    {
        "rel": "guidance/2024-08-07-失业保险金热点问答.md",
        "title": "失业保险金热点问答（北京市人民政府）",
        "url": "https://www.beijing.gov.cn/fuwu/bmfw/bmzt/syzqh/syqj/sybxj/202408/t20240807_3768506.html",
        "authority": "北京市人民政府（首都之窗）",
        "published_at": "2024-08-07",
        "topic": "guidance",
        "notes": "口径类问答页：① 失业保险金分档标准（与市人社局调整通告一致，页面为 2024-08 时的标准）；"
                 "② 领取期限表述——「累计缴费时间满 1 年不足 5 年的，每满一年可领取 3 个月；"
                 "累计缴费时间 5 年以上的，缴费每满一年增发一个月，领取期限最长不超过 24 个月」，"
                 "仍未给出增发的起算算例（见参数表 decisions.unemployment_benefit_months_over_5y）；"
                 "③ 领取条件与「非因本人意愿中断就业」六种情形（引《实施〈社会保险法〉若干规定》第十三条，"
                 "含劳动者依《劳动合同法》第三十八条解除）。",
    },
]


def main() -> None:
    for doc in DOCS:
        html = fetch_text(doc["url"])
        title, date, md = html_to_md(html, doc["url"])
        if not md:
            raise SystemExit(f"[stage18] 正文为空，疑似抓取被拦：{doc['url']}")
        print(f"[stage18] {doc['rel']}  页面标题={title}  页面日期={date}  正文 {len(md)} 字符")
        save_md(
            doc["rel"], doc["title"],
            f"> 来源：{doc['url']}\n> 发布机关：{doc['authority']}\n> 原件标题：{title}\n\n{md}\n",
            topic=doc.get("topic", "regulations"), source_url=doc["url"],
            published_at=doc["published_at"], authority=doc["authority"],
            region=BEIJING, notes=doc["notes"],
        )


if __name__ == "__main__":
    main()
