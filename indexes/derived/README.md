# 派生数据（indexes/derived）

由 `tools/crawl/extract_cases.py` 从归档原文脚本化生成，**不含 LLM 输出**，可随时重跑覆盖。

| 文件 | 内容 |
| --- | --- |
| `cases-meta.json` | 每篇案例的元数据：章节结构、字数、法条引用、主题标签 |
| `cases-chunks.jsonl` | 年度合集中的单个案例切片（每行一条，含正文、来源 URL、父文件） |
| `cases-citations.md` | 法条引用频次与对应案例清单 |
| `cases-topics.md` | 主题标签统计与对应案例清单 |

再生成：`cd tools/crawl && LABOR_LAWYER_REPO=<repo> python extract_cases.py`

说明：切片一律保留 `parent` 与 `source_url`，检索命中后可回溯到官方原文；正式用于 RAG 前建议先跑 `cases-meta.json` 检查章节完整度。
