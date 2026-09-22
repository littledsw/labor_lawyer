# Obsidian 使用约定（labor_lawyer）

本仓库可直接作为 Obsidian vault 打开：`~/workspace/projects/labor_lawyer`。
（Obsidian 1.13.7，已装于 `/Applications/Obsidian.app`，纯本地、无账号、不启用 Sync。）

## 一、目录分层（重要）

| 层 | 路径 | 谁写 | 能否手改 |
| --- | --- | --- | --- |
| **机器层（生成物）** | `indexes/**`、`regions/**/README.md`、`SOURCES.yaml` | 抓取流程 `tools/crawl/stage6_indexes.py` 等 | ❌ 不要手改，下次抓取会被覆盖 |
| **归档层（原件）** | `regions/**` 下的法规/案例/模板/统计原文件 | 抓取脚本 + 人工补档 | ⚠️ 可改，但改完要跑核验（`tools/crawl/verify.py`） |
| **人工层（笔记）** | 新增的案例要旨、法规摘录、办案笔记、双链 | 人工 / Agent | ✅ 随便改 |

约定：**在 Obsidian 里自由编辑的只有「人工层」**。生成物已在 Obsidian 中设为 Excluded files（见 `.obsidian/app.json` 的 `userIgnoreFilters`），以免误改。

## 二、已配置的 vault 设置

- 自动更新内部链接 **关闭**（`alwaysUpdateLinks: false`）——避免脚本/人工写入双链时被 Obsidian 改写。
- 显示所有文件类型 **开启**（`showUnsupportedFiles: true`）——`docx / pdf / xls` 原件在库里可见可直接打开。
- 删除进系统废纸篓（`trashOption: system`），不在仓库里生成 `.trash/`。
- 排除文件见 `userIgnoreFilters`（`indexes/` + 14 个生成的 `README.md`）。
- 未写入 `core-plugins.json` / `appearance.json`：由 Obsidian 自行生成默认值，本地状态不进 git（`.gitignore` 只放行 `app.json`）。

## 三、命令行为自动化预留

Obsidian 自带 CLI（`/Applications/Obsidian.app/Contents/MacOS/obsidian-cli`，需 1.12.7+ 安装器），
可在 **Settings → General → Command line interface** 打开并注册，之后可：

```shell
cd ~/workspace/projects/labor_lawyer
obsidian search query="经济补偿"            # 全库检索
obsidian search:context query="第四十七条"  # 带上下文
obsidian read file="中华人民共和国劳动合同法"
obsidian backlinks file="中华人民共和国劳动合同法"
obsidian properties                         # 列 frontmatter 属性
obsidian eval code="app.vault.getFiles().length"
```

前提：Obsidian 桌面端正在运行（CLI 是驱动 App，不是独立进程）。不启用也不影响其他工作流。

## 四、与检索方案的关系

Obsidian = 人机导航层（反链、图谱、frontmatter 表格、全文检索）；
Agent 检索仍走结构化路线：`indexes/documents.json`（含 region/topic/status/published_at/content_hash）
+ `indexes/by-topic/*.md` + `indexes/derived/cases-chunks.jsonl`。
向量 RAG 仅在「按事实模式找相似案例」时才有优势，且必须先做元数据过滤（排除已失效 / 非本地区），
详见 `indexes/derived/README.md` 与 workspace 的 `shared/policies/`。
