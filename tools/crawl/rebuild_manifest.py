"""从仓库现状重建 manifest.json（不联网）。

`stage6_indexes.py`（生成 indexes/、主题 README、SOURCES.yaml、CHANGELOG）与
`verify.py`（校验 frontmatter、附件类型、索引一致性）都从
`<cache>/manifest.json` 读元数据；该文件位于 `.cache/`（已 gitignore），
清理缓存或换机器后会丢失，导致索引与校验流程无法重跑。

本脚本按磁盘上的两类事实来源重建同一份 manifest：

- `regions/**/*.md`            → 从 YAML frontmatter 取元数据
- `regions/**/<其他文件>`      → 从同名 `<文件>.meta.yaml` 侧车取元数据

元数据字段与 `stage6_indexes.CSV_FIELDS` 对齐，供两者直接消费。

用法：

    # 重建（默认写入 <repo>/.cache/labor_lawyer_crawl/manifest.json）
    uv run --with pyyaml python tools/crawl/rebuild_manifest.py

    # 重建并核对重建结果与已入库的 indexes/documents.json 是否一致
    uv run --with pyyaml python tools/crawl/rebuild_manifest.py --check

环境变量与 common.py 保持一致：`LABOR_LAWYER_REPO`、`LABOR_LAWYER_CACHE`。

`--check` 的作用：documents.json 是由 manifest 生成的产物，两者字段一致即证明
重建没有丢信息（新增资料后 documents.json 会落后，此时应先用 `--write-docs`
把索引刷新再核对，或直接以 `--check` 的报告为差异清单）。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import sys

import yaml

REPO = pathlib.Path(os.environ.get("LABOR_LAWYER_REPO") or pathlib.Path.cwd()).resolve()
CRAWL = pathlib.Path(
    os.environ.get("LABOR_LAWYER_CACHE") or (REPO / ".cache" / "labor_lawyer_crawl")
)
MANIFEST = CRAWL / "manifest.json"

# 与 stage6_indexes.CSV_FIELDS 保持一致（顺序也一致，便于逐列比对）
CSV_FIELDS = [
    "region", "level", "topic", "local_path", "title", "authority", "published_at", "source_url",
    "download_url", "retrieved_at", "status", "content_hash", "file_type", "bytes",
]

# 非归档内容：说明页与侧车文件本身不进 manifest（与 verify.py 的例外一致）
SKIP_NAMES = {"README.md", "SOURCE.md", "official-index.md", ".gitkeep"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_frontmatter(text: str) -> tuple[dict, str]:
    """返回 (frontmatter dict, body)。

    body 的边界与 common.save_md 写入时一致：`---\\n<fm>\\n---\\n\\n<body>`，
    因此 bytes / content_hash 都按 body 计算（见 save_md: sha256(body.encode())）。
    """
    if not text.startswith("---\n"):
        raise ValueError("缺少 frontmatter")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("frontmatter 未闭合")
    meta = yaml.safe_load(text[4:end + 1]) or {}
    body_start = end + 4                      # text[end:end+4] == "\n---"
    if text[body_start:body_start + 1] == "\n":   # 收尾换行
        body_start += 1
    if text[body_start:body_start + 1] == "\n":   # save_md 写入的空行分隔符
        body_start += 1
    return meta, text[body_start:]


def record_from_markdown(path: pathlib.Path) -> tuple[dict, str | None]:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    rel = str(path.relative_to(REPO))
    rec = {k: meta.get(k) for k in CSV_FIELDS}
    rec["region"] = meta.get("region") or "/".join(rel.split("/")[1:-2])
    rec["local_path"] = meta.get("local_path") or rel
    rec["file_type"] = "markdown"
    rec["bytes"] = len(body.encode())          # 与 save_md 同口径：只算正文
    warning = None
    if meta.get("content_hash") and sha256(body.encode()) != meta["content_hash"]:
        warning = f"content_hash 与正文不符（磁盘正文已变，未同步 frontmatter）: {rel}"
    return rec, warning


def record_from_sidecar(path: pathlib.Path) -> tuple[dict, str | None]:
    meta = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    target = path.with_name(path.name[: -len(".meta.yaml")])
    rel = str(target.relative_to(REPO))
    rec = {k: meta.get(k) for k in CSV_FIELDS}
    rec["local_path"] = meta.get("local_path") or rel
    rec["file_type"] = target.suffix.lstrip(".").lower()
    rec["bytes"] = target.stat().st_size
    warning = None
    if meta.get("content_hash") and sha256(target.read_bytes()) != meta["content_hash"]:
        warning = f"content_hash 与文件不符（文件已被替换）: {rel}"
    return rec, warning


def collect() -> tuple[list[dict], list[str], list[str]]:
    """返回 (records, 跳过文件的说明, content_hash 告警)。"""
    regions = REPO / "regions"
    if not regions.exists():
        raise SystemExit(f"未找到 {regions}")
    records: list[dict] = []
    problems: list[str] = []
    warnings: list[str] = []
    for path in sorted(regions.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES or path.name.endswith(".meta.yaml"):
            continue
        try:
            if path.suffix == ".md":
                rec, warn = record_from_markdown(path)
            else:
                sidecar = path.with_name(path.name + ".meta.yaml")
                if not sidecar.exists():
                    problems.append(f"缺少侧车元数据: {path.relative_to(REPO)}")
                    continue
                rec, warn = record_from_sidecar(sidecar)
        except Exception as exc:  # noqa: BLE001 - 逐条报告，不中断整体重建
            problems.append(f"{path.relative_to(REPO)}: {exc}")
            continue
        records.append(rec)
        if warn:
            warnings.append(warn)
    return records, problems, warnings


def sorted_records(records: list[dict]) -> list[dict]:
    """与 stage6_indexes.write_indexes 相同的排序，便于比对 documents.json。"""
    return sorted(records, key=lambda r: (r.get("region", ""), r.get("topic", ""),
                                          r.get("published_at") or "", r.get("title", "")))


def project(records: list[dict]) -> list[dict]:
    return [{k: r.get(k) for k in CSV_FIELDS} for r in records]


def check(records: list[dict]) -> int:
    docs = REPO / "indexes" / "documents.json"
    if not docs.exists():
        print(f"未找到 {docs}，跳过核对")
        return 1
    want = json.loads(docs.read_text(encoding="utf-8"))
    got = project(sorted_records(records))
    by_path = {r["local_path"]: r for r in want}
    print(f"manifest 重建 {len(got)} 条 / documents.json {len(want)} 条")
    problems, drift = [], []
    for rec in got:
        old = by_path.pop(rec["local_path"], None)
        if old is None:
            problems.append(f"documents.json 缺失: {rec['local_path']}")
            continue
        diff = {k: (old.get(k), rec.get(k)) for k in CSV_FIELDS
                if k != "bytes" and old.get(k) != rec.get(k)}
        if diff:
            problems.append(f"字段不一致 {rec['local_path']}: {diff}")
        elif old.get("bytes") != rec.get("bytes"):
            # bytes 是抓取当时的快照值；md 文件在抓取后补过 frontmatter/正文，
            # 因此 documents.json 里的 bytes 会偏小（陈旧），磁盘现值才是对的。
            # verify.py 不校验该字段，故只作提示，不算不一致。
            drift.append((rec["local_path"], old.get("bytes"), rec.get("bytes")))
    problems += [f"documents.json 多出记录: {p}" for p in by_path]
    if drift:
        print(f"\n仅 bytes 陈旧（磁盘现值更大，索引刷新后即校正）: {len(drift)} 条，示例：")
        for path, old_b, new_b in drift[:3]:
            print(f"  - {path}: {old_b} → {new_b}")
    if problems:
        print("\n不一致:")
        for p in problems:
            print("  -", p)
        return 1
    print("核对通过：元数据字段与 documents.json 完全一致")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只核对，不写 manifest")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写 manifest")
    args = ap.parse_args()

    records, problems, warnings = collect()
    if problems:
        print("存在问题的文件（已跳过）:")
        for p in problems:
            print("  -", p)
        if len(problems) > 10:
            print(f"  …… 共 {len(problems)} 个")
    if warnings:
        print(f"content_hash 告警（{len(warnings)} 条，正文已改但 frontmatter 未同步）:")
        for w in warnings[:10]:
            print("  -", w)
        if len(warnings) > 10:
            print(f"  …… 其余 {len(warnings) - 10} 条")

    missing = [r["local_path"] for r in records
               if not all(r.get(k) for k in ("title", "region", "topic", "source_url",
                                             "retrieved_at", "status", "content_hash"))]
    print(f"重建记录 {len(records)} 条（frontmatter/侧车字段不全: {len(missing)} 条）")
    for m in missing[:10]:
        print("  - 字段不全:", m)

    if args.check:
        return check(records)
    if args.dry_run:
        return 0

    CRAWL.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已写入 {MANIFEST.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
