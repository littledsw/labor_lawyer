# 公开资料抓取流程（tools/crawl）

本目录是 `regions/national/`（国家层面）与 `regions/municipalities/beijing/`（北京市）资料的抓取与索引生成流程，用于复现、增量更新与扩展到其他地区。

## 依赖

- Python 3.11+
- 第三方库：`markdownify`、`beautifulsoup4`、`lxml`、`pyyaml`（日历参数另需 `cnlunar`、`lunardate`）

```bash
# 推荐用 uv 临时环境
uv run --with markdownify --with beautifulsoup4 --with lxml --with pyyaml --with xlrd python stage1_templates_manuals.py
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
| 7 | `stage9_calendar.py` | 计算参数（日历）：抓取 2016—2026 各年国办节假日安排通知，派生法定节假日/休息日/调休上班日 |
| 8 | `stage10_beijing_params.py` | 计算参数（北京）：社平工资三组口径、最低工资标准与封顶口径决定，生成 `statistics/parameters.yaml` |
| 10 | `stage11_injury_params.py` | 计算参数（工伤）：归档京人社工发〔2011〕384号原文并写入工伤待遇对照表与社平口径待确认项 |
| 11 | `stage13_national_income.py` | 国家层面参数：抓取 2013—2025 年国家统计局统计公报，归档「居民收入消费」小节并提取全国城镇居民人均可支配收入（工亡补助金基数） |
| 11b | `stage15_beijing_yearbook.py` | 从北京统计年鉴在线版（hgk.tjj.beijing.gov.cn）取「全市法人单位从业人员年末人数及工资情况」表，归档 xls 原件并解析出封顶基数序列（2017—2023） |
| 11c | `stage16_beijing_2024_estimate.py` | 年鉴2025 已无「法人单位」表（3-13 改为城镇非私营/私营两行口径），用两行工资总额÷人数之和估算 2024 年度值，并用 2023 年官方值校验偏差；结果标记 `estimate-not-official` |
| 12 | `stage14_cap_basis_evidence.py` | 归档「经济补偿封顶基数」口径链条证据（人社局通告 + 统计局答复）并更新参数表缺口与取数路径 |
| 12b | `stage17_working_hours_regs.py` | 计算参数（工时与加班）：归档折算依据（人社部发〔2025〕2号，及其废止的劳社部发〔2008〕3号）、假期加班工资复函（人社厅函〔2020〕135号）与《北京市工资支付规定》（市政府令第142号） |
| 12c | `stage18_beijing_social_insurance.py` | 计算参数（社保赔偿）：归档《北京市失业保险规定》（赔偿责任第31条、计发月数第17条）、京人社评发〔2024〕17号《北京市失业保险金申领发放实施办法（试行）》（第21条单位承担失业待遇损失）与京人社医发〔2011〕334号（生育津贴计发口径） |
| — | `stage12_promote_wage.py` | 参数核实工具：仅在官方页面确能检索到数值时，把候选值提升为已验证参数（需手动指定 `--year --annual --url`） |
| 9 | `stage6_indexes.py` | 由 `manifest.json` 生成 `indexes/`、各主题 README 清单、`SOURCES.yaml`、`CHANGELOG.md` |
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

## 计算参数（statistics）

| 路径 | 内容 |
| --- | --- |
| `regions/national/statistics/calendar/notices/` | 国办年度节假日安排通知原文（2016—2026） |
| `regions/national/statistics/calendar/calendar-<年>.json` | 逐日分类：`statutory_holiday`（3 倍工资日）/ `rest_day`（2 倍或补休）/ `makeup_workday`（调休上班）/ `weekend` / `workday` |
| `regions/national/statistics/calendar/calendar-index.json` | 各年度法定节假日天数、调休上班日与校验问题汇总 |
| `regions/municipalities/beijing/statistics/parameters.yaml` | 北京工资/最低工资参数台账（`series` 时间序列 + `decisions` 口径 + `gaps` 缺口） |
| `regions/municipalities/beijing/statistics/sources/` | 参数来源页面原文 |

口径要点：法定节假日按《全国年节及纪念日放假办法》确定，农历/节气日期由 `cnlunar` 计算，并与当年国办通知交叉校验（法定节假日必须落在通知的放假区间内）；2020 年另计春节假期延长。北京经济补偿三倍封顶基数自 2019-08-16 起按「法人单位从业人员平均工资」，而不是「全口径城镇单位就业人员平均工资」（后者官方注明仅用于社保基数）。

工时与加班折算口径：日/小时工资按**月计薪天数 21.75 天**（人社部发〔2025〕2号第二条）折算，该值不受法定节假日由 11 天增至 13 天影响；**月工作日**已由 20.83 天（劳社部发〔2008〕3号，已废止）调整为 **20.67 天**，仅用于制度工作时间核算，不用于工资折算。加班倍数与基数：劳动法第 44 条、人社厅函〔2020〕135号（假期内分段）、北京《北京市工资支付规定》第 14/16/17/44 条。日历中 `makeup_workday`（调休上班日/补班日）的加班费定性**无官方原文支撑**，计算侧按工作日处理并输出待核实提示，详见根目录 `CHANGELOG.md` 的「加班与工时口径补档」。

## 归档约定

- Markdown：正文 + YAML frontmatter（`title`、`region`、`level`、`topic`、`authority`、`published_at`、`source_url`、`retrieved_at`、`status`、`content_hash`、`local_path`、`notes`）。
- 二进制附件：与原文件同名的 `<文件名>.meta.yaml`，并保留 `original_filename` 记录官方原始文件名。
- `status` 取值：`active`（现行有效）、`superseded`（已被新版本取代，需保留旧文件）、`unreachable`（来源不可访问）。
- 重新执行脚本会按 `local_path` 覆盖同名记录，属于幂等更新；官方网站改版导致选择器失效时需先修正抽取逻辑。
## 抓 JS 渲染的页面（站内检索、政民互动答复）

政务网站的智能云搜索、数据表等由 JS 动态渲染，纯 HTTP 抓取只能拿到空壳。用自带的 headless 浏览器：

```bash
python browser_fetch.py "https://tjj.beijing.gov.cn/so/s?qt=<URL编码关键词>" --wait 8 --grep 平均工资
python browser_fetch.py "<页面URL>" --json /tmp/page.json     # 含正文/链接/表单
```

```python
from browser_fetch import render
page = render(url, wait=8)      # page["text"] / page["links"] / page["html"]
```

无需任何配置（自建 headless Chrome + CDP，依赖 `websocket-client`）。注意：分页与筛选是 JS 行为，
翻页后需重新 render；`javascript:;` 的链接不能直接抓取。

## 参数核实（candidates_unverified → entries）

`parameters.yaml` 中 `candidates_unverified` 的数值来自二手渠道（律所/媒体转述），**禁止直接用于计算**。取得官方页面后用：

```bash
python stage12_promote_wage.py --year 2023 --annual 188413 \
    --url "https://tjj.beijing.gov.cn/<官方页面>" --pubdate 2024-06-19
```

脚本会抓取该页面并校验数值确实出现在页面文本中（含千分位写法），校验通过才写入 `entries` 并记录
`source_url`、抓取时间与页面 sha256；未命中（exit 2）或页面不可达（exit 3）时不写入任何内容。

- 地区通过 `region` 参数区分（`national`、`municipalities/beijing`），索引与主题 README 由 `stage6_indexes.py` 按地区自动生成。

## 合规要求

只抓取公开页面与公开直链，不绕过登录、验证码、访问控制或技术限制；不抓取个人隐私或客户材料数据。所有归档文件均保留来源 URL 与 SHA-256，便于核验与追溯。
