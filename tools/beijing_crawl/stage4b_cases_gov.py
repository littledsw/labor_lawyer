"""阶段 4b：归档首都之窗发布的年度十大案例动态页及其官方附件。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch, fetch_text, html_to_md, save_binary, save_md  # noqa: E402
from stage4_regs import attachments  # noqa: E402

PAGES = [
    ("https://www.beijing.gov.cn/ywdt/gzdt/202312/t20231229_3521081.html",
     "北京市发布2023年度十大劳动人事争议仲裁典型案例"),
    ("https://www.beijing.gov.cn/ywdt/gzdt/202412/t20241217_3967825.html",
     "北京市发布2024年度十大劳动人事争议仲裁典型案例"),
]


def main() -> None:
    for url, title in PAGES:
        html = fetch_text(url)
        _, date, md = html_to_md(html, url)
        prefix = f"{date or 'undated'}-{title}"
        body = (
            f"> 来源：首都之窗（北京市人民政府门户网站）· {url}\n"
            f"> 发布日期：{date}\n\n"
            f"> 说明：本文件为该年度案例的官方发布动态；每个案例的完整正文见同级目录下"
            f"「{title.replace('北京市发布', '').replace('劳动人事争议仲裁典型案例', '')}」"
            "对应的按年度归档文件。\n\n" + md + "\n"
        )
        save_md(f"cases/{prefix}.md", title, body, topic="cases", source_url=url,
                published_at=date, authority="北京市人力资源和社会保障局（首都之窗发布）",
                notes="年度十大案例发布动态页（含官方附件）")
        for abs_url, name in attachments(html, url):
            data = fetch(abs_url, referer=url)
            save_binary(f"cases/files/{prefix}-{name}", data,
                        title=f"{title} · 原文附件 {name}", topic="cases",
                        source_url=url, download_url=abs_url, published_at=date,
                        original_filename=name,
                        notes="首都之窗页面官方附件（案例汇编/原文）")


if __name__ == "__main__":
    main()
