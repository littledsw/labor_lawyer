"""flk 归档审计：按 flk_state.json 汇总本期成果，检查 frontmatter 完整性与条号覆盖。

用法：
    python flk_audit.py            # 汇总 + 逐件检查
    python flk_audit.py --list     # 额外逐件列出
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import CRAWL, REPO, split_frontmatter  # noqa: E402

STATE = pathlib.Path(CRAWL) / "flk_state.json"
REQUIRED = ["title", "region", "level", "topic", "authority", "published_at",
            "source_url", "retrieved_at", "status", "effect_status", "content_hash",
            "flk_category", "flk_bbbs", "body_structure"]

# 这些体裁本身不用「第N条」体例（批复/决议/复函/暂行规定等），条号少不算问题
NO_ARTICLE_HINT = ["批复", "决议", "复函", "答复", "暂行规定", "补充规定", "实施办法", "通知",
                   "决定", "意见", "执行意见"]
# 无条号体裁的正文兜底：正文有实质内容（≥500 字）就不算抽取失败
MIN_CHARS_NO_ARTICLE = 500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="逐件列出")
    args = ap.parse_args()

    state = json.loads(STATE.read_text(encoding="utf-8"))
    ok = {k: v for k, v in state.items() if v.get("status") == "ok"}
    bad = {k: v for k, v in state.items() if v.get("status") != "ok"}

    by_cat: Counter = Counter()
    by_effect: Counter = Counter()
    problems: list[str] = []
    rows = []
    for bbbs, v in sorted(ok.items(), key=lambda kv: kv[1].get("local_path") or ""):
        rel = v.get("local_path")
        if not rel:
            problems.append(f"{v.get('title')}: state 缺少 local_path")
            continue
        path = REPO / rel
        if not path.exists():
            problems.append(f"文件缺失: {rel}")
            continue
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        for key in REQUIRED:
            if not meta.get(key):
                problems.append(f"{rel}: frontmatter 缺 {key}")
        tiao = len(re.findall(r"第[一二三四五六七八九十百零〇]+条", body))
        by_cat[meta.get("flk_category")] += 1
        by_effect[meta.get("effect_status")] += 1
        originals = [REPO / p for p in (v.get("originals") or [])]
        missing_orig = [p.name for p in originals if not p.exists()]
        if missing_orig:
            problems.append(f"{rel}: 原件缺失 {missing_orig}")
        title = meta.get("title") or ""
        no_article_genre = any(h in title for h in NO_ARTICLE_HINT)
        body_chars = len(re.sub(r"\s", "", body))
        if tiao < 3 and not no_article_genre and body_chars < MIN_CHARS_NO_ARTICLE:
            problems.append(f"{rel}: 条号疑似缺失（仅 {tiao} 处、正文 {body_chars} 字）")
        if not originals:
            problems.append(f"{rel}: 无归档原件")
        rows.append((meta.get("flk_category"), meta.get("effect_status"), tiao,
                     len(originals), meta.get("title"), len(body)))

    print(f"已归档 {len(ok)} 件；未完成 {len(bad)} 件")
    print("按 flk 分类:", dict(by_cat))
    print("按效力状态:", dict(by_effect))
    print("正文字符数合计:", sum(r[5] for r in rows))
    print("原件份数合计:", sum(r[3] for r in rows), "（其中 docx",
          sum(1 for _ in original_types(state, "docx")), "、pdf",
          sum(1 for _ in original_types(state, "pdf")), "）")
    if args.list:
        print("\n分类 | 效力 | 条号数 | 原件 | 标题 | 正文字符")
        for r in rows:
            print(f"  {r[0]} | {r[1]} | {r[2]:4d} | {r[3]} | {r[4]} | {r[5]}")
    if bad:
        print("\n未完成（需重跑）:")
        for bbbs, v in bad.items():
            print(f"  - [{v.get('status')}] {v.get('title')} ({bbbs})")
    if problems:
        print(f"\n问题 {len(problems)} 条:")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print("\n审计通过：frontmatter 完整、原件在库、条号齐备")
    return 0


def original_types(state: dict, ext: str):
    for v in state.values():
        for p in v.get("originals") or []:
            if p.endswith("." + ext):
                yield p


if __name__ == "__main__":
    raise SystemExit(main())
