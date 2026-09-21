"""校验：frontmatter 完整性、附件类型、索引一致性。"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import BEIJING, MANIFEST, REPO  # noqa: E402

import yaml  # noqa: E402

REQUIRED = ["title", "region", "level", "topic", "source_url", "retrieved_at", "status", "content_hash"]
MAGIC = {
    ".pdf": b"%PDF",
    ".docx": b"PK",
    ".xlsx": b"PK",
    ".png": b"\x89PNG",
    ".jpg": b"\xff\xd8",
}


def main() -> int:
    records = json.loads(MANIFEST.read_text())
    problems: list[str] = []
    roots = [REPO / "regions/national", BEIJING]
    disk = {str(p.relative_to(REPO)) for root in roots if root.exists()
            for p in root.rglob("*")
            if p.is_file() and not p.name.endswith(".meta.yaml") and p.name != ".gitkeep"}
    listed = {r["local_path"] for r in records}
    for extra in sorted(disk - listed):
        if extra.endswith(("README.md", "SOURCE.md", "official-index.md")):
            continue
        problems.append(f"未登记的仓库文件: {extra}")
    for missing in sorted(listed - disk):
        problems.append(f"manifest 记录但文件缺失: {missing}")

    for r in records:
        path = REPO / r["local_path"]
        if not path.exists():
            continue
        data = path.read_bytes()
        if r["file_type"] == "markdown":
            text = data.decode("utf-8")
            if not text.startswith("---\n"):
                problems.append(f"缺少 frontmatter: {r['local_path']}")
                continue
            end = text.find("\n---", 3)
            if end == -1:
                problems.append(f"frontmatter 未闭合: {r['local_path']}")
                continue
            fm = text[4:end + 1]
            try:
                meta = yaml.safe_load(fm) or {}
            except yaml.YAMLError as exc:
                problems.append(f"frontmatter 解析失败 {r['local_path']}: {exc}")
                continue
            for key in REQUIRED:
                if not meta.get(key):
                    problems.append(f"frontmatter 缺字段 {key}: {r['local_path']}")
            if len(text) < 300:
                problems.append(f"内容过短: {r['local_path']}")
        else:
            magic = MAGIC.get(path.suffix.lower())
            if magic and not data.startswith(magic):
                problems.append(f"文件类型与扩展名不符: {r['local_path']}")

    csv_rows = list(csv.DictReader((REPO / "indexes/documents.csv").open(encoding="utf-8")))
    if len(csv_rows) != len(records):
        problems.append(f"documents.csv 行数 {len(csv_rows)} != manifest {len(records)}")
    json_rows = json.loads((REPO / "indexes/documents.json").read_text())
    if len(json_rows) != len(records):
        problems.append(f"documents.json 行数 {len(json_rows)} != manifest {len(records)}")

    print(f"records={len(records)} csv={len(csv_rows)} json={len(json_rows)} disk_files={len(disk)}")
    for topic in sorted({r["topic"] for r in records}):
        n = len([r for r in records if r["topic"] == topic])
        print(f"  {topic}: {n}")
    if problems:
        print("\n问题:")
        for p in problems:
            print(" -", p)
        return 1
    print("\n校验通过：无异常")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
