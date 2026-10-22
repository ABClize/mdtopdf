"""Long table content must wrap inside its cell in HTML and PDF."""

import math

import pypdfium2 as pdfium
import pytest
from playwright.sync_api import sync_playwright

from mdtopdf import markdown_to_html, markdown_to_pdf
from mdtopdf.core import browser


LONG_IDENTIFIER = "ReportIdentifier20261023" * 8
LONG_URL = "https://example.com/reports/" + "abcdefghij0123456789" * 8


@pytest.fixture(scope="module")
def table_page():
    with sync_playwright() as driver:
        executable, source = browser._resolve_executable(driver.chromium.executable_path)
        options = {"headless": True, "chromium_sandbox": True}
        if source == "playwright":
            options["channel"] = "chromium"
        else:
            options["executable_path"] = executable
        with driver.chromium.launch(**options) as renderer:
            yield renderer.new_page(viewport={"width": 1000, "height": 900})


@pytest.mark.parametrize("content", [
    "中文长说明用于检查单元格自动换行" * 20,
    "A long description with ordinary spaces. " * 20,
    LONG_IDENTIFIER,
    f"[{LONG_URL}]({LONG_URL})",
    f"`{LONG_IDENTIFIER}`",
    f"**{LONG_IDENTIFIER}**",
], ids=["chinese", "english", "identifier", "url", "inline-code", "strong"])
@pytest.mark.parametrize("media", ["screen", "print"])
@pytest.mark.parametrize("width_mm", [180, 100], ids=["a4-width", "narrow-width"])
def test_long_table_text_stays_inside_each_cell(table_page, content, media, width_mm):
    result = markdown_to_html(
        f"| ID | {content} | Status |\n| --- | --- | --- |\n| 1 | {content} | END-2026 |\n"
    )
    table_page.emulate_media(media=media)
    table_page.set_content(result.html)
    # Check normal and narrow printable widths in both HTML media modes.
    table_page.add_style_tag(content=f".document {{ width: {width_mm}mm; padding: 0; }}")
    geometry = table_page.evaluate("""() => {
        const overflows = [];
        for (const cell of document.querySelectorAll('th, td')) {
            const bounds = cell.getBoundingClientRect();
            const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                const range = document.createRange();
                range.selectNodeContents(walker.currentNode);
                for (const rect of range.getClientRects()) {
                    if (rect.left < bounds.left - 1 || rect.right > bounds.right + 1) {
                        overflows.push({text: walker.currentNode.textContent.slice(0, 50),
                                        cell: [bounds.left, bounds.right],
                                        textBounds: [rect.left, rect.right]});
                    }
                }
            }
        }
        const table = document.querySelector('table').getBoundingClientRect();
        const documentBounds = document.querySelector('.document').getBoundingClientRect();
        return {overflows, tableWidth: table.width, documentWidth: documentBounds.width};
    }""")
    assert geometry["tableWidth"] <= geometry["documentWidth"] + 1
    assert not geometry["overflows"], geometry["overflows"]


@pytest.mark.parametrize("media", ["screen", "print"])
@pytest.mark.parametrize("fixed_override", [False, True], ids=["adaptive", "explicit-fixed"])
def test_table_width_follows_content_without_crushing_short_columns(table_page, media, fixed_override):
    source = (
        "| 编号 | 说明 | 状态 |\n| :--- | :--- | :--- |\n"
        f"| IT-001 | {'项目详细说明用于验证列宽分配' * 80} | 已完成 |\n"
        f"| IT-002 | {LONG_IDENTIFIER * 8} | Processing |\n"
    )
    result = markdown_to_html(
        source, custom_css="table { table-layout: fixed; }" if fixed_override else None
    )
    table_page.emulate_media(media=media)
    table_page.set_content(result.html)
    table_page.add_style_tag(content=".document { width: 180mm; padding: 0; }")
    geometry = table_page.locator("table").evaluate("""table => ({
        columns: [...table.rows[0].cells].map(cell => cell.getBoundingClientRect().width),
        shortCellLines: [...table.rows].flatMap(row => [row.cells[0], row.cells[2]]).map(cell => {
            const range = document.createRange();
            range.selectNodeContents(cell);
            return range.getClientRects().length;
        }),
    })""")
    first, description, status = geometry["columns"]
    if fixed_override:
        assert max(geometry["columns"]) - min(geometry["columns"]) < 2
    else:
        assert description > 2 * max(first, status), geometry
    assert all(lines == 1 for lines in geometry["shortCellLines"]), geometry


def test_short_table_headers_remain_readable_with_long_notes(table_page):
    source = (
        "| Metric | Current | Target | Notes |\n| --- | ---: | ---: | --- |\n"
        "| Page count | 12 | 12 | Numeric columns use Markdown alignment markers. |\n"
        "| Average paragraph length | 64 | 80 | Regular text columns should wrap naturally. |\n"
        "| Render status | Done | Done | **Key result** |\n"
        "| Link example | [site](https://example.com) | this section | Check links inside tables. |\n"
    )
    table_page.emulate_media(media="print")
    table_page.set_content(markdown_to_html(source).html)
    table_page.add_style_tag(content=".document { width: 180mm; padding: 0; }")
    headers = table_page.locator("th").evaluate_all("""cells => cells.map(cell => {
        const range = document.createRange();
        range.selectNodeContents(cell);
        return {text: cell.textContent, lines: range.getClientRects().length};
    })""")
    assert all(header["lines"] == 1 for header in headers), headers


def test_long_table_content_is_complete_and_visible_in_pdf(tmp_path):
    code = "report_identifier_20261023_" * 5
    chinese = "中文长说明与数字2026混排" * 8
    source = (
        "| ID | Description | Status |\n| ---: | :--- | :---: |\n"
        f"| 1 | {LONG_IDENTIFIER} | END101 |\n"
        f"| 2 | [{LONG_URL}]({LONG_URL}) | END202 |\n"
        f"| 3 | `{code}` | END303 |\n"
        f"| 4 | {chinese} | END404 |\n"
    )
    target = tmp_path / "long-table.pdf"
    result = markdown_to_pdf(source, target, strict=True, include_page_header=False)
    assert result["ok"] and not result["warnings"]
    all_text = []
    visible_digits = 0
    with pdfium.PdfDocument(target) as document:
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            bitmap = page.render(scale=2)
            try:
                image = bitmap.to_pil().copy()
                image.save(tmp_path / f"long-table-{index + 1}.png")
                all_text.append(text_page.get_text_range())
                sx, sy = image.width / page.get_width(), image.height / page.get_height()
                margin = 15 * 72 / 25.4
                for char_index in range(text_page.count_chars()):
                    char = text_page.get_text_range(char_index, 1)
                    if not char or char.isspace():
                        continue
                    left, bottom, right, top = text_page.get_charbox(char_index)
                    assert left >= margin - 1 and right <= page.get_width() - margin + 1, (
                        index, char, left, right
                    )
                    if char in "0123456789":
                        crop = image.crop((
                            math.floor(left * sx), math.floor((page.get_height() - top) * sy),
                            math.ceil(right * sx), math.ceil((page.get_height() - bottom) * sy),
                        )).convert("L")
                        assert sum(crop.histogram()[:200]) >= 3, (index, char, left, top)
                        visible_digits += 1
            finally:
                bitmap.close()
                text_page.close()
                page.close()
    compact = "".join("".join(all_text).split())
    for expected in (LONG_IDENTIFIER, LONG_URL, code, chinese, "END101", "END202", "END303", "END404"):
        assert expected in compact, f"Missing table content: {expected!r}"
    assert visible_digits >= 100
