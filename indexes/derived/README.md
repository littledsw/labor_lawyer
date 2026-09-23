# 派生数据（indexes/derived）

由 `tools/crawl/extract_cases.py`（脚本化，零 LLM 成本）与 `tools/crawl/merge_llm_extract.py`（合并模型抽取结果）生成，可随时重跑覆盖。

## 脚本派生（无 LLM）

| 文件 | 内容 |
| --- | --- |
| `cases-meta.json` | 逐个文件的元数据：`kind`（年度合集 / 单篇案例 / 发布动态）、章节结构、字数、法条引用、主题标签 |
| `cases-chunks.jsonl` | 语义单元切片（每行一条，含正文、来源 URL、父文件）：合集按案例锚点切、单篇案例整篇一片 |
| `cases-citations.md` | 法条引用频次与对应案例清单 |
| `cases-topics.md` | 主题标签统计与对应案例清单 |

## 模型抽取（方案 A，供 RAG 检索）

| 文件 | 内容 |
| --- | --- |
| `llm-extract/<发布日期>.json` | 年度合集批次（`<合集发布日期>.json`）与单篇案例批次（`singles-NN.json`）的原始抽取结果 |
| `cases-structured.json` | 合并后的结构化记录：争议焦点、仲裁请求、处理结果、裁决要旨、法条依据、金额口径、关键词、主体类型 |
| `cases-structured.md` | 上述记录的人工可读版本 |

`legal_basis_check` 字段记录每条法条引用的回文核验等级：`exact` 与原文逐字一致、`short-form` 系简称写法、`anaphoric` 为原文承接上文的写法、`manual-confirmed` 为人工比对确认。

`merge_llm_extract.py` 要求 `cases-chunks.jsonl` 的**每一条切片都被抽取覆盖**，缺一条即报错退出。

## 再生成

```bash
cd tools/crawl
LABOR_LAWYER_REPO=<repo> python extract_cases.py        # 脚本派生
LABOR_LAWYER_REPO=<repo> python merge_llm_extract.py    # 合并 + 校验模型抽取
```

## 使用注意

- 切片一律保留 `parent` 与 `source_url`，检索命中后可回溯到官方原文。
- 模型抽取的争议焦点/要旨属归纳性内容；法条依据保留原文写法并经回文核验，但正式用于出具意见或文书前仍需对照官方原文复核。
