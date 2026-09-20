# labor_lawyer

北京劳动人事争议仲裁公开资料归档项目。

本仓库以北京市劳动人事争议调解仲裁网上服务平台为起点，长期收集和整理中国大陆各省、自治区、直辖市以及地级市公开发布的劳动仲裁资料，包括：

- 劳动仲裁申请书、授权委托书、证据清单等模板
- 劳动人事争议典型案例
- 仲裁案件管辖规定和通知
- 仲裁机构名录和联系方式
- 劳动者、用人单位、代理人操作手册
- 地方法规、政策文件和要点说明

> 免责声明：本仓库仅归档公开资料，不构成法律意见。具体案件应以当地法律、政策、仲裁机构要求和专业法律意见为准。

## 北京资料入口

- 北京市劳动人事争议调解仲裁网上服务平台
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/index

- 北京市人力资源和社会保障局：劳动人事争议典型案例
  - https://rsj.beijing.gov.cn/bm/ztzl/dxal/index_1.html

- 劳动人事争议调解仲裁机构查询
  - https://banshi.beijing.gov.cn/zwfwapi/cycx/shbz/ldrszytjzcjg/query.html

- 北京市劳动人事争议仲裁申请政务服务入口
  - https://banshi.beijing.gov.cn/pubtask/task/1/110101000000/63fb2f78-f61a-434e-a834-ac398cd29417.html

- 北京市政府公开页：劳动人事争议仲裁案件管辖调整通知
  - https://www.beijing.gov.cn/zhengce/gfxwj/202207/t20220714_2771636.html

- 北京市政府公开页：2023年度十大劳动人事争议仲裁典型案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202312/t20231229_3521081.html

- 北京市政府公开页：2024年度十大劳动人事争议仲裁典型案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202412/t20241217_3967825.html

## 目录结构

```text
labor_lawyer/
├── README.md
├── CONTRIBUTING.md
├── SOURCES.yaml
├── CHANGELOG.md
├── regions/
│   ├── national/
│   ├── municipalities/
│   │   └── beijing/
│   │       ├── README.md
│   │       ├── official-index.md
│   │       ├── templates/
│   │       │   └── README.md
│   │       ├── cases/
│   │       │   └── README.md
│   │       ├── jurisdiction/
│   │       │   └── README.md
│   │       ├── institutions/
│   │       │   └── README.md
│   │       ├── manuals/
│   │       │   └── README.md
│   │       ├── regulations/
│   │       │   └── README.md
│   │       └── archive/
│   ├── provinces/
│   ├── autonomous-regions/
│   └── cities/
├── schemas/
│   └── document.schema.yaml
├── indexes/
│   ├── documents.csv
│   ├── documents.json
│   └── by-topic/
├── tools/
└── reports/
```

## 北京地区资料归档目标

北京地区的资料归档应按主题落到以下目录：

- `regions/municipalities/beijing/templates/`
  - 仲裁申请书、授权委托书、证据清单、办事须知等模板
- `regions/municipalities/beijing/cases/`
  - 年度典型案例、案例解读、案例专题
- `regions/municipalities/beijing/jurisdiction/`
  - 管辖规定、受理范围、通知和主管机关分工说明
- `regions/municipalities/beijing/institutions/`
  - 仲裁机构名录、办公地址、电话和时间
- `regions/municipalities/beijing/manuals/`
  - 劳动者、用人单位、代理人在网上办理时的操作手册
- `regions/municipalities/beijing/regulations/`
  - 地方规范性文件、政策解读、通知和要点说明
- `regions/municipalities/beijing/archive/`
  - 暂无法分类或原始打包材料

## 建议的归档规则

1. 优先保留官方原始文件，而不是仅保留扫描件或 OCR 文本。
2. 下载后保持原始文件名，并额外生成规范化文件名。
3. 记录来源页面、官方附件地址、发布时间、抓取时间和 SHA-256。
4. 若官方文件已更新或被废止，保留旧文件并标记 `superseded`。
5. 不构成法律意见；具体案件应以官方最新文件和专业法律意见为准。

## 北京官方入口索引（已核验为公开入口）

- 北京市劳动人事争议调解仲裁网上服务平台
  - https://fuwu.rsj.beijing.gov.cn/zhrs/api4/arbitration/html/home/index

- 北京市人力资源和社会保障局：劳动人事争议典型案例
  - https://rsj.beijing.gov.cn/bm/ztzl/dxal/index_1.html

- 北京市劳动人事争议调解仲裁机构查询
  - https://banshi.beijing.gov.cn/zwfwapi/cycx/shbz/ldrszytjzcjg/query.html

- 北京市劳动人事争议仲裁申请政务服务入口
  - https://banshi.beijing.gov.cn/pubtask/task/1/110101000000/63fb2f78-f61a-434e-a834-ac398cd29417.html

- 北京市政府公开页：关于调整劳动人事争议仲裁案件管辖的通知
  - https://www.beijing.gov.cn/zhengce/gfxwj/202207/t20220714_2771636.html

- 北京市政府公开页：2023年度十大劳动人事争议仲裁典型案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202312/t20231229_3521081.html

- 北京市政府公开页：2024年度十大劳动人事争议仲裁典型案例
  - https://www.beijing.gov.cn/ywdt/gzdt/202412/t20241217_3967825.html

## 工作方式

本项目目前先做结构和索引，后续每个省或城市都按以下方式扩展：

- `regions/{level}/{region}/README.md`
- `regions/{level}/{region}/official-index.md`
- `regions/{level}/{region}/templates/`
- `regions/{level}/{region}/cases/`
- `regions/{level}/{region}/jurisdiction/`
- `regions/{level}/{region}/institutions/`
- `regions/{level}/{region}/manuals/`
- `regions/{level}/{region}/regulations/`
- `regions/{level}/{region}/archive/`

## 面向后续扩展

后续会按行政区划逐步增加：

- 直辖市：北京、上海、天津、重庆
- 省份：广东、浙江、江苏、山东等
- 自治区：内蒙古、广西、新疆等
- 城市：深圳、广州、杭州、南京等

每个地区都会保留同样的资料主题结构，方便后续检索、添加索引和生成统计。

## 备注

这一版 README 仅用于记录：

- 目前的目录结构
- 官方入口
- 后续长期归档方向
- 北京地区的起点规划

如果你自己下载了北京资料，可以继续往 `regions/municipalities/beijing/` 相关目录中放置真实文件，并补充各文件的来源信息。
