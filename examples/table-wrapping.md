# 表格长文本自动换行

表格根据各列内容自动分配宽度：短标签列收窄，长说明列获得更多空间，行高随内容增长。普通文字优先在自然断点换行；长编号、URL 等连续文本超出列宽时也能断行，无需手动插入 `<br>`。

| 类型 | 长内容示例 | 检查结果 |
| :--- | :--- | :---: |
| 中文说明 | 这是一段故意放在同一个单元格里的长说明，用于验证中文内容能够根据列宽自然换行，同时保留数字 2026、日期 2026-10-23 和编号 IT-001。 | 完整显示 |
| 英文说明 | A table cell can contain a detailed explanation with several sentences. Normal words wrap at spaces while the row grows to fit the complete text. | 完整显示 |
| 连续编号 | ReportIdentifier20261023ReportIdentifier20261023ReportIdentifier20261023ReportIdentifier20261023ReportIdentifier20261023 | 自动断行 |
| 长链接 | [https://example.com/reports/abcdefghij0123456789abcdefghij0123456789abcdefghij0123456789abcdefghij0123456789](https://example.com/reports/abcdefghij0123456789abcdefghij0123456789abcdefghij0123456789abcdefghij0123456789) | 链接保留 |
| 行内代码 | `report_identifier_20261023_report_identifier_20261023_report_identifier_20261023_report_identifier_20261023` | 自动断行 |

END-OF-TABLE：最后一行后的正文也应完整显示。
