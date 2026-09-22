"""阶段 20：以国家法律法规数据库（flk.npc.gov.cn）为法律法规/司法解释的唯一信源，全量更新归档。

信源约定（用户 2026-09-22 指定）：
- 只收录时效性为「有效」与「尚未生效」的文件（flk 的 sxx = 3 / 4），已废止版本不归档，
  历史沿革记入 frontmatter 的 notes。
- 记录 制定机关（zdjgName）、公布日期（gbrq）、施行日期（sxrq）、flk 分类（flxz）。
- 分类目录对齐 flk：
    法律        → regions/national/regulations/laws/
    行政法规    → regions/national/regulations/administrative-regulations/
    司法解释    → regions/national/regulations/judicial-interpretations/
    地方法规    → regions/<地区>/regulations/local-regulations/

原文与原件（实测结论）：
- 官方原件可直接下载：详情页「下载」走
  `GET /law-search/download/pc?format=docx|pdf&bbbs=<id>&fileId=<id>`，
  返回的 `data.url` 在**公开可取的 OSS**（flkoss.obs-bj2.cucloud.cn，注意与
  `previewLink` 返回的 `-internal` 域名不同），浏览器上下文可直接 fetch 到字节。
- WPS 版 docx 完整保留段首条号（《劳动法》107 条、《劳动合同法》98 条实测齐全），
  因此正文以 docx 抽取为准，原件（docx + 公报版 pdf）一并归档。
- 兜底：若某件没有 docx 可下载，则记入 state 待人工处理（OFD 阅读器文本层不含条号，不作为正文来源）。

用法：
    python stage20_flk_npc.py --dry-run
    python stage20_flk_npc.py --only-bbbs <bbbs>       # 试跑一件
    python stage20_flk_npc.py --skip-local             # 只做国家层面
    python stage20_flk_npc.py                          # 全量（支持断点续跑）
    python stage20_flk_npc.py --mark-non-flk           # 给非 flk 文件补 source_note
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import (CRAWL, REPO, RETRIEVED_AT, _frontmatter, add_record,  # noqa: E402
                    save_binary, sha256, split_frontmatter)

CACHE = pathlib.Path(CRAWL)
CANDIDATES = CACHE / "flk_candidates.json"
STATE = CACHE / "flk_state.json"
DOWNLOADS = CACHE / "downloads"
FLK = "https://flk.npc.gov.cn"

SXX_NAME = {3: "有效", 4: "尚未生效"}
STATUS = {3: "active", 4: "not-yet-effective"}
CAT_DIR = {
    "法律": "regions/national/regulations/laws",
    "行政法规": "regions/national/regulations/administrative-regulations",
    "司法解释": "regions/national/regulations/judicial-interpretations",
}
FILES_DIR = "regions/national/regulations/files"

PROVINCE_PINYIN = {
    "北京": "beijing", "天津": "tianjin", "上海": "shanghai", "重庆": "chongqing",
    "河北": "hebei", "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin", "黑龙江": "heilongjiang",
    "江苏": "jiangsu", "浙江": "zhejiang", "安徽": "anhui", "福建": "fujian", "江西": "jiangxi",
    "山东": "shandong", "河南": "henan", "湖北": "hubei", "湖南": "hunan", "广东": "guangdong",
    "海南": "hainan", "四川": "sichuan", "贵州": "guizhou", "云南": "yunnan", "陕西": "shaanxi",
    "甘肃": "gansu", "青海": "qinghai", "台湾": "taiwan",
    "内蒙古": "neimenggu", "广西": "guangxi", "西藏": "xizang", "宁夏": "ningxia", "新疆": "xinjiang",
}
MUNICIPALITIES = {"北京", "天津", "上海", "重庆"}

# 与仓库既有落点保持一致：山西在 stage19 已归档到 regions/municipalities/shanxi/，
# 这里沿用同一目录，避免同一地区分裂成 municipalities/ 与 provinces/ 两处
# （legal-assistant 的计算层也按该路径读 parameters.yaml）。
REGION_OVERRIDES = {"山西": "municipalities/shanxi"}

# 司法解释中与劳动仲裁无关的条目（刑事、军队等），第一期不收（用户 2026-09-22 确认）
JUDICIAL_EXCLUDE = [
    "贪污养老、医疗等社会保险基金能否适用",
    "挪用失业保险基金和下岗职工基本生活保障资金",
    "国家工作人员利用职务上的便利为他人谋取利益离退休后收受财物",
    "无期徒刑犯减刑",
    "军队离退休干部腾退军产房",
]


def region_from_authority(authority: str) -> str | None:
    """把 制定机关 映射到 regions/ 下的地区目录；无法判定时返回 None。"""
    if not authority:
        return None
    a = authority.replace("人民代表大会", "").replace("常务委员会", "").replace("人民政府", "").strip()
    m = re.match(r"^([\u4e00-\u9fa5]{2,3})(省|市|自治区|特别行政区)?", a)
    if not m:
        return None
    name, suffix = m.group(1), m.group(2) or ""
    for prov, pinyin in PROVINCE_PINYIN.items():
        if name.startswith(prov):
            if prov in REGION_OVERRIDES:
                return REGION_OVERRIDES[prov]
            if prov in MUNICIPALITIES and suffix != "省":
                return f"municipalities/{pinyin}"
            return f"provinces/{pinyin}"
    return None


# ------------------------------------------------------------------ 浏览器侧调用
CHALLENGE_HINT = "Please enable JavaScript"


def _raw_fetch(b, url: str, var: str = "__r", tries: int = 40) -> str:
    b.evaluate(f"window.{var} = null;")
    b.evaluate("fetch(%s).then(r => r.text().then(t => window.%s = t)).catch(e => window.%s = 'ERR ' + e)"
               % (json.dumps(url), var, var))
    for _ in range(tries):
        raw = b.evaluate(f"window.{var} || ''") or ""
        if raw:
            return raw
        time.sleep(0.4)
    return ""


def _fetch(b, url: str, *, var: str = "__r", backoff: tuple[int, ...] = (15, 30, 60, 90),
           pace: float = 2.5) -> dict:
    """带 WAF 退避的请求：命中 JS 挑战页则等待并重载页面续期会话后重试。"""
    for wait in (0,) + backoff:
        if wait:
            print(f"      WAF 挑战，等待 {wait}s 后重试…", flush=True)
            time.sleep(wait)
            b.render(f"{FLK}/search", wait=8)
        time.sleep(pace)
        raw = _raw_fetch(b, url, var)
        if raw.startswith("{"):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        if not raw.startswith("<"):
            return {}
    print("      ✗ 持续被 WAF 挑战，放弃该请求", flush=True)
    return {}


def flk_detail(b, bbbs: str) -> dict:
    return (_fetch(b, f"/law-search/search/flfgDetails?bbbs={bbbs}") or {}).get("data") or {}


def download_link(b, bbbs: str, fmt: str, file_id: str = "") -> str:
    """fmt: docx（WPS 版）或 pdf（公报原版）。返回公开可取的下载直链。"""
    j = _fetch(b, f"/law-search/download/pc?format={fmt}&bbbs={bbbs}&fileId={file_id}")
    return ((j or {}).get("data") or {}).get("url") or ""


def save_via_browser(b, url: str, filename: str, *, timeout: float = 240.0) -> bytes | None:
    """用浏览器把远端文件落到本地下载目录（fetch → blob → a[download]），返回字节。"""
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    target = DOWNLOADS / filename
    if target.exists():
        target.unlink()
    b.evaluate("""(() => { window.__dl = 'start';
      fetch(%s).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.blob(); })
        .then(bl => { const a = document.createElement('a');
          a.href = URL.createObjectURL(bl); a.download = %s;
          document.body.appendChild(a); a.click(); a.remove(); window.__dl = 'ok'; })
        .catch(e => { window.__dl = 'ERR ' + e; });
    })()""" % (json.dumps(url), json.dumps(filename)))
    state = ""
    for _ in range(60):
        state = b.evaluate("window.__dl || ''") or ""
        if state.startswith(("ok", "ERR")):
            break
        time.sleep(0.5)
    if not state.startswith("ok"):
        print(f"      下载失败：{state[:120]}", flush=True)
        return None
    for _ in range(int(timeout * 2)):
        if target.exists() and not list(DOWNLOADS.glob(filename + ".crdownload")):
            time.sleep(0.3)
            return target.read_bytes()
        time.sleep(0.5)
    print("      下载超时", flush=True)
    return None


def clean_line(t: str) -> str:
    t = re.sub(r"[\u3000\t]+", " ", (t or "")).strip()
    return re.sub(r" {2,}", " ", t)


def docx_paragraphs(path: pathlib.Path) -> list[str]:
    import docx  # noqa: PLC0415

    return [c for c in (clean_line(p.text) for p in docx.Document(str(path)).paragraphs) if c]


def extract_paragraphs(data: bytes, stem: str) -> tuple[list[str], str]:
    """按实际文件格式抽取段落，返回 (段落, 实际扩展名)。

    flk 的 `format=docx` 偶尔给的是**老式 .doc**（OLE2 头 d0cf11e0），python-docx 读不了，
    用 macOS 自带 `textutil` 转纯文本兜底。
    """
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    if data[:2] == b"PK":                                   # 真 docx
        p = DOWNLOADS / f"{stem}.docx"
        p.write_bytes(data)
        try:
            return docx_paragraphs(p), "docx"
        except Exception as exc:  # noqa: BLE001
            print(f"      docx 解析失败：{exc}", flush=True)
            return [], "docx"
    if data[:4] == b"\xd0\xcf\x11\xe0":                     # 老式 .doc
        import subprocess  # noqa: PLC0415

        p = DOWNLOADS / f"{stem}.doc"
        p.write_bytes(data)
        try:
            out = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(p)],
                                 capture_output=True, timeout=120)
            text = out.stdout.decode("utf-8", "ignore")
            return [c for c in (clean_line(l) for l in text.splitlines()) if c], "doc"
        except Exception as exc:  # noqa: BLE001
            print(f"      .doc 转换失败：{exc}", flush=True)
            return [], "doc"
    return [], "bin"


# ------------------------------------------------------------------ 正文与落盘
def body_from_docx(paras: list[str]) -> str:
    """docx 段落转 Markdown 正文：段间空行，段首条号自然成段。"""
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(paras)).strip() + "\n"


def write_md(rel: str, body: str, meta: dict) -> int:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(meta, content_hash=sha256(body.encode()), local_path=rel)
    path.write_text(_frontmatter(meta) + "\n" + body, encoding="utf-8")
    add_record(dict(meta, file_type="markdown", bytes=len(body.encode()), downloaded=False))
    return len(body.encode())


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def mark_non_flk(dry: bool = False) -> int:
    """给 flk 未收录的现行文件（部门规章、地方政府规章）补 `source_note` 标注。"""
    flk_paths = {v.get("local_path") for v in load_state().values() if v.get("status") == "ok"}
    marked = 0
    for path in sorted((REPO / "regions").rglob("*.md")):
        rel = str(path.relative_to(REPO))
        if "/regulations/" not in rel or "/local-regulations/" in rel or rel in flk_paths:
            continue
        try:
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not meta:
            continue
        note = "信源：非 flk（国家规章库 / 地方政府网站）；国家法律法规数据库未收录，本期未更新"
        if meta.get("source_note") == note:
            continue
        meta["source_note"] = note
        if not dry:
            path.write_text(_frontmatter(meta) + "\n" + body, encoding="utf-8")
        print(f"  + {rel}")
        marked += 1
    print(f"标注 {marked} 个文件{'（dry-run）' if dry else ''}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只列出将抓取的文件")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 份")
    ap.add_argument("--only-bbbs", default="", help="只处理指定 bbbs（逗号分隔）")
    ap.add_argument("--skip-local", action="store_true", help="跳过地方法规")
    ap.add_argument("--only-regions", default="",
                    help="只处理指定地区的地方法规，逗号分隔（如 municipalities/beijing,municipalities/shanxi）")
    ap.add_argument("--redo", action="store_true", help="忽略断点，重抓已完成项")
    ap.add_argument("--no-pdf", action="store_true", help="只归档 docx 原件，不存公报版 pdf")
    ap.add_argument("--mark-non-flk", action="store_true", help="只补 source_note 标注，然后退出")
    args = ap.parse_args()

    if args.mark_non_flk:
        return mark_non_flk(dry=args.dry_run)

    if not CANDIDATES.exists():
        raise SystemExit(f"缺少候选清单 {CANDIDATES}，先运行 flk_collect.py")
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))

    todo, excluded = [], []
    only_regions = {r.strip() for r in args.only_regions.split(",") if r.strip()}
    for c in candidates:
        if args.skip_local and c["flxz"] == "地方法规":
            continue
        if only_regions and c["flxz"] != "地方法规":
            continue
        if c["flxz"] == "司法解释" and any(x in c["title"] for x in JUDICIAL_EXCLUDE):
            excluded.append(c["title"])
            continue
        if args.only_bbbs and c["bbbs"] not in args.only_bbbs.split(","):
            continue
        region = None
        if c["flxz"] == "地方法规":
            region = region_from_authority(c.get("zdjgName") or "")
            if not region:
                continue
            if only_regions and region not in only_regions:
                continue
        c["_region"] = region
        todo.append(c)
    if args.limit:
        todo = todo[: args.limit]

    if excluded:
        print(f"按相关性过滤剔除 {len(excluded)} 件司法解释：")
        for t in excluded:
            print("  -", t)
    print(f"候选 {len(candidates)} 条，本次处理 {len(todo)} 条")
    if args.dry_run:
        for c in todo[:60]:
            tgt = CAT_DIR.get(c["flxz"]) or f"regions/{c['_region']}/regulations/local-regulations"
            print(f"  [{c['flxz']}] {c['title']} -> {tgt}/  ({SXX_NAME.get(c['sxx'])}, "
                  f"公布 {c.get('gbrq')}, 施行 {c.get('sxrq')}, {c.get('zdjgName')})")
        if len(todo) > 60:
            print(f"  …… 其余 {len(todo) - 60} 条")
        return 0

    from browser_fetch import Browser  # noqa: PLC0415

    state = load_state()
    b = Browser()
    b.start()
    b.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(DOWNLOADS))
    ok = fail = skip = 0
    try:
        b.render(f"{FLK}/search", wait=8)
        for i, c in enumerate(todo, 1):
            bbbs, title = c["bbbs"], c["title"]
            if not args.redo and state.get(bbbs, {}).get("status") == "ok":
                skip += 1
                continue
            print(f"[{i}/{len(todo)}] {title} ({c['flxz']}/{SXX_NAME.get(c['sxx'])})", flush=True)

            det = flk_detail(b, bbbs)
            for _ in range(2):
                if det:
                    break
                print("      详情为空，等待 30s 重试…", flush=True)
                time.sleep(30)
                det = flk_detail(b, bbbs)
            file_id = str(det.get("fileId") or "")

            if c["flxz"] == "地方法规":
                region, level = c["_region"], ("province" if c["_region"].startswith("provinces/") else "municipality")
                rel = f"regions/{c['_region']}/regulations/local-regulations/{title}.md"
                rel_files_dir = "regulations/local-regulations/files"      # 相对 region 根目录
            else:
                region, level = "national", "national"
                rel = f"{CAT_DIR[c['flxz']]}/{title}.md"
                rel_files_dir = "regulations/files"

            # 1) 官方原件：WPS 版 docx（正文来源）+ 公报原版 pdf（归档）
            paras: list[str] = []
            originals: list[str] = []
            for fmt in ("docx",) + (() if args.no_pdf else ("pdf",)):
                url = download_link(b, bbbs, fmt, file_id)
                if not url:
                    print(f"      {fmt}：未取到下载链接", flush=True)
                    continue
                name = f"{bbbs}-{fmt}"
                cached = DOWNLOADS / f"{name}.{fmt}"
                if cached.exists() and cached.stat().st_size > 0:
                    data = cached.read_bytes()                  # 复用已下载的原件，避免重复拉取
                else:
                    data = save_via_browser(b, url, f"{name}.{fmt}")
                if not data:
                    continue
                ext = fmt
                if fmt == "docx":
                    paras, ext = extract_paragraphs(data, name)
                rec = save_binary(
                    f"{rel_files_dir}/{title}-{bbbs[-6:]}.{ext}", data,
                    title=f"{title}（flk {ext} 原件）", topic="regulations",
                    source_url=f"{FLK}/detail?id={bbbs}", download_url=url,
                    published_at=c.get("gbrq"), authority=c.get("zdjgName"),
                    notes=f"国家法律法规数据库官方原件（{'WPS 版' if fmt == 'docx' else '公报原版'}，"
                          f"实际格式 {ext}）；时效性 {SXX_NAME.get(c['sxx'])}；下载链接为 flk 签名直链（限时）",
                    original_filename=f"{title}.{ext}", region=region, level=level)
                originals.append(rec["local_path"])

            if not paras:
                print("      ✗ docx 未取到/解析失败，跳过（无正文来源）", flush=True)
                state[bbbs] = {"status": "no-docx", "title": title, "originals": originals}
                save_state(state)
                fail += 1
                continue

            # 2) 正文 + frontmatter
            body = body_from_docx(paras)
            notes = [f"信源：国家法律法规数据库 {FLK}/detail?id={bbbs}（时效性：{SXX_NAME.get(c['sxx'])}）",
                     f"flk 分类：{c['flxz']}（flfgCodeId={c.get('flfgCodeId')}）；版本标识 bbbs={bbbs}",
                     "正文由官方 WPS 版 docx 原件抽取（段首条号完整）"]
            published = c.get("gbrq")
            if not published:
                # flk 偶有未记录公布日期的条目：从原件题注里取「通过/公布」日期
                m = re.search(r"(1[89]\d{2}|20\d{2})年(\d{1,2})月(\d{1,2})日",
                              "\n".join(paras[:3]) if paras else "")
                if m:
                    published = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    notes.append(f"公布日期：flk 记录未提供，取自原件题注（{published}）")
            if not c.get("sxrq"):
                notes.append("施行日期：flk 记录未提供（见正文题注）")
            hist = [h for h in (det.get("lsyg") or []) if h.get("bbbs") != bbbs]
            if hist:
                notes.append("历史沿革（未归档的旧版本）：" + "；".join(f"{h.get('gbrq')}（bbbs={h.get('bbbs')}）" for h in hist))
            if originals:
                notes.append("已归档原件：" + "、".join(originals))
            meta = {
                "title": title, "region": region, "level": level, "topic": "regulations",
                "authority": c.get("zdjgName"), "published_at": published,
                "effective_at": c.get("sxrq"), "source_url": f"{FLK}/detail?id={bbbs}",
                "download_url": None, "retrieved_at": RETRIEVED_AT,
                "status": STATUS.get(c["sxx"], "active"), "effect_status": SXX_NAME.get(c["sxx"]),
                "flk_category": c["flxz"], "flk_bbbs": bbbs, "body_structure": "docx-paragraphs",
                "articles_count": len(re.findall(r"第[一二三四五六七八九十百零〇]+条", body)) or None,
                "notes": " ".join(notes),
            }
            size = write_md(rel, body, meta)
            print(f"      md {rel} {size}B；原件 {len(originals)} 份", flush=True)
            state[bbbs] = {"status": "ok", "title": title, "chars": len(body),
                           "local_path": rel, "originals": originals}
            save_state(state)
            ok += 1
            time.sleep(2)
    finally:
        b.close()

    print(f"\n完成：成功 {ok}、失败 {fail}、跳过（已完成） {skip}")
    print(f"状态文件：{STATE}；接着跑 stage6_indexes.py 与 verify.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
