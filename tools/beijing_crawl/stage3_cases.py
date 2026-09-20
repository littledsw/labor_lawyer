"""阶段 3：归档北京市人社局「劳动人事争议典型案例」专题全部文章。"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch_text, html_to_md, save_md, save_binary  # noqa: E402

BASE = "https://rsj.beijing.gov.cn/bm/ztzl/dxal/"
INDEX = BASE + "index.html"
BAD = re.compile(r'[\\/:*?"<>|\s]+')


def collect_links() -> list[tuple[str, str, str]]:
    """返回 [(绝对URL, 标题, 发布日期)]，来自 7 个列表分页。"""
    seen: dict[str, tuple[str, str]] = {}
    for i in ["", "_1", "_2", "_3", "_4", "_5", "_6"]:
        html = fetch_text(f"{BASE}index{i}.html")
        for m in re.finditer(
            r'<li><i></i><a href="\./([^"]+)" target="_blank" title="([^"]*)">.*?<span>([\d-]+)</span>',
            html,
        ):
            rel, title, date = m.groups()
            seen[rel] = (title.strip(), date.strip())
    out = [(BASE + rel.lstrip("./"), t, d) for rel, (t, d) in seen.items()]
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def main() -> None:
    links = collect_links()
    print("cases:", len(links))
    (pathlib.Path(__file__).parent / "case_links.json").write_text(
        json.dumps(links, ensure_ascii=False, indent=1))
    for url, title, date in links:
        try:
            html = fetch_text(url, referer=INDEX)
            t_title, t_date, md = html_to_md(html, url)
            title_use = title or t_title
            date_use = date or t_date
            if len(md) < 200:
                print("  SKIP(short)", url, len(md))
                continue
            fname = f"{date_use or 'undated'}-{BAD.sub('-', title_use)[:70].strip('-')}.md"
            save_md(
                f"cases/{fname}", title_use,
                f"> 来源：北京市人力资源和社会保障局「劳动人事争议典型案例」专题 · {url}\n"
                f"> 发布日期：{date_use}\n\n" + md,
                topic="cases", source_url=url, published_at=date_use,
                notes="北京市人社局专题页原文（HTML 抓取转 Markdown）",
            )
        except Exception as exc:  # noqa: BLE001
            print("  FAIL", url, exc)


if __name__ == "__main__":
    main()
