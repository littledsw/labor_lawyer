# 北京市劳动人事争议仲裁资料

来源入口：<https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/index>

本目录保存北京市人力资源和社会保障局等官方渠道公开的劳动人事争议仲裁资料。每份资料均记录官方来源页面、附件地址、发布日期、抓取日期和 SHA-256 校验值：

- Markdown 文档：写在文件头部的 YAML frontmatter 中。
- 二进制附件（docx / pdf / xlsx）：写在与文件同名的 `<文件名>.meta.yaml` 中，并汇总进 `indexes/`。

## 目录与已归档内容

| 目录 | 内容 | 入口说明 |
| --- | --- | --- |
| `templates/` | 文书模板（仲裁申请书、调解申请书、授权委托书、法定代表人身份证明书） | `templates/README.md` |
| `manuals/` | 劳动者 / 用人单位 / 代理人操作手册（PDF） | `manuals/README.md` |
| `guidance/` | 办事指南（市级 + 区级政务服务事项）、平台在线申请须知 | `guidance/README.md` |
| `cases/` | 北京市人社局典型案例专题全部文章与年度十大案例 | `cases/README.md` |
| `jurisdiction/` | 仲裁管辖规定（含官方 PDF 原件） | `jurisdiction/README.md` |
| `institutions/` | 仲裁机构名录（官方查询接口数据与整理表） | `institutions/README.md` |
| `regulations/` | 地方规范性文件、裁审口径解答、政策解读 | `regulations/README.md` |
| `archive/` | 暂无法分类的原始材料 | — |

全量清单见仓库根目录 `indexes/documents.csv`（同名 `documents.json` 为 JSON 版本，`indexes/by-topic/` 为主题视图）。抓取与核验结论见 `official-index.md`。

> 免责声明：本目录仅归档公开资料，不构成法律意见。文件可能因政策更新而失效，使用前请以官方最新版本为准。
