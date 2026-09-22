"""条号回核：把 legal-assistant（规则/口径文档）里的法条引用，逐条对到 labor_lawyer 的 flk 归档正文上。

用法：
    LABOR_LAWYER_REPO=... python tools/verify_citations.py --target ~/workspace/projects/legal-assistant
    ... --report ~/workspace/projects/legal-assistant/docs/citation-check.md

判定：
- OK        ：引用的法规已归档，且该条号在正文里存在
- 条号不存在 ：法规已归档，但正文里找不到该条号（需人工核对，可能引用错条号或用了旧版条号）
- 未归档    ：引用的法规不在本期归档范围（非 flk 收录，或不在劳动仲裁范围）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent / "crawl"))
from common import REPO, split_frontmatter  # noqa: E402

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn2int(s: str) -> int | None:
    """中文数字/阿拉伯数字 → int（支持「一百零七」「四十七」「44」）。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s:
        return None
    total, section, number = 0, 0, 0
    for ch in s:
        if ch in CN_DIGITS:
            number = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
        else:
            return None
    total += section + number
    return total or None


def norm_name(s: str) -> str:
    """法规名归一化：去空白与书名号、去「中华人民共和国」、去括号注释。"""
    s = re.sub(r"[\s\u3000]", "", s or "")
    s = s.replace("〈", "《").replace("〉", "》")
    s = s.replace("《", "").replace("》", "")
    s = s.split("（")[0].split("(")[0]
    return s.replace("中华人民共和国", "")


ART_RE = re.compile(r"^[\s\u3000*]*第([一二三四五六七八九十百零〇]+)条", re.M)
ITEM_RE = re.compile(r"^[\s\u3000*]*([一二三四五六七八九十]+)、", re.M)


def law_index() -> tuple[dict[str, dict], dict[str, dict]]:
    """返回 (条号体索引, 通知体序号索引)，键为归一化名称。"""
    index: dict[str, dict] = {}
    loose: dict[str, dict] = {}
    for path in sorted((REPO / "regions").rglob("*.md")):
        rel = str(path.relative_to(REPO))
        if "/regulations/" not in rel or rel.endswith("README.md"):
            continue
        try:
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        title = (meta.get("title") or "").strip()
        if not title:
            continue
        arts = {cn2int(m) for m in ART_RE.findall(body)}
        arts.discard(None)
        items = {cn2int(m) for m in ITEM_RE.findall(body)}
        items.discard(None)
        entry = {"path": rel, "articles": arts, "items": items, "title": title, "count": len(arts)}
        index.setdefault(norm_name(title), entry)
        if not arts and items:                       # 通知体：用「一、二、三」编号
            loose.setdefault(norm_name(title), entry)
    return index, loose


def find_entry(index: dict, cited: str) -> dict | None:
    key = norm_name(cited)
    if not key:
        return None
    if key in index:
        return index[key]
    cands = [k for k in index if k.endswith(key) or key.endswith(k)]
    if cands:
        cands.sort(key=len, reverse=True)
        return index[cands[0]]
    return None


CITE_RE = re.compile(r"《([^》]{2,45})》\s*第\s*([一二三四五六七八九十百零〇0-9]{1,6})\s*条")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=str(pathlib.Path(REPO).parent / "legal-assistant"),
                    help="被检查的仓库（默认 sibling legal-assistant）")
    ap.add_argument("--report", default="", help="把报告写到指定 md 文件")
    args = ap.parse_args()

    target = pathlib.Path(args.target).expanduser()
    if not target.exists():
        raise SystemExit(f"目标仓库不存在：{target}")

    index, loose = law_index()
    print(f"归档法规索引：{len(index)} 份（条号体 {len(index) - len(loose)}、通知体序号 {len(loose)}）")

    rows = []
    skip = pathlib.Path(args.report).expanduser().resolve() if args.report else None
    files = [p for p in target.rglob("*") if p.suffix in (".md", ".yaml", ".yml", ".json", ".py")
             and "/.git/" not in str(p) and "/.venv/" not in str(p)
             and (skip is None or p.resolve() != skip)]
    for path in sorted(files):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in CITE_RE.finditer(text):
            law, num_raw = m.group(1), m.group(2)
            num = cn2int(num_raw)
            entry = find_entry(index, law)
            loose_entry = find_entry(loose, law) if entry is None else None
            line = text[: m.start()].count("\n") + 1
            if entry is None and loose_entry is None:
                status, archive = "未归档", ""
            elif entry is None:
                archive = loose_entry["path"]
                status = "OK（通知体序号）" if (num and num in loose_entry["items"]) else "序号不存在"
            else:
                archive = entry["path"]
                if num is None:
                    status = "条号无法解析"
                elif num in entry["articles"]:
                    status = "OK"
                elif entry["items"] and num in entry["items"]:
                    status = "OK（通知体序号）"
                else:
                    status = "条号不存在"
            rows.append({"file": str(path.relative_to(target)), "line": line, "law": law,
                         "num": num, "status": status, "archive": archive})

    stats = Counter(r["status"] for r in rows)
    by_law = Counter(r["law"] for r in rows)
    print(f"\n共发现引用 {len(rows)} 处，涉及法规 {len(by_law)} 部")
    print("判定：", dict(stats))
    bad = [r for r in rows if not r["status"].startswith("OK")]
    if bad:
        print("\n需人工核对：")
        for r in bad[:40]:
            print(f"  [{r['status']}] {r['file']}:{r['line']} 《{r['law']}》第{r['num']}条"
                  + (f" → {r['archive']}" if r["archive"] else ""))
        if len(bad) > 40:
            print(f"  …… 其余 {len(bad) - 40} 处")
    ok_laws = sorted({r["law"] for r in rows if r["status"].startswith("OK")})
    print(f"\n已核对通过的法规（{len(ok_laws)}）：" + "、".join(ok_laws[:20]) + ("…" if len(ok_laws) > 20 else ""))

    if args.report:
        out = pathlib.Path(args.report).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# 法条引用回核报告", "",
                 f"- 被检查仓库：`{target}`",
                 f"- 归档信源：国家法律法规数据库（`labor_lawyer/regions/**/regulations/`）",
                 f"- 检出引用：{len(rows)} 处，涉及法规 {len(by_law)} 部",
                 f"- 判定：{dict(stats)}", "",
                 "## 需人工核对", "", "| 状态 | 位置 | 引用 | 归档文件 |", "| --- | --- | --- | --- |"]
        if bad:
            for r in bad:
                lines.append(f"| {r['status']} | `{r['file']}:{r['line']}` | 《{r['law']}》第{r['num']}条 | `{r['archive']}` |")
        else:
            lines.append("| — | — | 无 | — |")
        lines += ["", "## 全部引用", "", "| 状态 | 位置 | 法规 | 条号 |", "| --- | --- | --- | --- |"]
        for r in rows:
            lines.append(f"| {r['status']} | `{r['file']}:{r['line']}` | {r['law']} | {r['num']} |")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n报告已写入 {out}")

    return 1 if any(r["status"] == "条号不存在" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
