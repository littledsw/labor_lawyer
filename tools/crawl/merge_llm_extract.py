"""合并并校验子代理产出的结构化抽取结果（方案 A）。

输入：indexes/derived/cases-chunks.jsonl + indexes/derived/llm-extract/*.json
输出：
- indexes/derived/cases-structured.json  合并后的 RAG 结构化记录
- indexes/derived/cases-structured.md    人工可读摘要
- 控制台打印校验结果（覆盖率、字段齐备性、法条引用回文核验、空字段统计）
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import REPO  # noqa: E402

DER = REPO / "indexes" / "derived"
CHUNKS = DER / "cases-chunks.jsonl"
LLM = DER / "llm-extract"
FIELDS = ["chunk_id", "case_title", "dispute_focus", "claims", "outcome", "holding",
          "legal_basis", "amounts", "keywords", "party_type"]

# 逐字核验脚本无法自动判定、但已人工比对原文确认存在的引用（原文含引号内嵌或承接上文写法）
MANUAL_OK = {
    ("2021-11-05-2021年北京市劳动人事争议仲裁十大典型案例#8",
     "《中华人民共和国民法典》第一千零三十八条第二款"),
    ("2023-12-29-2023年北京市劳动人事争议仲裁典型案例#2",
     "人力资源社会保障部等八部门《关于维护新就业形态劳动者劳动保障权益的指导意见》（人社部发〔2021〕56号）第一条第一项"),
}


def norm(s: str) -> str:
    return re.sub(r"[\s《》〈〉（）()【】\[\]，,。；;：:、·・\-—_]+", "", s)


def main() -> int:
    chunks = {json.loads(l)["chunk_id"]: json.loads(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines() if l.strip()}
    problems: list[str] = []
    items: list[dict] = []
    for path in sorted(LLM.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        batch = data.get("items", [])
        for it in batch:
            cid = it.get("chunk_id")
            if cid not in chunks:
                problems.append(f"未知 chunk_id: {cid}（{path.name}）")
                continue
            missing = [f for f in FIELDS if f not in it]
            if missing:
                problems.append(f"{cid} 缺字段 {missing}")
            if len(it.get("keywords") or []) > 5:
                problems.append(f"{cid} keywords 超过 5 个")
            src = chunks[cid]
            merged = {
                "chunk_id": cid,
                "parent": src["parent"],
                "parent_title": src["parent_title"],
                "published_at": src.get("published_at"),
                "source_url": src.get("source_url"),
                "local_path": src.get("local_path"),
                "case_title": it.get("case_title") or src.get("case_title"),
                "source_case_id": it.get("case_id"),
                "dispute_focus": it.get("dispute_focus") or [],
                "claims": it.get("claims") or [],
                "outcome": it.get("outcome") or "",
                "holding": it.get("holding") or "",
                "legal_basis": it.get("legal_basis") or [],
                "amounts": it.get("amounts") or [],
                "keywords": it.get("keywords") or [],
                "party_type": it.get("party_type") or "",
                "text_chars": len(src["text"]),
            }
            # 法条引用回文核验：原文可能使用简称/承接上文，故按三级放宽核验并标注等级
            body = norm(src["text"])
            verified: list[str] = []
            for cite in merged["legal_basis"]:
                c = norm(cite)
                if not c:
                    continue
                if c in body:
                    verified.append("exact")
                    continue
                short = c.replace("中华人民共和国", "")
                if short in body:
                    verified.append("short-form")
                    continue
                tail = re.search(r"(第[一二三四五六七八九十百零\d]+条.*)$", short)
                head = short.split("第")[0]
                if tail and norm(tail.group(1)) in body and head in body:
                    verified.append("anaphoric")
                    continue
                verified.append("unverified")
            for idx, cite in enumerate(merged["legal_basis"]):
                if verified[idx] == "unverified" and (cid, cite) in MANUAL_OK:
                    verified[idx] = "manual-confirmed"
            if "unverified" in verified:
                for cite, level in zip(merged["legal_basis"], verified):
                    if level == "unverified":
                        problems.append(f"{cid} 法条未能在原文匹配: {cite}")
            merged["legal_basis_check"] = verified
            items.append(merged)

    covered = {i["chunk_id"] for i in items}
    for cid in chunks:
        if cid not in covered:
            problems.append(f"切片未覆盖: {cid}")

    (DER / "cases-structured.json").write_text(
        json.dumps({"generated_from": "indexes/derived/cases-chunks.jsonl",
                    "extractor": "LLM 批处理（子代理并行，2026-09-20）",
                    "note": "争议焦点/要旨/处理结果为模型抽取，法条依据保留原文写法；正式使用前请对照 local_path 原文复核。",
                    "count": len(items), "items": items},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    md = ["# 典型案例结构化抽取（方案 A，模型抽取）", "",
          f"来源：`indexes/derived/cases-chunks.jsonl` 共 {len(chunks)} 条切片，抽取 {len(items)} 条。", "",
          "> 争议焦点、处理结果、裁决要旨为模型归纳；法条依据保留原文写法；金额与计算口径仅在有原文依据时保留。",
          "> 正式引用前请对照每条记录 `source_url` / `local_path` 的官方原文复核。", ""]
    for it in items:
        md += [f"## {it['case_title']}", "",
               f"- 年度：{it['parent_title']}（{it['published_at']}）",
               f"- 来源：{it['source_url']}",
               f"- 主体类型：{it['party_type'] or '—'}",
               f"- 争议焦点：{'；'.join(it['dispute_focus']) or '—'}",
               f"- 仲裁请求：{'；'.join(it['claims']) or '—'}",
               f"- 处理结果：{it['outcome'] or '—'}",
               f"- 裁决要旨：{it['holding'] or '—'}",
               f"- 法条依据：{'；'.join(it['legal_basis']) or '—'}",
               f"- 金额与口径：{'；'.join(it['amounts']) or '—'}",
               f"- 关键词：{'、'.join(it['keywords']) or '—'}", ""]
    (DER / "cases-structured.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    empty = {f: sum(1 for i in items if not i[f]) for f in
             ["dispute_focus", "claims", "outcome", "holding", "legal_basis", "amounts", "party_type"]}
    print(f"切片 {len(chunks)} 条 / 抽取 {len(items)} 条 / 覆盖 {len(covered)} 条")
    print("空字段统计:", empty)
    print("法条引用总数:", sum(len(i['legal_basis']) for i in items))
    if problems:
        print(f"\n问题 {len(problems)} 项（前 25）：")
        for p in problems[:25]:
            print("  -", p)
        return 1
    print("\n校验通过：字段齐备、切片全覆盖、法条引用均可在原文匹配")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
