"""阶段 2：归档北京市劳动人事争议调解仲裁机构名录（官方查询接口数据）。"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import fetch_text, save_binary, save_md  # noqa: E402

API = "https://banshi.beijing.gov.cn/zwfwapi/bjmap/query"
PAGE = "https://banshi.beijing.gov.cn/zwfwapi/cycx/shbz/ldrszytjzcjg/query.html"


def query() -> list[dict]:
    out: list[dict] = []
    page = 0
    while True:
        url = f"{API}?page={page}&size=50&categoryId=ldrszytjzcjg&text="
        payload = json.loads(fetch_text(url, referer=PAGE))
        if payload.get("code") != 100:
            raise RuntimeError(payload)
        data = payload["data"]
        out.extend(data["datas"])
        total = int(data["total"])
        page += 1
        if page * 50 >= total or page > 20:
            break
    return out


def main() -> None:
    rows = query()
    print("institutions:", len(rows))
    raw = json.dumps(rows, ensure_ascii=False, indent=1).encode()
    save_binary(
        "institutions/arbitration-institutions.json", raw,
        title="北京市劳动人事争议调解仲裁机构名录（查询接口原始数据）",
        topic="institutions", source_url=PAGE,
        download_url=f"{API}?page=0&size=50&categoryId=ldrszytjzcjg&text=",
        notes="北京市政务服务网「劳动人事争议调解仲裁机构查询」接口返回的公开名录数据（JSON）",
    )

    lines = [
        "# 北京市劳动人事争议调解仲裁机构名录",
        "",
        f"共 {len(rows)} 家机构，数据来自北京市政务服务网「劳动人事争议调解仲裁机构查询」公开接口。",
        "字段含义：`lianshijian` 为对外办公时间，`tel` 为咨询电话（部分含业务范围说明），",
        "`orignal_url` 为北京市政务地图对应机构页面。",
        "",
        "## 机构一览",
        "",
        "| 序号 | 行政区 | 机构名称 | 咨询电话 | 地址 | 对外办公时间 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        def cell(v: object) -> str:
            return str(v or "").replace("|", "/").replace("\n", "<br>").strip()
        lines.append(
            f"| {i} | {cell(r.get('regionName'))} | {cell(r.get('name'))} | "
            f"{cell(r.get('tel'))} | {cell(r.get('addr'))} | {cell(r.get('lianshijian'))} |"
        )
    lines += [
        "",
        "## 查询方式",
        "",
        f"- 查询页面：{PAGE}",
        "- 接口：`GET https://banshi.beijing.gov.cn/zwfwapi/bjmap/query"
        "?page=0&size=50&categoryId=ldrszytjzcjg&text=`",
        "- 页面 UI 需要滑动验证码，接口本身对公开名录数据无需验证；本项目只归档公开名录，不绕过任何访问控制。",
        "",
        "## 备注",
        "",
        "名录信息可能随机构调整而变化，使用前请以官方查询页面实时结果为准。",
    ]
    save_md(
        "institutions/arbitration-institutions.md", "北京市劳动人事争议调解仲裁机构名录",
        "\n".join(lines), topic="institutions", source_url=PAGE,
        notes="由官方查询接口数据整理而成的 Markdown 名录，伴随原始 JSON 一并归档",
    )
    print("institutions md ok")


if __name__ == "__main__":
    main()
