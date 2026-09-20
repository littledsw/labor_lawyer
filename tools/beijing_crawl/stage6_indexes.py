"""阶段 6：根据 manifest 生成索引、更新来源台账与目录说明。"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import BEIJING, MANIFEST, REPO, RETRIEVED_AT  # noqa: E402

TOPICS = ["templates", "manuals", "guidance", "cases", "jurisdiction", "institutions", "regulations"]
TOPIC_CN = {
    "templates": "模板与文书", "manuals": "系统操作手册", "guidance": "办事指南",
    "cases": "典型案例", "jurisdiction": "管辖规定", "institutions": "仲裁机构名录",
    "regulations": "地方法规与政策文件",
}
CSV_FIELDS = [
    "local_path", "topic", "title", "authority", "published_at", "source_url",
    "download_url", "retrieved_at", "status", "content_hash", "file_type", "bytes",
]
START, END = "<!-- inventory:start -->", "<!-- inventory:end -->"


def load() -> list[dict]:
    records = json.loads(MANIFEST.read_text())
    kept, dropped = [], []
    for r in records:
        (kept if (REPO / r["local_path"]).exists() else dropped).append(r)
    if dropped:
        print(f"prune {len(dropped)} 条已失效记录（文件不存在）")
        for r in dropped[:10]:
            print("   -", r["local_path"])
        MANIFEST.write_text(json.dumps(kept, ensure_ascii=False, indent=1))
    return kept


def write_indexes(records: list[dict]) -> None:
    idx = REPO / "indexes"
    (idx / "by-topic").mkdir(parents=True, exist_ok=True)
    rows = sorted(records, key=lambda r: (r.get("topic", ""), r.get("published_at") or "", r.get("title", "")))
    with (idx / "documents.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_FIELDS})
    (idx / "documents.json").write_text(
        json.dumps([{k: r.get(k) for k in CSV_FIELDS} for r in rows], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    for topic in TOPICS:
        items = [r for r in rows if r.get("topic") == topic]
        lines = [
            f"# {TOPIC_CN[topic]}（{topic}）资料索引", "",
            f"共 {len(items)} 项，抓取时间 {RETRIEVED_AT}。", "",
            "| 标题 | 发布日期 | 类型 | 本地路径 | 来源 |", "| --- | --- | --- | --- | --- |",
        ]
        for r in items:
            lines.append(
                f"| {r.get('title')} | {r.get('published_at') or '—'} | {r.get('file_type')} | "
                f"[{r.get('local_path')}](../{r.get('local_path').replace('regions/municipalities/beijing/', '')}) | "
                f"[来源]({r.get('source_url')}) |"
            )
        (idx / "by-topic" / f"{topic}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("indexes:", len(rows), "records")


def write_sources(records: list[dict]) -> None:
    data = {
        "updated_at": RETRIEVED_AT,
        "region": "municipalities/beijing",
        "authority": "北京市人力资源和社会保障局",
        "sources": [
            {
                "id": "beijing-arbitration-platform",
                "region": "municipalities/beijing",
                "authority": "北京市人力资源和社会保障局",
                "homepage": "https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/index",
                "status": "active",
                "topics": ["templates", "manuals", "guidance"],
                "note": "文书模板 docx 与操作手册 PDF 为公开直链（public/doc/），已归档；"
                        "在线申请须知为服务端渲染页面，已抓取为 Markdown。",
            },
            {
                "id": "beijing-rsj-typical-cases",
                "region": "municipalities/beijing",
                "authority": "北京市人力资源和社会保障局",
                "homepage": "https://rsj.beijing.gov.cn/bm/ztzl/dxal/index_1.html",
                "status": "active",
                "topics": ["cases"],
                "note": "典型案例专题 7 个列表分页全部抓取，共 91 篇。",
            },
            {
                "id": "beijing-arbitration-institutions",
                "region": "municipalities/beijing",
                "authority": "北京市政务服务网 / 北京市人力资源和社会保障局",
                "homepage": "https://banshi.beijing.gov.cn/zwfwapi/cycx/shbz/ldrszytjzcjg/query.html",
                "status": "active",
                "topics": ["institutions"],
                "note": "公开名录查询接口（GET /zwfwapi/bjmap/query?categoryId=ldrszytjzcjg）返回 20 家机构。",
            },
            {
                "id": "beijing-gov-service-guides",
                "region": "municipalities/beijing",
                "authority": "北京市政务服务中心（banshi.beijing.gov.cn）",
                "homepage": "https://banshi.beijing.gov.cn/pubtask/task/1/110000000000/1f742ee9-db1e-46f0-b009-0a71220d2f08.html",
                "status": "active",
                "topics": ["guidance", "templates"],
                "note": "「劳动人事争议仲裁申请」政务服务事项办事指南，已归档 12 个（市级 + 11 区）；"
                        "石景山、门头沟、房山、顺义、大兴及经开区办事指南尚未定位到公开 URL。",
            },
            {
                "id": "beijing-rsj-policy",
                "region": "municipalities/beijing",
                "authority": "北京市人力资源和社会保障局",
                "homepage": "https://rsj.beijing.gov.cn/xxgk/",
                "status": "active",
                "topics": ["regulations", "jurisdiction"],
                "note": "政策文件、通知公告、政策解读栏目中与劳动人事争议仲裁相关的现行文件。",
            },
            {
                "id": "beijing-gov-normative-docs",
                "region": "municipalities/beijing",
                "authority": "北京市人民政府门户网站（首都之窗）",
                "homepage": "https://www.beijing.gov.cn/zhengce/gfxwj/",
                "status": "active",
                "topics": ["jurisdiction"],
                "note": "规范性文件栏目中的仲裁管辖调整通知（含官方 PDF）。",
            },
            {
                "id": "zwfw-beijing-dead-link",
                "region": "municipalities/beijing",
                "homepage": "https://zwfw.beijing.gov.cn/art/2022/2/20/art_3077_341211.html",
                "status": "unreachable",
                "topics": ["jurisdiction"],
                "note": "该域名当前无法解析（DNS 失败），原 README 中「东城区政务服务中心仲裁指南」链接已失效；"
                        "东城区内容改由政务服务事项办事指南页面替代归档。",
            },
        ],
        "documents": [
            {
                "local_path": r.get("local_path"),
                "title": r.get("title"),
                "topic": r.get("topic"),
                "source_url": r.get("source_url"),
                "download_url": r.get("download_url"),
                "published_at": r.get("published_at"),
                "retrieved_at": r.get("retrieved_at"),
                "status": r.get("status"),
                "content_hash": r.get("content_hash"),
            }
            for r in sorted(records, key=lambda r: (r.get("topic", ""), r.get("title", "")))
        ],
    }
    import yaml
    (REPO / "SOURCES.yaml").write_text(
        "# 来源站点索引（由抓取流程生成，保留原始 URL 与 SHA-256 追溯信息）\n"
        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8",
    )
    print("SOURCES.yaml updated")


def write_topic_readmes(records: list[dict]) -> None:
    for topic in TOPICS:
        items = [r for r in records if r.get("topic") == topic]
        readme = BEIJING / topic / "README.md"
        block = [START, f"## 已归档资料（{len(items)} 项，抓取时间 {RETRIEVED_AT}）", ""]
        if items:
            block += ["| 标题 | 发布日期 | 类型 | 文件名 |", "| --- | --- | --- | --- |"]
            for r in sorted(items, key=lambda r: (r.get("published_at") or "", r.get("title", ""))):
                local = r["local_path"].replace(f"regions/municipalities/beijing/{topic}/", "")
                block.append(
                    f"| {r.get('title')} | {r.get('published_at') or '—'} | {r.get('file_type')} | `{local}` |"
                )
        else:
            block.append("（暂无归档文件）")
        block += ["", END]
        new_block = "\n".join(block)
        if readme.exists():
            text = readme.read_text(encoding="utf-8")
            if START in text and END in text:
                pre = text[: text.index(START)]
                post = text[text.index(END) + len(END):]
                readme.write_text(pre.rstrip() + "\n\n" + new_block + post, encoding="utf-8")
            else:
                readme.write_text(text.rstrip() + "\n\n" + new_block + "\n", encoding="utf-8")
        else:
            readme.write_text(f"# {TOPIC_CN[topic]}\n\n" + new_block + "\n", encoding="utf-8")
    print("topic READMEs updated")


def write_changelog(records: list[dict]) -> None:
    counts = {t: len([r for r in records if r.get("topic") == t]) for t in TOPICS}
    changelog = REPO / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8").rstrip()
    heading = f"## {datetime.date.today().isoformat()} · 北京资料首次批量抓取"
    # 幂等：同日同标题的旧条目先移除，避免重复追加
    if heading in text:
        head, _, rest = text.partition(heading)
        nxt = rest.find("\n## ")
        text = (head.rstrip() + ("\n\n" + rest[nxt + 1:] if nxt != -1 else "")).rstrip()
    entry = [
        "",
        f"## {datetime.date.today().isoformat()} · 北京资料首次批量抓取",
        "",
        "抓取并归档北京地区公开仲裁资料，新增内容：",
        "",
        f"- 模板与文书 {counts['templates']} 份（docx 原始文件）",
        f"- 系统操作手册 {counts['manuals']} 份（PDF 原始文件）",
        f"- 办事指南 {counts['guidance']} 份（政务服务事项指南 + 平台在线申请须知）",
        f"- 典型案例 {counts['cases']} 篇（北京市人社局专题页全部文章 + 年度十大案例）",
        f"- 管辖规定 {counts['jurisdiction']} 份（含官方 PDF 附件）",
        f"- 仲裁机构名录 {counts['institutions']} 份（官方查询接口数据 + 整理名录）",
        f"- 地方法规与政策文件 {counts['regulations']} 份",
        f"- 新增 `indexes/documents.csv`、`indexes/documents.json`、`indexes/by-topic/`，"
        f"并为每个二进制附件生成同名 `.meta.yaml` 来源记录（来源页、下载地址、发布时间、抓取时间、SHA-256）",
        "- `SOURCES.yaml` 更新为来源台账（含各来源状态与逐份文件索引）",
        "- 已知失效来源：`zwfw.beijing.gov.cn`（DNS 不可解析），原 README 中东城区指南链接失效",
        "",
    ]
    changelog.write_text(text + "\n" + "\n".join(entry), encoding="utf-8")
    print("CHANGELOG.md updated")


def main() -> None:
    records = load()
    print("manifest records:", len(records))
    write_indexes(records)
    write_sources(records)
    write_topic_readmes(records)
    write_changelog(records)


if __name__ == "__main__":
    main()
