"""Real PDF layout and glyph checks for complex Pele diagrams.

Artifacts are kept under pytest's tmp_path so the existing CI upload includes
the PDFs and their PDFium renders on every supported platform.
"""

import math

import pypdfium2 as pdfium
import pytest

from mdtopdf import markdown_to_pdf


def _rasterize(page, target):
    bitmap = page.render(scale=3)
    try:
        image = bitmap.to_pil().copy()
    finally:
        bitmap.close()
    image.save(target)
    return image


def _assert_labels_visible(page, image, labels, *, margins=(15, 15), light=False, minimum_capital_height=0):
    """Check actual label ink and page containment, without a font-specific golden."""
    text_page = page.get_textpage()
    try:
        text = text_page.get_text_range()
        scale_x = image.width / page.get_width()
        scale_y = image.height / page.get_height()
        left_limit = margins[0] * 72 / 25.4
        right_limit = page.get_width() - margins[1] * 72 / 25.4
        for label in labels:
            offset = text.find(label)
            assert offset >= 0, f"Missing diagram label {label!r}: {text!r}"
            for index in range(offset, offset + len(label)):
                char = text_page.get_text_range(index, 1)
                if char.isspace():
                    continue
                left, bottom, right, top = text_page.get_charbox(index)
                assert left >= left_limit - 1 and right <= right_limit + 1, (label, char, left, right)
                assert 0 <= bottom < top <= page.get_height(), (label, char, bottom, top)
                if "A" <= char <= "Z":
                    assert top - bottom >= minimum_capital_height, f"Unnecessarily shrunken label {label!r}"
                crop = image.crop((
                    math.floor(left * scale_x), math.floor((page.get_height() - top) * scale_y),
                    math.ceil(right * scale_x), math.ceil((page.get_height() - bottom) * scale_y),
                )).convert("L")
                assert crop.width > 0 and crop.height > 0
                histogram = crop.histogram()
                ink = sum(histogram[210:]) if light else sum(histogram[:160])
                assert ink >= 2, f"Invisible glyph {char!r} in {label!r} at {(left, bottom, right, top)}"
    finally:
        text_page.close()


GANTT = """gantt
    dateFormat YYYY-MM-DD
    axisFormat %m-%d
    section Release
    PLAN-101 :a1, 2026-10-01, 3d
    BUILD-202 :a2, after a1, 7d
    CHECK-303 :a3, after a2, 5d
    SHIP-404 :a4, after a3, 1d
"""


@pytest.mark.parametrize(("css", "dimensions", "margins"), [
    ("", (210, 297), (15, 15)),
    ("@page { size: Letter landscape; margin: 12mm 18mm; }", (279.4, 215.9), (18, 18)),
    ("@page { size: 180mm 240mm; margin: 10mm 12mm 14mm 22mm; }", (180, 240), (22, 12)),
], ids=["a4", "letter-landscape", "custom-asymmetric"])
def test_gantt_fits_actual_pdf_paper_and_margins(tmp_path, css, dimensions, margins):
    target = tmp_path / "gantt-page-geometry.pdf"
    result = markdown_to_pdf(f"```mermaid\n{GANTT}```\n", target, custom_css=css)
    assert result["ok"]
    assert not result["warnings"]
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 1
        page = document[0]
        try:
            assert page.get_width() == pytest.approx(dimensions[0] * 72 / 25.4, abs=1)
            assert page.get_height() == pytest.approx(dimensions[1] * 72 / 25.4, abs=1)
            image = _rasterize(page, tmp_path / "gantt-page-geometry.png")
            # Fitting the chart to the paper should shorten its time axis, not
            # shrink its labels. Allow font differences across the CI platforms.
            _assert_labels_visible(page, image, ("PLAN-101", "BUILD-202", "CHECK-303"),
                                   margins=margins, minimum_capital_height=6, light=True)
            _assert_labels_visible(page, image, ("SHIP-404",), margins=margins, minimum_capital_height=6)
        finally:
            page.close()


