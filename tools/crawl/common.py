"""劳动仲裁公开资料抓取公共库（Hermes 私有草稿区，不进仓库）。

用法：在 labor_lawyer_crawl 下 `python stageN_xxx.py`，抓取结果写入
/Users/abaaba/workspace/projects/labor_lawyer，并在 manifest.json 累积元数据。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

import markdownify
import yaml
from bs4 import BeautifulSoup

REPO = pathlib.Path(os.environ.get("LABOR_LAWYER_REPO") or pathlib.Path.cwd()).resolve()
BEIJING = REPO / "regions/municipalities/beijing"
CRAWL = pathlib.Path(
    os.environ.get("LABOR_LAWYER_CACHE") or (REPO / ".cache" / "labor_lawyer_crawl")
)
MANIFEST = CRAWL / "manifest.json"
CACHE = CRAWL / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
RETRIEVED_AT = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
REGION = "municipalities/beijing"
LEVEL = "municipality"
AUTHORITY = "北京市人力资源和社会保障局"


def region_root(region: str) -> pathlib.Path:
    """地区根目录，如 region='municipalities/beijing' 或 'national'。"""
    return REPO / "regions" / region


def default_level(region: str) -> str:
    return "national" if region == "national" else "municipality"


# ---------------------------------------------------------------- network
def solve_eo_bot(html_text: str) -> str | None:
    """解析人社部网站的 EO_Bot 反爬挑战脚本，返回所需 Cookie。"""
    ssid = re.search(r"\(t,\s*(\d{6,})\)", html_text)
    props = re.findall(r"(\w{5,}):(\d{6,})", html_text)
    if not ssid or not props:
        return None
    total = sum(int(v) for _, v in props)
    return f"__tst_status={total}#; EO_Bot_Ssid={ssid.group(1)}"


def fetch(url: str, referer: str | None = None, cache: bool = True, timeout: int = 45) -> bytes:
    """下载 URL 内容（带本地缓存，避免重复请求）。"""
    key = hashlib.sha1(url.encode()).hexdigest() + ".bin"
    cp = CACHE / key
    if cache and cp.exists() and cp.stat().st_size > 0:
        return cp.read_bytes()
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "*/*")
    if referer:
        req.add_header("Referer", referer)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            # 人社部等站点会返回反爬挑战页，解出 Cookie 后重试
            if len(data) < 4000 and b"EO_Bot_Ssid" in data:
                cookie = solve_eo_bot(data.decode("utf-8", "ignore"))
                if cookie:
                    req2 = urllib.request.Request(url)
                    req2.add_header("User-Agent", UA)
                    req2.add_header("Accept", "*/*")
                    req2.add_header("Cookie", cookie)
                    if referer:
                        req2.add_header("Referer", referer)
                    with urllib.request.urlopen(req2, timeout=timeout) as r2:
                        data = r2.read()
            cp.write_bytes(data)
            time.sleep(0.4)
            return data
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                raise
            print("  retry", url, exc)
            time.sleep(2)
    raise RuntimeError(url)


def fetch_text(url: str, referer: str | None = None, cache: bool = True) -> str:
    raw = fetch(url, referer=referer, cache=cache)
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "ignore")


# ---------------------------------------------------------------- html → md
def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def page_title(soup: BeautifulSoup) -> str:
    for node in (soup.find("h1"), soup.find("meta", attrs={"name": "ArticleTitle"}), soup.find("title")):
        if node is None:
            continue
        text = node.get("content", "") if node.name == "meta" else node.get_text(" ", strip=True)
        text = (text or "").split("_")[0].strip()
        if text:
            return text
    return ""


def page_date(html: str, soup: BeautifulSoup, url: str) -> str | None:
    meta = soup.find("meta", attrs={"name": "PubDate"})
    raw = (meta.get("content") if meta else "") or ""
    m = re.search(r"(20\d\d)[-/年](\d{1,2})[-/月](\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"/t(20\d\d)(\d\d)(\d\d)_", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(20\d\d)[-/年](\d{1,2})[-/月](\d{1,2})", html)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def main_node(soup: BeautifulSoup):
    """定位正文节点：优先常见 TRS 容器，否则选文本量最大的 div。"""
    for sel in ("div.view", "div.TRS_PreAppend", "#mainText", "div.task-detail", "div.detail", "article"):
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            return node
    best, best_len = None, 0
    for div in soup.find_all("div"):
        txt = div.get_text(" ", strip=True)
        if len(txt) > best_len and len(div.find_all("a")) < max(5, len(txt) // 300):
            best, best_len = div, len(txt)
    return best


def html_to_md(html: str, url: str = "") -> tuple[str, str | None, str]:
    soup = soup_of(html)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = page_title(soup)
    date = page_date(html, soup, url)
    node = main_node(soup)
    if node is None:
        return title, date, ""
    for tag in node(["script", "style"]):
        tag.decompose()
    md = markdownify.markdownify(str(node), heading_style="ATX", bullets="-")
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return title, date, md.strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- writing
def _fmt(v) -> str:
    """标量 → YAML 安全字面量（字符串用 JSON 双引号形式，YAML 兼容）。"""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def _frontmatter(meta: dict) -> str:
    order = [
        "title", "region", "level", "topic", "authority", "published_at",
        "source_url", "download_url", "retrieved_at", "status", "content_hash",
        "file", "local_path", "notes",
    ]
    lines = ["---"]
    for k in order:
        if meta.get(k) is not None:
            lines.append(f"{k}: {_fmt(meta[k])}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def add_record(rec: dict) -> None:
    rec.setdefault("region", REGION)
    rec.setdefault("level", LEVEL)
    rec.setdefault("status", "active")
    data = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []
    data = [r for r in data if r.get("local_path") != rec.get("local_path")]
    data.append(rec)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def save_md(rel: str, title: str, md: str, *, topic: str, source_url: str,
            published_at: str | None = None, authority: str = AUTHORITY,
            notes: str | None = None, extra_meta: dict | None = None,
            region: str = REGION, level: str | None = None) -> dict:
    path = region_root(region) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = md.rstrip() + "\n"
    meta = {
        "title": title, "region": region, "level": level or default_level(region), "topic": topic,
        "authority": authority, "published_at": published_at,
        "source_url": source_url, "retrieved_at": RETRIEVED_AT,
        "status": "active", "content_hash": sha256(body.encode()),
        "local_path": str(path.relative_to(REPO)), "notes": notes,
    }
    if extra_meta:
        meta.update(extra_meta)
    path.write_text(_frontmatter(meta) + "\n" + body, encoding="utf-8")
    rec = dict(meta, file_type="markdown", bytes=len(body.encode()), downloaded=False)
    add_record(rec)
    print("  md  ", rel, f"{len(body)}B")
    return rec


def save_binary(rel: str, data: bytes, *, title: str, topic: str, source_url: str,
                download_url: str | None = None, published_at: str | None = None,
                authority: str = AUTHORITY, notes: str | None = None,
                original_filename: str | None = None,
                region: str = REGION, level: str | None = None) -> dict:
    path = region_root(region) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    meta = {
        "title": title, "region": region, "level": level or default_level(region), "topic": topic,
        "authority": authority, "published_at": published_at,
        "source_url": source_url, "download_url": download_url or source_url,
        "retrieved_at": RETRIEVED_AT, "status": "active",
        "content_hash": sha256(data), "local_path": str(path.relative_to(REPO)),
        "file": path.name, "original_filename": original_filename or path.name,
        "notes": notes,
    }
    sidecar = path.with_suffix(path.suffix + ".meta.yaml")
    sidecar.write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    rec = dict(meta, file_type=path.suffix.lstrip("."), bytes=len(data), downloaded=True)
    add_record(rec)
    print("  file", rel, f"{len(data)}B")
    return rec
