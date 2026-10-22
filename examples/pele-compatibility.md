## 1. 文档交付流程

Pele 图表兼容与 PDF 视觉检查：中文、ASCII 数字、日期、版本号和工单编号应清晰可见。

| 工单 | 基准日期 | 版本 | 输出 |
| --- | --- | --- | --- |
| IT-001 | 2026-06-22 | v0.2.2 | HTML + PDF |

> [!note] 审阅基准
> 检查节点文字、箭头、图例、公式和分页；图表颜色应与正文蓝灰主题协调。

```mermaid
---
title: IT-001 文档交付
---
flowchart LR
    A[收集 Markdown] --> B[审阅 v0.2.2]:::review
    B --> C[生成 PDF]
    C --> D[归档 2026-06-22]
    classDef review fill:#eef2f6,stroke:#173b5c,color:#172033
```

```mermaid
sequenceDiagram
    participant U as 作者
    participant C as mdtopdf CLI
    participant P as Pele
    participant B as Chromium
    U->>C: 转换 IT-001.md
    C->>P: 渲染 Mermaid 代码块
    P-->>C: 返回 SVG
    C->>B: 排版 v0.2.2 报告
    B-->>U: 2026-06-22.pdf
```

## 2. 报告模型与状态

IT-001 · 2026-06-22 · v0.2.2。检查类成员、关系符号和状态转换标签。

```mermaid
classDiagram
    class Report {
        +String ticketId
        +String version
        +renderPDF()
    }
    class Diagram {
        +String source
        +renderSVG()
    }
    Report "1" *-- "2" Diagram : 包含图表
```

```mermaid
stateDiagram-v2
    direction LR
    state "草稿 IT-001" as Draft
    state "审阅 v0.2.2" as Review
    state "已归档" as Archived
    [*] --> Draft
    Draft --> Review: 提交
    Review --> Archived: 2026-06-22
    Archived --> [*]
```

```mermaid
erDiagram
    REPORT ||--o{ DIAGRAM : includes
    REPORT {
        string ticket_id PK
        string version
    }
    DIAGRAM {
        int diagram_id PK
        string source
    }
```

## 3. 交付进度与计划

IT-001 · v0.2.2。图例数量、百分比和日期轴应可读，彩色区域应保留足够对比度。

```mermaid
pie showData
    title 报告状态 2026-06-22
    "已通过 8 份" : 8
    "待审阅 3 份" : 3
    "待修订 1 份" : 1
```

```mermaid
gantt
    title v0.2.2 交付计划
    dateFormat YYYY-MM-DD
    axisFormat %m-%d
    section IT-001
    整理资料 :done, collect, 2026-06-22, 2d
    图表审阅 :active, review, after collect, 2d
    PDF 验收 :verify, after review, 1d
```

## 4. 检查范围与版本记录

IT-001 · 2026-06-22 · v0.2.2。检查分支层级、中文换行与时间线对齐。

```mermaid
mindmap
    root((PDF 验收))
        字体
            中文标签
            ASCII 0123456789
        图表
            节点与连线
            图例与公式
        交付
            IT-001
            v0.2.2
```

```mermaid
timeline
    title IT-001 验收记录
    2026-06-22 : v0.2.2 草稿
    2026-06-23 : 图表审阅
    2026-06-24 : PDF 验收
```

## 5. 数据坐标与趋势

IT-001 · 2026-06-22 · v0.2.2。检查坐标刻度、柱高和趋势线，避免图例或标签被截断。

```mermaid
xychart-beta
    title "每日通过数"
    x-axis ["06-22", "06-23", "06-24", "06-25"]
    y-axis "通过份数" 0 --> 12
    bar [3, 5, 8, 11]
    line [3, 5, 8, 11]
```

## 6. 桑基图与数据流向

检查流向宽度、数量和标签。内置 Pele 1.8.0 的桑基图节点名须使用 ASCII；其他页展示中文标签。

```mermaid
sankey-beta
Source,Review,12
Review,PDF accepted,9
Review,Revision,3
```

## 7. 版本分支、公式与嵌套代码块

IT-001 · 2026-06-22 · v0.2.2。检查分支标记、数学符号和引用块内的 `mmd` 别名。

```mermaid
gitGraph
    commit id: "草稿 IT-001"
    branch review
    checkout review
    commit id: "图表审阅"
    checkout main
    merge review tag: "v0.2.2"
    commit id: "2026-06-22"
```

```mermaid
flowchart LR
    A["$$n = 12$$"] --> B["$$p = \frac{9}{12} = 75\%$$"]
    B --> C[通过率]
```

> 引用中的交付检查：保留原有 `mmd` 代码块用法。
>
> ```mmd
> graph LR
>     A[工单 IT-001] --> B[校验 v0.2.2] --> C[交付 PDF]
> ```
