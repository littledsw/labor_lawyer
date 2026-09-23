"""阶段 21：标注「空壳页」案例页——正文由站点 JS 动态加载，抓取只拿到站内搜索控件。

背景：`regions/municipalities/beijing/cases/` 下有 4 个 2024 年度案例专题页，
纯 HTTP 抓取与 headless Chrome 渲染抓取（`browser_fetch.py`）都只得到约 228 字符的
站内搜索控件文案，页面自身不含案例正文。同案完整正文已在
`2024-12-17-2024年北京市劳动人事争议仲裁十大典型案例.md`（2024 年度十大案例合集）归档。

本阶段做两件事（幂等，可重跑）：

1. 在正文顶部插入「正文缺失」提示块，避免下游把搜索控件文案当案例内容；
2. 重写 frontmatter 的 `notes`（写明复核方式、日期与替代来源），并把记录写回 manifest，
   随后由 `stage6_indexes.py` 刷新 `indexes/` 与 CHANGELOG。

用法：
    LABOR_LAWYER_REPO=<repo> python stage21_flag_empty_cases.py [--render-check]

`--render-check` 会额外用 headless Chrome 重新渲染每个页面，把渲染后的正文字符数写进提示块
（需要联网；不加则沿用已记录的复核结论）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import (  # noqa: E402
    AUTHORITY, LEVEL, REGION, REPO, save_md, split_frontmatter,
)

META = REPO / "indexes" / "derived" / "cases-meta.json"
REGION_ROOT = REPO / "regions" / REGION
MARK = "正文缺失"
# 官方替代来源：同域名（rsj.beijing.gov.cn）2024-12-17 发布的年度十大案例合集页，
# 含这 4 个单篇专题页对应案例的完整正文（案情简介 / 仲裁请求 / 处理结果 / 案例评析 / 仲裁委员会提示）。
ALT_URL = "https://rsj.beijing.gov.cn/bm/ztzl/dxal/202412/t20241217_3968004.html"
BANNER = """> ⚠️ **正文缺失（已复核）**：本页正文由站点 JS 动态加载，纯 HTTP 抓取与 headless Chrome 渲染抓取
> （`tools/crawl/browser_fetch.py`）都只得到约 {chars} 字符的站内搜索控件文案，页面自身不含案例正文。
> 同案完整正文见同目录 `2024-12-17-2024年北京市劳动人事争议仲裁十大典型案例.md`
> （2024 年度十大案例合集，含完整评析），**该合集的来源页即官方替代来源**：
> {alt}
> **补齐正文前请勿引用本文件作为依据。**
"""
NOTES = ("北京市人社局专题页；正文由站点 JS 动态加载，静态抓取与 headless 渲染抓取"
         "（browser_fetch.py）均只得到站内搜索控件、页面无可取正文。"
         "官方替代来源（同域名、同一机构，含同案完整正文）："
         f"{ALT_URL}，已归档为同目录《2024年北京市劳动人事争议仲裁十大典型案例》合集。")


def empty_case_pages() -> list[dict]:
    if not META.exists():
        raise SystemExit(f"缺少 {META.relative_to(REPO)}；先跑 extract_cases.py")
    return [r for r in json.loads(META.read_text(encoding="utf-8")) if r.get("kind") == "空壳页"]


BANNER_END = "**补齐正文前请勿引用本文件作为依据。**"


def strip_banners(body: str) -> str:
    """剥离已写入的提示块，使提示文案升级后仍能幂等重写（不留重复块）。

    提示块以 `> ` 引用行开头，正文（站点控件文案）不以 `>` 开头，故可据此循环剥离。
    """
    while body.lstrip().startswith(">") and BANNER_END in body[:1200]:
        body = body[body.find(BANNER_END) + len(BANNER_END):].lstrip("\n")
    return body


def render_chars(url: str) -> int | None:
    """用 headless Chrome 渲染页面，返回渲染后正文（body.innerText）字符数。"""
    try:
        from browser_fetch import render
        page = render(url, wait=8)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 渲染失败：{exc}")
        return None
    return len((page.get("text") or "").strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-check", action="store_true",
                    help="用 headless Chrome 重新渲染页面并在提示块中记录正文字符数")
    args = ap.parse_args()

    targets = empty_case_pages()
    if not targets:
        print("没有「空壳页」记录，无需处理")
        return 0

    for rec in targets:
        path = REPO / rec["local_path"]
        rel = path.relative_to(REGION_ROOT)
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        if body.count(MARK) == 1 and ALT_URL in body[:900]:
            print(f"  跳过（已标注且替代来源已写入）：{rel}")
            continue
        chars = render_chars(rec["source_url"]) if args.render_check else 228
        if args.render_check and not chars:
            print(f"  ! {rel} 渲染失败，本次跳过（不写入未核实的结论）")
            continue
        save_md(str(rel), meta.get("title") or path.stem,
                BANNER.format(chars=chars, alt=ALT_URL) + "\n" + strip_banners(body),
                topic="cases", source_url=rec["source_url"], published_at=rec.get("published_at"),
                notes=NOTES, authority=meta.get("authority") or AUTHORITY,
                region=REGION, level=LEVEL)
        print(f"  已标注正文缺失：{rel}（渲染正文 {chars} 字符）")

    print(f"\n处理完成：{len(targets)} 个空壳页已登记；接续执行 stage6_indexes.py 刷新索引")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
