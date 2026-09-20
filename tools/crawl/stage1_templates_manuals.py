"""阶段 1：归档平台「文书模板（常用模板下载）」与「操作手册」原始文件。"""
from __future__ import annotations

import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import BEIJING, fetch, save_binary  # noqa: E402

BASE = "https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration"
TEMPLATE_PAGE = BASE + "/html/home/newsList?items=10"
MANUAL_PAGE = BASE + "/html/home/index"

TEMPLATES = [
    ("劳动人事争议调解申请书.docx", "劳动人事争议调解申请书"),
    ("授权委托书（申请调解）.docx", "授权委托书（申请调解）"),
    ("法定代表人身份证明书（通用）.docx", "法定代表人身份证明书（通用）"),
    ("劳动人事争议仲裁申请书.docx", "劳动人事争议仲裁申请书"),
    ("授权委托书（申请仲裁）.docx", "授权委托书（申请仲裁）"),
]

MANUALS = [
    ("劳动者操作手册.pdf", "劳动者操作手册"),
    ("用人单位操作手册.pdf", "用人单位操作手册"),
    ("代理人操作手册.pdf", "代理人操作手册"),
]


def main() -> None:
    for name, title in TEMPLATES:
        url = f"{BASE}/public/doc/{urllib.parse.quote(name)}"
        data = fetch(url, referer=BASE + "/html/home/index")
        save_binary(
            f"templates/files/{name}", data, title=title, topic="templates",
            source_url=TEMPLATE_PAGE, download_url=url,
            notes="平台首页「常用模板下载」栏目（items=10）原始 docx",
        )
    for name, title in MANUALS:
        url = f"{BASE}/public/doc/{urllib.parse.quote(name)}"
        data = fetch(url, referer=BASE + "/html/home/index")
        save_binary(
            f"manuals/files/{name}", data, title=title, topic="manuals",
            source_url=MANUAL_PAGE, download_url=url,
            notes="平台首页「操作手册」栏目原始 PDF",
        )


if __name__ == "__main__":
    main()
