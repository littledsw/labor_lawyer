# 北京劳动人事争议仲裁公开资料索引

## 1. 官方入口

- 北京市劳动人事争议调解仲裁网上服务平台（首页/常用模板/操作手册入口）
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/index

- 北京市人力资源和社会保障局专题页：劳动人事争议典型案例
  - https://rsj.beijing.gov.cn/bm/ztzl/dxal/index_1.html

- 北京市劳动人事争议调解仲裁机构查询
  - https://banshi.beijing.gov.cn/zwfwapi/cycx/shbz/ldrszytjzcjg/query.html

- 北京市劳动人事争议仲裁申请政务服务入口
  - https://banshi.beijing.gov.cn/pubtask/task/1/110101000000/63fb2f78-f61a-434e-a834-ac398cd29417.html

- 北京市政府公开页：2022年管辖调整通知
  - https://www.beijing.gov.cn/zhengce/gfxwj/202207/t20220714_2771636.html

- 北京市政府公开页：2023 年度十大案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202312/t20231229_3521081.html

- 北京市政府公开页：2024 年度十大案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202412/t20241217_3967825.html

## 2. 资料分区说明

- 模板与文书：`templates/`
- 典型案例：`cases/`
- 管辖规定：`jurisdiction/`
- 机构名录：`institutions/`
- 操作手册：`manuals/`
- 办事指南与在线须知：`guidance/`
- 地方法规与政策文件：`regulations/`
- 总索引：`indexes/documents.csv`、`indexes/documents.json`、`indexes/by-topic/`

## 3. 当前状态

- 已完成北京地区第一轮批量抓取，资料落盘情况见各主题目录 `README.md` 的「已归档资料」小节与 `indexes/`。
- 可直接下载的官方附件（文书模板 docx、操作手册 PDF、管辖通知 PDF、办事指南表格样例）均已归档原始文件，并生成同名 `.meta.yaml` 记录来源页、下载地址、发布时间、抓取时间与 SHA-256。
- 无法下载的页面信息（典型案例、政策文件、办事指南、在线须知）已抓取关键内容为 Markdown。
- 已知失效入口：`zwfw.beijing.gov.cn` 域名当前无法解析，原「东城区政务服务中心仲裁指南」链接失效，东城区内容改以政务服务事项办事指南页面归档。

## 4. 已核验的直接下载地址

- 文书模板（北京市人社局网上服务平台，公开直链）
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/劳动人事争议调解申请书.docx
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/授权委托书（申请调解）.docx
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/法定代表人身份证明书（通用）.docx
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/劳动人事争议仲裁申请书.docx
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/授权委托书（申请仲裁）.docx
  - 列表页：https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/newsList?items=10

- 操作手册（PDF，公开直链）
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/劳动者操作手册.pdf
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/用人单位操作手册.pdf
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/public/doc/代理人操作手册.pdf

- 仲裁机构名录（公开查询接口）
  - `GET https://banshi.beijing.gov.cn/zwfwapi/bjmap/query?page=0&size=50&categoryId=ldrszytjzcjg&text=`

- 办事指南（政务服务事项页面，含受理条件、申请材料、流程与依据）
  - 市级 https://banshi.beijing.gov.cn/pubtask/task/1/110000000000/1f742ee9-db1e-46f0-b009-0a71220d2f08.html
  - 各区页面见 `guidance/guides/` 各文件 frontmatter 中的 `source_url`

- 管辖规定原件 PDF（首都之窗规范性文件附件）
  - https://www.beijing.gov.cn/zhengce/gfxwj/202207/W020220802491095522860.pdf

## 5. 后续作业顺序

1. 补齐尚未定位到公开 URL 的区级办事指南（石景山、门头沟、房山、顺义、大兴、北京经济技术开发区）。
2. 按年度翻查 `rsj.beijing.gov.cn` 政策文件/通知公告栏目，持续补充仲裁相关规范性文件与被废止文件的 `superseded` 标记。
3. 归档各区仲裁院发布的送达公告、开庭公告等动态信息（可选，需单独评估敏感性）。
4. 补充北京地区裁审口径类文件（法院与仲裁委联合解答、会议纪要）的历年版本。
5. 视需要扩展 `regions/national/`（劳动法、劳动合同法、劳动争议调解仲裁法、办案规则等）。

## 6. 重要说明

本索引仅记录官方公开入口与已归档资料，不构成法律意见；具体案件仍以官方最新文件、法律法规和专业法律意见为准。
