"""派生数据抽取（方案 C，纯脚本、零 LLM 成本）。

输入：regions/municipalities/beijing/cases/*.md（年度合集 + 单篇案例）
输出：indexes/derived/
- cases-meta.json      每个文件的元数据（kind 分类、章节结构、字数、法条引用、主题标签）
- cases-chunks.jsonl   语义单元切片（供 RAG 检索；一律保留父文件来源）：
                       年度合集按「案例 N」锚点切；单篇案例本身即一个语义单元，切为 1 片

跳过：主题 `README.md`（目录说明，不是案例）、年度案例的「官方发布动态」页
（其正文只是发布消息，案例正文另有归档文件）、抓取只拿到站内搜索框的「空壳页」
（后两类仅进 cases-meta.json，分别标 `kind: 发布动态` / `kind: 空壳页`）
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


# 主题目录说明，不是案例文件
SKIP_FILES = {"README.md"}
# 年度案例的「官方发布动态」页：正文仅为发布消息，案例正文另有归档文件
NOTICE_MARK = "官方发布动态"
# 空壳页：正文由 JS 加载，静态与渲染抓取都只得到站内搜索框（站点自身如此）
STUB_MARKS = ("按相关度排序", "结果排序", "高级搜索")
# 2017 年式合集：锚点形如「**2017年北京市……典型案例之一——**」，其下一行才是案例标题
ORD_HEAD = re.compile(r"之([一二三四五六七八九十]{1,3})[—\-－]+$")


def is_stub(body: str) -> bool:
    """判定抓取到的「空壳页」：只剩站内搜索控件文案，没有案例正文。"""
    return len(body) < 1200 and sum(m in body for m in STUB_MARKS) >= 2


def split_chunks_ordinal(body: str) -> list[tuple[str, str]]:
    """切「之一/之二……」式合集（正文用粗体行分隔，无「案例N」编号）。

    锚点行的下一非空行即案例小标题；正文自锚点行起、至下一锚点前止。
    """
    lines = body.splitlines()
    marks: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        if not ORD_HEAD.search(norm_line(line)):
            continue
        head = ""
        for nxt in lines[i + 1:i + 4]:
            text = norm_line(nxt)
            if text:
                head = text
                break
        marks.append((head or f"案例{len(marks) + 1}", i))
    if len(marks) < 5:
        return []
    out = []
    for n, (head, pos) in enumerate(marks):
        end = marks[n + 1][1] if n + 1 < len(marks) else len(lines)
        text = "\n".join(lines[pos:end]).strip()
        if len(text) > 200:
            out.append((head, text))
    return out


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    metas, chunks, cite_cases, topic_cases = [], [], {}, {}
    for path in sorted(CASES.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        meta, body = strip_frontmatter(path.read_text(encoding="utf-8"))
        title = meta.get("title") or path.stem
        is_notice = NOTICE_MARK in body[:500]
        stub_page = is_stub(body)
        is_collection = len(body) > 5000 and not is_notice and not stub_page
        if is_notice:
            kind = "发布动态"
        elif stub_page:
            kind = "空壳页"
        else:
            kind = "年度合集" if is_collection else "单篇案例"
        cites = citations(body)
        tags = topics(body)
        found_sections = sorted({v for k, v in SECTIONS.items() if k in body})
        rec = {
            "id": path.stem,
            "title": title,
            "published_at": meta.get("published_at"),
            "source_url": meta.get("source_url"),
            "local_path": str(path.relative_to(REPO)),
            "kind": kind,
            "chars": len(body),
            "sections": found_sections,
            "citations": cites,
            "topics": tags,
        }
        # 语义单元：合集按案例锚点切；单篇案例本身即一个语义单元，整体作一片
        if is_collection:
            pieces = split_chunks(body, title) or split_chunks_ordinal(body)
            rec["chunks"] = len(pieces)
        elif kind == "单篇案例":
            pieces = [(title, body)]
        else:
            pieces = []
        metas.append(rec)
        if kind not in ("发布动态", "空壳页"):  # 非案例页不进引用/主题索引
            for law in cites:
                cite_cases.setdefault(law, []).append(rec["id"])
            for t in tags:
                topic_cases.setdefault(t, []).append(rec["id"])
        for n, (head, text) in enumerate(pieces, 1):
            chunks.append({
                "chunk_id": f"{path.stem}#{n}",
                "parent": path.stem,
                "parent_title": title,
                "kind": kind,
                "published_at": meta.get("published_at"),
                "source_url": meta.get("source_url"),
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

    case_metas = [m for m in metas if m["kind"] not in ("发布动态", "空壳页")]
    lines = ["# 典型案例法条引用索引（脚本抽取）", "",
             f"来源：`regions/municipalities/beijing/cases/` 共 {len(case_metas)} 篇"
             f"（年度合集 + 单篇案例；不含主题 `README.md`、「发布动态」页与「空壳页」）；引用统计基于正文中的《…》书名号。", "",
             "| 法条/文件 | 引用次数 | 涉及案例数 |", "| --- | --- | --- |"]
    for law, ids in sorted(cite_cases.items(), key=lambda x: -len(x[1])):
        total = sum(r["citations"].get(law, 0) for r in case_metas)
        lines.append(f"| 《{law}》 | {total} | {len(ids)} |")
    lines += ["", "## 按法条查看案例", ""]
    for law, ids in sorted(cite_cases.items(), key=lambda x: -len(x[1])):
        if len(ids) < 2:
            continue
        lines.append(f"- **《{law}》**（{len(ids)} 篇）：")
        lines += [f"  - [{i}](../regions/municipalities/beijing/cases/{i}.md)" for i in ids]
    (OUT / "cases-citations.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    tlines = ["# 典型案例主题索引（脚本抽取）", "",
              f"来源：`regions/municipalities/beijing/cases/` 共 {len(case_metas)} 篇"
              f"（年度合集 + 单篇案例；不含主题 `README.md`、「发布动态」页与「空壳页」）；标签按关键词命中，可能多标签。", "",
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
        "由 `tools/crawl/extract_cases.py`（脚本化，零 LLM 成本）与 "
        "`tools/crawl/merge_llm_extract.py`（合并模型抽取结果）生成，可随时重跑覆盖。\n\n"
        "## 脚本派生（无 LLM）\n\n"
        "| 文件 | 内容 |\n| --- | --- |\n"
        "| `cases-meta.json` | 逐个文件的元数据：`kind`（年度合集 / 单篇案例 / 发布动态）、章节结构、字数、法条引用、主题标签 |\n"
        "| `cases-chunks.jsonl` | 语义单元切片（每行一条，含正文、来源 URL、父文件）：合集按案例锚点切、单篇案例整篇一片 |\n"
        "| `cases-citations.md` | 法条引用频次与对应案例清单 |\n"
        "| `cases-topics.md` | 主题标签统计与对应案例清单 |\n\n"
        "## 模型抽取（方案 A，供 RAG 检索）\n\n"
        "| 文件 | 内容 |\n| --- | --- |\n"
        "| `llm-extract/<发布日期>.json` | 年度合集批次（`<合集发布日期>.json`）与单篇案例批次（`singles-NN.json`）的原始抽取结果 |\n"
        "| `cases-structured.json` | 合并后的结构化记录：争议焦点、仲裁请求、处理结果、裁决要旨、法条依据、金额口径、关键词、主体类型 |\n"
        "| `cases-structured.md` | 上述记录的人工可读版本 |\n\n"
        "`legal_basis_check` 字段记录每条法条引用的回文核验等级：`exact` 与原文逐字一致、"
        "`short-form` 系简称写法、`anaphoric` 为原文承接上文的写法、`manual-confirmed` 为人工比对确认。\n\n"
        "`merge_llm_extract.py` 要求 `cases-chunks.jsonl` 的**每一条切片都被抽取覆盖**，缺一条即报错退出。\n\n"
        "## 再生成\n\n"
        "```bash\ncd tools/crawl\n"
        "LABOR_LAWYER_REPO=<repo> python extract_cases.py        # 脚本派生\n"
        "LABOR_LAWYER_REPO=<repo> python merge_llm_extract.py    # 合并 + 校验模型抽取\n```\n\n"
        "## 使用注意\n\n"
        "- 切片一律保留 `parent` 与 `source_url`，检索命中后可回溯到官方原文。\n"
        "- 模型抽取的争议焦点/要旨属归纳性内容；法条依据保留原文写法并经回文核验，"
        "但正式用于出具意见或文书前仍需对照官方原文复核。\n",
        encoding="utf-8",
    )
    by_kind: dict[str, int] = {}
    for m in metas:
        by_kind[m["kind"]] = by_kind.get(m["kind"], 0) + 1
    print(f"文件 {len(metas)} 个（{'、'.join(f'{k} {v}' for k, v in sorted(by_kind.items()))}）；"
          f"切片 {len(chunks)} 条；法条 {len(cite_cases)} 部；主题 {len(topic_cases)} 类")


if __name__ == "__main__":
    main()
