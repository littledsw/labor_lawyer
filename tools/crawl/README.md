# 公开资料抓取流程（tools/crawl）

本目录是 `regions/national/`（国家层面）与 `regions/municipalities/beijing/`（北京市）资料的抓取与索引生成流程，用于复现、增量更新与扩展到其他地区。

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
| `LABOR_LAWYER_REPO` | 当前工作目录 | 仓库根目录，资料写入 `<repo>/regions/...` |
| `LABOR_LAWYER_CACHE` | `<repo>/.cache/labor_lawyer_crawl` | 页面缓存与 `manifest.json`（元数据累积文件，已 gitignore） |

## 执行顺序

| 步骤 | 脚本 | 作用 |
| --- | --- | --- |
| 1 | `stage1_templates_manuals.py` | 北京：下载网上服务平台「常用模板下载」docx 与「操作手册」PDF |
| 2 | `stage2_institutions.py` | 北京：通过政务服务网公开查询接口抓取仲裁机构名录，生成 JSON 与 Markdown |
| 3 | `stage3_cases.py` | 北京：抓取人社局「劳动人事争议典型案例」专题全部文章并转 Markdown |
| 4 | `stage4_regs.py` | 北京：归档管辖规定、裁审口径解答、规范性文件与政策解读（含官方附件） |
| 4b | `stage4b_cases_gov.py` | 北京：归档首都之窗的年度十大案例发布动态页及其官方附件 |
| 5 | `stage5_guidance.py` | 北京：抓取市级/区级政务服务事项办事指南与平台在线申请须知（含表格样例附件） |
| 6 | `stage7_national.py` | 国家层面：法律、行政法规、司法解释、部门规章（含页面附带的 DOCX/PDF 原件） |
| 7 | `stage6_indexes.py` | 由 `manifest.json` 生成 `indexes/`、各主题 README 清单、`SOURCES.yaml`、`CHANGELOG.md` |
| — | `verify.py` | 校验 frontmatter 完整性、附件类型、索引与实际文件一致性 |
| — | `extract_cases.py` | 派生抽取：法条引用、主题标签、年度合集切片 → `indexes/derived/`（纯脚本，无 LLM 成本） |
| — | `merge_llm_extract.py` | 合并 `indexes/derived/llm-extract/*.json` 的模型抽取结果并做回文核验，产出 `cases-structured.json/md` |

```bash
cd tools/crawl
export LABOR_LAWYER_REPO=/path/to/labor_lawyer
./run_all.sh          # 或按上表逐个执行
```

## 站点适配要点

- **人社部（mohrss.gov.cn）**：启用 EO_Bot 反爬挑战，首次请求返回一段设置 Cookie 的脚本；`common.solve_eo_bot()` 按公开挑战逻辑解出 `__tst_status` / `EO_Bot_Ssid` 后重试，不绕过登录或访问控制。法律/行政法规/规章栏目列表分页为 `index.html`、`index_1.html`…
- **政务服务网办事指南（banshi.beijing.gov.cn）**：正文与申请材料、流程、依据等结构化数据以 `var material = [...]` / `var process = [...]` 内联 JSON 形式嵌在页面中，直接解析；附件下载地址形如 `/pubtask/download/<DOC_ID>.<EXT>`。
- **典型案例专题（rsj.beijing.gov.cn）**：列表分页为 `index.html`、`index_1.html`…，正文在 `div.view`。
- **司法解释**：最高法官网（`court.gov.cn`）或最高人民法院公报（`gongbao.court.gov.cn`）。
- 抓取失败会打印 `FAIL` / `ATT FAIL`，可直接重跑；页面已缓存（`LABOR_LAWYER_CACHE`），重跑不会重复请求站点。

## 归档约定

- Markdown：正文 + YAML frontmatter（`title`、`region`、`level`、`topic`、`authority`、`published_at`、`source_url`、`retrieved_at`、`status`、`content_hash`、`local_path`、`notes`）。
- 二进制附件：与原文件同名的 `<文件名>.meta.yaml`，并保留 `original_filename` 记录官方原始文件名。
- `status` 取值：`active`（现行有效）、`superseded`（已被新版本取代，需保留旧文件）、`unreachable`（来源不可访问）。
- 重新执行脚本会按 `local_path` 覆盖同名记录，属于幂等更新；官方网站改版导致选择器失效时需先修正抽取逻辑。
- 地区通过 `region` 参数区分（`national`、`municipalities/beijing`），索引与主题 README 由 `stage6_indexes.py` 按地区自动生成。

## 合规要求

只抓取公开页面与公开直链，不绕过登录、验证码、访问控制或技术限制；不抓取个人隐私或客户材料数据。所有归档文件均保留来源 URL 与 SHA-256，便于核验与追溯。
