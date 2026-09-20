"""派生数据抽取（方案 C，纯脚本、零 LLM 成本）。

输入：regions/municipalities/beijing/cases/*.md（含年度合集）
输出：indexes/derived/
- cases-meta.json      每篇案例的结构化元数据（章节结构、字数、法条引用、主题标签）
- cases-chunks.jsonl   年度合集中的单个案例切片（供 RAG 检索；一律保留父文件来源）
- cases-citations.md   法条引用频次与对应案例清单
- cases-topics.md      主题标签统计与对应案例清单
- README.md            派生数据说明与再生成方式
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import BEIJING, REPO  # noqa: E402

CASES = BEIJING / "cases"
OUT = REPO / "indexes" / "derived"

SECTIONS = {
    "案情简介": "案情简介", "案情": "案情简介",
    "仲裁请求": "仲裁请求", "申请请求": "仲裁请求",
    "处理结果": "处理结果", "裁决结果": "处理结果", "处理情况": "处理结果",
    "案例评析": "案例评析", "评析": "案例评析", "焦点分析": "案例评析",
    "争议焦点": "争议焦点", "焦点": "争议焦点",
    "法律依据": "法律依据", "法律分析": "案例评析",
}

TOPICS = {
    "经济补偿与违法解除": ["经济补偿", "赔偿金", "违法解除", "被迫解除"],
    "加班费与工时": ["加班费", "加班工资", "延时加班", "休息日加班", "法定节假日", "不定时工作制", "综合计算工时"],
    "带薪年休假": ["年休假", "年假"],
    "工伤与职业病": ["工伤", "停工留薪", "伤残", "劳动能力鉴定"],
    "社会保险": ["社会保险", "社保", "养老保险", "医疗保险", "失业保险", "生育保险"],
    "竞业限制与保密": ["竞业限制", "竞业禁止", "保密", "商业秘密"],
    "劳务派遣与外包": ["劳务派遣", "用工单位", "劳务外包"],
    "二倍工资与合同订立": ["二倍工资", "未订立", "未签订书面劳动合同", "劳动合同订立"],
    "试用期": ["试用期"],
    "医疗期与病假": ["医疗期", "病假"],
    "女职工与生育": ["产假", "生育", "女职工", "哺乳", "孕期"],
    "调岗与工作地点": ["调岗", "工作地点", "岗位调整"],
    "离职手续与证明": ["离职证明", "离职手续", "档案", "工作交接"],
    "劳动关系确认": ["确认劳动关系", "事实劳动关系", "混同用工"],
    "事业单位人事争议": ["事业单位人事争议", "聘用合同", "事业单位工作人员", "文职人员", "事业单位"],
    "工资支付与欠薪": ["拖欠工资", "工资支付", "农民工"],
    "仲裁时效与程序": ["仲裁时效", "受案范围", "管辖", "时效抗辩"],
    "规章制度与违纪": ["规章制度", "劳动纪律", "违纪", "考勤"],
    "养老保险与退休": ["退休", "养老保险", "缴费年限"],
    "新就业形态": ["平台用工", "网约", "外卖", "骑手", "新就业形态"],
}

CITE = re.compile(r"《([^》]{2,60})》(《[^》]{0,60}》)?")
def norm_line(line: str) -> str:
    """去掉 markdown 强调标记与空白，用于结构识别（不改变正文）。"""
    return re.sub(r"[*#\s\u3000]+", "", line)


HEAD_MARK = re.compile(r"^(?:案例)?(\d{1,2}|[一二三四五六七八九十]{1,3})[.、：:．]?(.+)$")
NUM_HEAD = re.compile(r"^案例\s*(\d{1,2})\s*[.、：:．]?\s*(.+)$")


def split_chunks(body: str, title: str) -> list[tuple[str, str]]:
    """把年度合集拆成单个案例：返回 [(小标题, 正文)]。

    以「案例编号标题行」为锚点（如 `案例1.xxx`、`一、xxx`），相同标题只保留最后一次出现，
    以排除正文前的目录列表。
    """
    lines = body.splitlines()
    marks: dict[str, int] = {}
    for i, line in enumerate(lines):
        norm = norm_line(line)
        if not norm or len(norm) > 60 or norm.startswith("20"):
            continue
        m = NUM_HEAD.match(norm) or HEAD_MARK.match(norm)
        if not m:
            continue
        head = re.sub(r"[.、：:]+$", "", m.group(2)).strip()
        if 4 <= len(head) <= 50:
            marks[head] = i  # 相同标题保留最后一次（目录在前、正文在后）
    if len(marks) < 5:
        return []
    ordered = sorted(marks.items(), key=lambda x: x[1])
    chunks = []
    for n, (head, pos) in enumerate(ordered):
        end = ordered[n + 1][1] if n + 1 < len(ordered) else len(lines)
        text = "\n".join(lines[pos:end]).strip()
        if len(text) > 200:
            chunks.append((head, text))
    return chunks


def strip_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 3)
    fm, body = text[4:end + 1], text[end + 4:]
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, body.lstrip("\n")


def citations(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in CITE.finditer(text):
        name = m.group(1).strip()
        if name.endswith("文书") or name.endswith("通知书") or "手册" in name:
            continue  # 排除《员工手册》《解除劳动合同通知书》这类材料名
        out[name] = out.get(name, 0) + 1
    return out


def topics(text: str) -> list[str]:
    return [t for t, kws in TOPICS.items() if any(k in text for k in kws)]


def split_chunks(body: str, title: str) -> list[tuple[str, str]]:
    """把年度合集拆成单个案例：返回 [(小标题, 正文)]。

    以「案例编号标题行」为锚点（如 `案例1.xxx`、`一、xxx`），相同标题只保留最后一次出现，
    以排除正文前的目录列表。
    """
    lines = body.splitlines()
    marks: dict[str, int] = {}
    for i, line in enumerate(lines):
        norm = norm_line(line)
        if not norm or len(norm) > 60 or norm.startswith("20"):
            continue
        m = NUM_HEAD.match(norm) or HEAD_MARK.match(norm)
        if not m:
            continue
        head = re.sub(r"[.、：:]+$", "", m.group(2)).strip()
        if 4 <= len(head) <= 50:
            marks[head] = i  # 相同标题保留最后一次（目录在前、正文在后）
    if len(marks) < 5:
        return []
    ordered = sorted(marks.items(), key=lambda x: x[1])
    chunks = []
    for n, (head, pos) in enumerate(ordered):
        end = ordered[n + 1][1] if n + 1 < len(ordered) else len(lines)
        text = "\n".join(lines[pos:end]).strip()
        if len(text) > 200:
            chunks.append((head, text))
    return chunks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    metas, chunks, cite_cases, topic_cases = [], [], {}, {}
    for path in sorted(CASES.glob("*.md")):
        meta, body = strip_frontmatter(path.read_text(encoding="utf-8"))
        cites = citations(body)
        tags = topics(body)
        found_sections = sorted({v for k, v in SECTIONS.items() if k in body})
        is_collection = len(body) > 5000
        rec = {
            "id": path.stem,
            "title": meta.get("title") or path.stem,
            "published_at": meta.get("published_at"),
            "source_url": meta.get("source_url"),
            "local_path": str(path.relative_to(REPO)),
            "kind": "年度合集" if is_collection else "单篇案例",
            "chars": len(body),
            "sections": found_sections,
            "citations": cites,
            "topics": tags,
        }
        if is_collection:
            rec["chunks"] = len(split_chunks(body, rec["title"]))
        metas.append(rec)
        for law in cites:
            cite_cases.setdefault(law, []).append(rec["id"])
        for t in tags:
            topic_cases.setdefault(t, []).append(rec["id"])
        for n, (head, text) in enumerate(split_chunks(body, rec["title"]), 1):
            chunks.append({
                "chunk_id": f"{path.stem}#{n}",
                "parent": path.stem,
                "parent_title": rec["title"],
                "published_at": rec.get("published_at"),
                "source_url": rec.get("source_url"),
                "local_path": rec["local_path"],
                "case_title": head,
                "text": text,
                "citations": citations(text),
                "topics": topics(text),
            })

    (OUT / "cases-meta.json").write_text(json.dumps(metas, ensure_ascii=False, indent=1), encoding="utf-8")
    with (OUT / "cases-chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    lines = ["# 典型案例法条引用索引（脚本抽取）", "",
             f"来源：`regions/municipalities/beijing/cases/` 共 {len(metas)} 篇；引用统计基于正文中的《…》书名号。", "",
             "| 法条/文件 | 引用次数 | 涉及案例数 |", "| --- | --- | --- |"]
    for law, ids in sorted(cite_cases.items(), key=lambda x: -len(x[1])):
        total = sum(r["citations"].get(law, 0) for r in metas)
        lines.append(f"| 《{law}》 | {total} | {len(ids)} |")
    lines += ["", "## 按法条查看案例", ""]
    for law, ids in sorted(cite_cases.items(), key=lambda x: -len(x[1])):
        if len(ids) < 2:
            continue
        lines.append(f"- **《{law}》**（{len(ids)} 篇）：")
        lines += [f"  - [{i}](../regions/municipalities/beijing/cases/{i}.md)" for i in ids]
    (OUT / "cases-citations.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    tlines = ["# 典型案例主题索引（脚本抽取）", "",
              f"来源：`regions/municipalities/beijing/cases/` 共 {len(metas)} 篇；标签按关键词命中，可能多标签。", "",
              "| 主题 | 案例数 |", "| --- | --- |"]
    for t, ids in sorted(topic_cases.items(), key=lambda x: -len(x[1])):
        tlines.append(f"| {t} | {len(ids)} |")
    tlines += ["", "## 按主题查看案例", ""]
    for t, ids in sorted(topic_cases.items(), key=lambda x: -len(x[1])):
        tlines.append(f"- **{t}**（{len(ids)} 篇）：")
        tlines += [f"  - [{i}](../regions/municipalities/beijing/cases/{i}.md)" for i in ids]
    (OUT / "cases-topics.md").write_text("\n".join(tlines) + "\n", encoding="utf-8")

    (OUT / "README.md").write_text(
        "# 派生数据（indexes/derived）\n\n"
        "由 `tools/crawl/extract_cases.py` 从归档原文脚本化生成，**不含 LLM 输出**，可随时重跑覆盖。\n\n"
        "| 文件 | 内容 |\n| --- | --- |\n"
        "| `cases-meta.json` | 每篇案例的元数据：章节结构、字数、法条引用、主题标签 |\n"
        "| `cases-chunks.jsonl` | 年度合集中的单个案例切片（每行一条，含正文、来源 URL、父文件） |\n"
        "| `cases-citations.md` | 法条引用频次与对应案例清单 |\n"
        "| `cases-topics.md` | 主题标签统计与对应案例清单 |\n\n"
        "再生成：`cd tools/crawl && LABOR_LAWYER_REPO=<repo> python extract_cases.py`\n\n"
        "说明：切片一律保留 `parent` 与 `source_url`，检索命中后可回溯到官方原文；"
        "正式用于 RAG 前建议先跑 `cases-meta.json` 检查章节完整度。\n",
        encoding="utf-8",
    )
    print(f"案例 {len(metas)} 篇；切片 {len(chunks)} 条；法条 {len(cite_cases)} 部；主题 {len(topic_cases)} 类")


if __name__ == "__main__":
    main()
