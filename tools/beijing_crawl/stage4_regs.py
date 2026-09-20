"""阶段 4：归档北京仲裁管辖规定与地方规范性/政策文件（正文 + 官方附件）。"""
from __future__ import annotations

import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import AUTHORITY, BEIJING, fetch, fetch_text, html_to_md, save_binary, save_md  # noqa: E402

ATT_RE = re.compile(r'(?:href|src)="([^"]+\.(?:docx?|pdf|xlsx?|zip|rar))"', re.I)


def attachments(html: str, page_url: str) -> list[tuple[str, str]]:
    """页面里的官方附件：[(绝对URL, 原始文件名)]，忽略站点图标类图片文件。"""
    out: list[tuple[str, str]] = []
    for href in ATT_RE.findall(html):
        if any(x in href for x in ("images/", "favicon")):
            continue
        abs_url = urllib.parse.urljoin(page_url, href)
        name = urllib.parse.unquote(pathlib.PurePosixPath(urllib.parse.urlparse(abs_url).path).name)
        out.append((abs_url, name))
    return out


def archive(url: str, topic: str, *, title: str | None = None, published_at: str | None = None,
            notes: str = "", filename_prefix: str | None = None, authority: str = AUTHORITY,
            with_attachments: bool = True, header: str = "") -> None:
    html = fetch_text(url)
    t_title, t_date, md = html_to_md(html, url)
    title = title or t_title
    date = published_at or t_date
    prefix = filename_prefix or f"{date or 'undated'}-{title}"
    doc = f"> 来源：{url}\n> 发布日期：{date}\n\n{header}{md}\n"
    save_md(f"{topic}/{prefix}.md", title, doc, topic=topic, source_url=url,
            published_at=date, authority=authority, notes=notes)
    if not with_attachments:
        return
    for abs_url, name in attachments(html, url):
        try:
            data = fetch(abs_url, referer=url)
        except Exception as exc:  # noqa: BLE001
            print("  ATT FAIL", abs_url, exc)
            continue
        safe = re.sub(r"[/\\]+", "-", name)
        save_binary(
            f"{topic}/files/{prefix}-{safe}", data, title=f"{title} · 附件 {safe}",
            topic=topic, source_url=url, download_url=abs_url, published_at=date,
            authority=authority, original_filename=name,
            notes=f"官方页面附件（原始文件名 {name}）",
        )


def main() -> None:
    # ---- 管辖规定 --------------------------------------------------------
    archive(
        "https://www.beijing.gov.cn/zhengce/gfxwj/202207/t20220714_2771636.html",
        "jurisdiction", title="北京市人力资源和社会保障局关于调整我市劳动人事争议仲裁案件管辖的通知",
        published_at="2022-04-01",
        notes="京人社仲发〔2022〕5号；首都之窗规范性文件栏目发布（页面发布日 2022-07-14）。"
              "同一文件另见北京市人社局政策文件栏目 "
              "https://rsj.beijing.gov.cn/xxgk/2024zcwj/202406/t20240617_3717217.html（内容一致，未重复归档）",
    )

    # ---- 规范性文件 / 政策文件 -------------------------------------------
    archive(
        "https://rsj.beijing.gov.cn/xxgk/tzgg/202404/t20240430_3648905.html",
        "regulations",
        notes="京高法发〔2024〕534号，裁审统一口径（含解答（一）全文）",
    )
    archive(
        "https://rsj.beijing.gov.cn/xxgk/2024zcjd/202406/t20240617_3717660.html",
        "regulations", notes="政策解读：解读《北京市高级人民法院、北京市劳动人事争议仲裁委员会关于审理劳动争议案件适用法律问题的解答》",
    )
    archive(
        "https://rsj.beijing.gov.cn/xxgk/2024zcwj/202501/t20250122_3996364.html",
        "regulations", notes="京人社仲发〔2025〕1号",
    )
    archive(
        "https://rsj.beijing.gov.cn/xxgk/tzgg/202001/t20200106_1556675.html",
        "regulations", notes="京人社仲发〔2019〕160号，落实“护薪”行动、拖欠农民工工资争议处理",
    )


if __name__ == "__main__":
    main()
