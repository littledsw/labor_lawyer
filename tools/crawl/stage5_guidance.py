"""阶段 5：归档办事指南（政务服务事项指南 + 平台在线申请须知）。"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import BEIJING, fetch, fetch_text, html_to_md, save_binary, save_md  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

BANSHI = "https://banshi.beijing.gov.cn/pubtask/download/"
PLATFORM = "https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/"

# 区县 → 政务服务事项页面
GUIDES: list[tuple[str, str]] = [
    ("市级", "https://banshi.beijing.gov.cn/pubtask/task/1/110000000000/1f742ee9-db1e-46f0-b009-0a71220d2f08.html"),
    ("东城区", "https://banshi.beijing.gov.cn/pubtask/task/1/110101000000/63fb2f78-f61a-434e-a834-ac398cd29417.html"),
    ("西城区", "https://banshi.beijing.gov.cn/pubtask/task/1/110102000000/a6d7e5fb-24f3-4c61-8f38-58422a04b3a0.html"),
    ("朝阳区", "https://banshi.beijing.gov.cn/pubtask/task/1/110105000000/75d01c1c-dc66-49fe-93a1-7003eaaedd8a.html"),
    ("丰台区", "https://banshi.beijing.gov.cn/pubtask/task/1/110106000000/92dc114c-c1d4-45c7-b2ec-f7bab0fcdfbd.html"),
    ("海淀区", "https://banshi.beijing.gov.cn/pubtask/task/1/110108000000/8221a886-d916-46ae-9df7-4ab53a973809.html"),
    ("通州区", "https://banshi.beijing.gov.cn/pubtask/task/1/110112000000/c692cfd3-1a9d-4734-8f16-86b3a0dbafee.html"),
    ("昌平区", "https://banshi.beijing.gov.cn/pubtask/task/1/110114000000/412074e4-44d0-46a4-8a72-6573663c49af.html"),
    ("怀柔区", "https://banshi.beijing.gov.cn/pubtask/task/1/110116000000/3b7543c6-4e1b-473a-bbef-4dcf3f9426b4.html"),
    ("平谷区", "https://banshi.beijing.gov.cn/pubtask/task/1/110117000000/49882054-d4d2-422c-88f9-a51b79a7575e.html"),
    ("密云区", "https://banshi.beijing.gov.cn/pubtask/task/1/110118000000/2d5f7972-303f-47f0-8f52-79fd28ce2be6.html"),
    ("延庆区", "https://banshi.beijing.gov.cn/pubtask/task/1/110119000000/4f81697c-d36e-4a5c-b79d-7030a0913c9b.html"),
]

NOTICES: list[tuple[str, str, str]] = [
    ("platform-online-arbitration-notice", PLATFORM + "sqzc/sqzc_ydxz", "北京市劳动人事争议调解仲裁网上服务平台 · 在线申请仲裁须知"),
    ("platform-online-mediation-notice", PLATFORM + "sqtj/sqtj_ydxz", "北京市劳动人事争议调解仲裁网上服务平台 · 在线申请调解须知"),
    ("platform-counter-claim-notice", PLATFORM + "fsq/fsq_ydxz", "北京市劳动人事争议调解仲裁网上服务平台 · 提出反申请须知"),
    ("platform-review-confirm-notice", PLATFORM + "scqr/scqr_ydxz", "北京市劳动人事争议调解仲裁网上服务平台 · 申请审查确认须知"),
    ("platform-death-case-notice", PLATFORM + "gwaj/gwaj_ydxz", "北京市劳动人事争议调解仲裁网上服务平台 · 工（非工）亡案件申请须知"),
]


# ------------------------------------------------------------------ helpers
def grab_json_var(html: str, name: str):
    """抽取页面内 `var name = <json>;` 的 JSON 数据（取首个可解析值）。"""
    for val in grab_all(html, name, flatten=False):
        return val
    return None


def grab_all(html: str, name: str, flatten: bool = True) -> list:
    """抽取页面内某变量的全部 JSON 值；flatten=True 时把列表/字典摊平成 dict 列表。"""
    items: list = []
    for m in re.finditer(rf"var\s+{re.escape(name)}\s*=\s*", html):
        try:
            val = json.JSONDecoder().raw_decode(html[m.end():])[0]
        except json.JSONDecodeError:
            continue
        items.append(val)
    if not flatten:
        return items
    flat: list = []
    for val in items:
        if isinstance(val, list):
            flat.extend(x for x in val if isinstance(x, dict))
        elif isinstance(val, dict):
            flat.append(val)
    return flat


def hidden_div(soup: BeautifulSoup, cls: str) -> str:
    node = soup.select_one(f"div.{cls}")
    return node.get_text("\n", strip=True) if node else ""


def attachment_local_name(doc_id: str, doc_name: str) -> str:
    """附件在仓库内的规范化文件名（同 doc_id 跨区复用同一份文件，避免重复归档）。"""
    safe = re.sub(r"[/\\]+", "-", doc_name)
    return f"{str(doc_id)[:8]}-{safe}"


def fmt_guide(name: str, url: str, html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")
    title_node = soup.find("meta", attrs={"name": "ArticleTitle"})
    title = f"{name}·劳动人事争议仲裁申请办事指南"
    org = hidden_div(soup, "jigou")
    addr = hidden_div(soup, "transactAddr")
    condition = hidden_div(soup, "acceptCondition")
    materials = [x for x in grab_all(html, "material") if "M_NAME" in x or "M_INDEX" in x]
    phases = [x for x in grab_all(html, "process") if "PHASE_NAME" in x]
    process_desc = "; ".join(
        dict.fromkeys(
            str(x.get("CONTENT")) for x in grab_all(html, "process") if x.get("CONTENT")
        )
    )
    laws = [x for x in grab_all(html, "law") if "LAW_NAME" in x]
    questions = [x for x in grab_all(html, "question") if "QUESTION" in x]
    results = [x for x in grab_all(html, "result") if "RESULTNAME" in x]

    lines = [
        f"# {title}",
        "",
        f"> 来源：{url}",
        f"> 事项名称：{title_node.get('content') if title_node else '劳动人事争议仲裁申请'}",
        f"> 实施机构：{org}" if org else "",
        "",
        "## 一、基本信息",
        "",
        f"- 实施机构（办事机构）：{org or '—'}",
        f"- 办理地点与时间：{addr.replace(chr(10), ' / ') if addr else '—'}",
        "- 事项类型：公共服务",
        "",
        "## 二、受理条件",
        "",
        f"{condition or '—'}",
        "",
        "## 三、申请材料",
        "",
    ]
    if materials:
        lines += [
            "| 序号 | 材料名称 | 必要性 | 数量要求 | 来源 | 受理标准 | 依据 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for i, mat in enumerate(materials, 1):
            need = "必需" if str(mat.get("ISNEED")) == "1" else "非必需"
            qty = (f"原件{mat.get('ORIGINAL_NUM') or ''}")
            src = {"10": "申请人自备", "20": "政府部门核发", "30": "中介机构出具"}.get(
                str(mat.get("M_SOURCE")), mat.get("M_SOURCE"))
            lines.append(
                f"| {i} | {str(mat.get('M_NAME') or '').replace('|', '/')} | {need} | {qty} | "
                f"{src} | "
                f"{str(mat.get('AUDIT_POINT') or '—').replace('|', '/')} | "
                f"{str(mat.get('MATERIALSEVIDENCE') or '—').replace('|', '/')} |"
            )
        lines += ["", "### 表格及样例下载", ""]
        seen_docs: set[str] = set()
        for doc_id, doc_name, ext in download_material_files(html):
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            local = attachment_local_name(doc_id, doc_name)
            lines.append(
                f"- [{doc_name}]({BANSHI}{doc_id}.{ext})"
                f"（本地副本：`guidance/files/{local}`）"
            )
    else:
        lines.append("该事项未配置申请材料清单。")

    lines += ["", "## 四、办理流程", ""]
    if process_desc:
        lines.append(f"流程概要：{process_desc}")
        lines.append("")
    if phases:
        lines += ["| 环节 | 办理时限（工作日） | 办理结果 |", "| --- | --- | --- |"]
        for ph in phases:
            lines.append(
                f"| {ph.get('PHASE_NAME') or ph.get('PHASE_STD_NAME') or ''} | "
                f"{ph.get('PHASE_LIMIT') if ph.get('PHASE_LIMIT') is not None else '即办'} | "
                f"{str(ph.get('PHASE_RESULT') or '').replace('|', '/')} |"
            )
    else:
        lines.append("官方页面未提供逐步环节数据（流程概要见上）。" if process_desc else "官方页面未提供结构化流程数据。")

    if results:
        lines += ["", "## 五、办理结果（结果样本）", ""]
        for r in results:
            lines.append(f"- {r.get('RESULTNAME')}（{r.get('RESULTTYPE_EXP') or ''}），时限 {r.get('RESULT_LIMIT') or '—'} 个工作日")

    if laws:
        lines += ["", "## 六、设定依据", ""]
        seen: set[str] = set()
        for law in laws:
            key = f"{law.get('LAW_NAME')}|{law.get('LAW_CODE')}"
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- 《{law.get('LAW_NAME')}》（{law.get('LAW_CODE') or '—'}），制定机关：{law.get('LAW_OWNER') or '—'}")

    if questions:
        lines += ["", "## 七、常见问题", ""]
        for q in questions:
            lines.append(f"- **{q.get('QUESTION')}** {q.get('ANSWER')}")

    lines += [
        "",
        "## 八、说明",
        "",
        "- 本文件由北京市政务服务网公开的政务服务事项办事指南页面抓取整理（原文见 `source_url`），附件为官方发布的表格/样例。",
        "- 办事指南内容可能随政策调整变化，办理前请以官方页面最新内容为准。",
        "",
    ]
    return title, "\n".join(x for x in lines if x is not None), url


def download_material_files(html: str) -> list[tuple[str, str, str]]:
    """办事指南里的表格/样例附件：[(DOC_ID, 文件名, 扩展名)]（仅 doc/docx/pdf/xls/xlsx）。"""
    out: list[tuple[str, str, str]] = []
    for arr_name in ("material", "attachment", "result"):
        for item in grab_all(html, arr_name):
            for id_key, name_key, type_key in (
                ("DOC_ID", "DOC_NAME", "DOC_EXT"),
                ("ATT1_ID", "ATT1_NAME", None),
                ("ATT3_ID", "ATT3_NAME", None),
            ):
                doc_id, doc_name = item.get(id_key), item.get(name_key)
                if not doc_id or not doc_name:
                    continue
                ext = str(item.get(type_key) or pathlib.PurePosixPath(str(doc_name)).suffix.lstrip("."))
                if ext.lower() not in ("doc", "docx", "pdf", "xls", "xlsx"):
                    continue
                if (doc_id, doc_name, ext) in out:
                    continue
                out.append((doc_id, doc_name, ext))
    return out


def main() -> None:
    for name, url in GUIDES:
        try:
            html = fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            print("  GUIDE FAIL", name, exc)
            continue
        title, md, source = fmt_guide(name, url, html)
        save_md(f"guidance/guides/{name}-劳动人事争议仲裁申请办事指南.md", title, md,
                topic="guidance", source_url=source,
                notes="北京市政务服务网政务服务事项办事指南（含受理条件、申请材料、流程、依据）")
        for doc_id, doc_name, ext in download_material_files(html):
            durl = f"{BANSHI}{doc_id}.{ext}"
            rel = f"guidance/files/{attachment_local_name(doc_id, doc_name)}"
            if (BEIJING / rel).exists():
                continue
            try:
                data = fetch(durl, referer=url)
            except Exception as exc:  # noqa: BLE001
                print("  ATT FAIL", durl, exc)
                continue
            save_binary(
                rel, data,
                title=f"{doc_name}", topic="guidance", source_url=url,
                download_url=durl, original_filename=doc_name,
                notes="政务服务事项办事指南中的表格及样例附件（同 doc_id 跨区复用同一份文件）",
            )

    for slug, url, title in NOTICES:
        try:
            html = fetch_text(url)
            _, _, md = html_to_md(html, url)
        except Exception as exc:  # noqa: BLE001
            print("  NOTICE FAIL", url, exc)
            continue
        # 去掉页面导航头
        idx = md.find("须知")
        if idx > 0:
            md = md[idx - 2 if md[idx - 2:idx] == "##" else idx:]
        body = f"> 来源：{url}\n\n{md}\n"
        save_md(f"guidance/{slug}.md", title, body, topic="guidance", source_url=url,
                notes="网上服务平台在线申请须知页面（HTML 抓取转 Markdown）")


if __name__ == "__main__":
    main()
