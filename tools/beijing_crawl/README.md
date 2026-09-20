# 北京资料抓取流程（tools/beijing_crawl）

本目录是 `regions/municipalities/beijing/` 下资料的抓取与索引生成流程，用于复现、增量更新与扩展到其他地区。

## 依赖

- Python 3.11+
- 第三方库：`markdownify`、`beautifulsoup4`、`lxml`、`pyyaml`

```bash
# 推荐用 uv 临时环境
uv run --with markdownify --with beautifulsoup4 --with lxml --with pyyaml python stage1_templates_manuals.py
# 或使用虚拟环境
python -m venv .venv && . .venv/bin/activate && pip install markdownify beautifulsoup4 lxml pyyaml
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LABOR_LAWYER_REPO` | 当前工作目录 | 仓库根目录，资料写入 `<repo>/regions/municipalities/beijing/` |
| `LABOR_LAWYER_CACHE` | `<repo>/.cache/labor_lawyer_crawl` | 页面缓存与 `manifest.json`（元数据累积文件，已 gitignore） |

## 执行顺序

| 步骤 | 脚本 | 作用 |
| --- | --- | --- |
| 1 | `stage1_templates_manuals.py` | 下载网上服务平台「常用模板下载」docx 与「操作手册」PDF |
| 2 | `stage2_institutions.py` | 通过政务服务网公开查询接口抓取仲裁机构名录，生成 JSON 与 Markdown |
| 3 | `stage3_cases.py` | 抓取北京市人社局「劳动人事争议典型案例」专题全部文章并转 Markdown |
| 4 | `stage4_regs.py` | 归档管辖规定、裁审口径解答、规范性文件与政策解读（含官方附件） |
| 5 | `stage5_guidance.py` | 抓取市级/区级政务服务事项办事指南与平台在线申请须知（含表格样例附件） |
| 6 | `stage6_indexes.py` | 由 `manifest.json` 生成 `indexes/`、主题 README 清单、`SOURCES.yaml`、`CHANGELOG.md` |

```bash
cd tools/beijing_crawl
export LABOR_LAWYER_REPO=/path/to/labor_lawyer
python stage1_templates_manuals.py
python stage2_institutions.py
python stage3_cases.py
python stage4_regs.py
python stage5_guidance.py
python stage6_indexes.py
```

## 归档约定

- Markdown：正文 + YAML frontmatter（`title`、`region`、`level`、`topic`、`authority`、`published_at`、`source_url`、`retrieved_at`、`status`、`content_hash`、`local_path`、`notes`）。
- 二进制附件：与原文件同名的 `<文件名>.meta.yaml`，并保留 `original_filename` 记录官方原始文件名。
- `status` 取值：`active`（现行有效）、`superseded`（已被新版本取代，需保留旧文件）、`unreachable`（来源不可访问）。
- 重新执行脚本会按 `local_path` 覆盖同名记录，属于幂等更新；官方网站改版导致选择器失效时需先修正抽取逻辑。

## 合规要求

只抓取公开页面与公开直链，不绕过登录、验证码、访问控制或技术限制；不抓取个人隐私或客户材料数据。所有归档文件均保留来源 URL 与 SHA-256，便于核验与追溯。