@pytest.mark.parametrize(("source", "labels"), [
    ("""sequenceDiagram
    participant A as CLIENT-101
    participant B as GATEWAY-202
    participant C as WORKER-303
    participant D as STORAGE-404
    A->>B: 中文请求 2026-10-23
    B->>C: VALIDATE-505 and prepare the report
    C->>D: Persist the completed report
    D-->>A: COMPLETE-606
""", ("CLIENT-101", "STORAGE-404", "VALIDATE-505", "COMPLETE-606", "中文请求", "2026-10-23")),
    ("""flowchart TB
    A["中文输入校验与编号 IT-001"] --> B["多段文字处理与日期 2026-10-23"]
    A --> C["字体回退检查与版本 v0.3.0"]
    B --> D["生成报告并检查数字 0123456789"]
    C --> D
""", ("中文输入校验", "IT-001", "2026-10-23", "v0.3.0", "0123456789")),
], ids=["wide-sequence", "dense-chinese-labels"])
def test_complex_diagram_labels_are_visible_and_not_clipped(tmp_path, source, labels):
    target = tmp_path / "complex-diagram.pdf"
    result = markdown_to_pdf(f"```mermaid\n{source}```\n", target)
    assert result["ok"]
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 1
        page = document[0]
        try:
            image = _rasterize(page, tmp_path / "complex-diagram.png")
            _assert_labels_visible(page, image, labels)
        finally:
            page.close()


def test_dark_diagram_math_and_digits_have_visible_light_ink(tmp_path):
    target = tmp_path / "dark-diagram-math.pdf"
    source = r'''```mermaid
flowchart LR
    A["$$\frac{x^2}{2}$$"] --> B["FORMULA-2026 中文"]
```
'''
    result = markdown_to_pdf(source, target, custom_css="""
        .mermaid-diagram {
            --pele-fg: #ffffff;
            --pele-surface: #111827;
            --pele-line: #93c5fd;
        }
    """)
    assert result["ok"]
    assert not result["warnings"]
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 1
        page = document[0]
        try:
            image = _rasterize(page, tmp_path / "dark-diagram-math.png")
            _assert_labels_visible(page, image, ("FORMULA-2026", "中文", "𝑥", "2"), light=True)
        finally:
            page.close()


def test_diagram_moves_whole_to_next_page_at_pagination_boundary(tmp_path):
    target = tmp_path / "diagram-pagination.pdf"
    source = '''FIRST-PAGE

<div class="page-spacer"></div>

```mermaid
flowchart TB
    A["START-101"] --> B["MIDDLE-202"] --> C["FINISH-303"]
```

AFTER-DIAGRAM
'''
    result = markdown_to_pdf(source, target, unsafe_html=True, custom_css=".page-spacer { height: 210mm; }")
    assert result["ok"]
    assert not result["warnings"]
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 2
        for index in range(len(document)):
            page = document[index]
            try:
                image = _rasterize(page, tmp_path / f"diagram-pagination-{index + 1}.png")
                text_page = page.get_textpage()
                try:
                    text = text_page.get_text_range()
                finally:
                    text_page.close()
                if index == 0:
                    assert "FIRST-PAGE" in text
                    assert all(label not in text for label in ("START-101", "MIDDLE-202", "FINISH-303"))
                else:
                    assert "AFTER-DIAGRAM" in text
                    _assert_labels_visible(page, image, ("START-101", "MIDDLE-202", "FINISH-303"))
            finally:
                page.close()


def test_oversized_explicit_lr_diagram_warns_and_strict_preserves_pdf(tmp_path):
    # Direction is an author choice. A long LR chain must not silently become TB.
    nodes = [f'N{i}["STAGE-{i:03d} with a deliberately long label"]' for i in range(8)]
    source = "```mermaid\nflowchart LR\n" + " --> ".join(nodes) + "\n```\n"
    target = tmp_path / "oversized-diagram.pdf"
    result = markdown_to_pdf(source, target)
    assert result["ok"]
    assert any(warning["type"] == "diagram_text_too_small" for warning in result["warnings"])
    original = target.read_bytes()
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 1
        page = document[0]
        try:
            image = _rasterize(page, tmp_path / "oversized-diagram.png")
            _assert_labels_visible(page, image, ("STAGE-000", "STAGE-007"))
            text_page = page.get_textpage()
            try:
                text = text_page.get_text_range()
                first = text_page.get_charbox(text.index("STAGE-000"))
                last = text_page.get_charbox(text.index("STAGE-007"))
                assert last[0] > first[2] + 200, "Explicit LR direction must survive width fitting"
                assert abs(last[1] - first[1]) < 1
            finally:
                text_page.close()
        finally:
            page.close()
    with pytest.raises(RuntimeError) as caught:
        markdown_to_pdf(source, target, overwrite=True, strict=True)
    assert any(warning["type"] == "diagram_text_too_small" for warning in caught.value.warnings)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".mdtopdf-*"))
