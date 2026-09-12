"""Check rasterized glyphs, not only PDF text extraction."""

import math

import pypdfium2 as pdfium

from mdtopdf import markdown_to_pdf


def _assert_visible_digits(page, image):
    text_page = page.get_textpage()
    try:
        text = text_page.get_text_range()
        assert "0123456789" in text
        assert "2026-06-22" in text
        assert "v0.2.2" in text
        assert "IT-001" in text
        sx, sy = image.width / page.get_width(), image.height / page.get_height()
        checked = 0
        for index in range(text_page.count_chars()):
            char = text_page.get_text_range(index, 1)
            if char not in "0123456789" or not char:
                continue
            left, bottom, right, top = text_page.get_charbox(index)
            crop = image.crop((
                math.floor(left * sx), math.floor((page.get_height() - top) * sy),
                math.ceil(right * sx), math.ceil((page.get_height() - bottom) * sy),
            )).convert("L")
            assert crop.width > 0 and crop.height > 0
            histogram = crop.histogram()
            assert sum(histogram[:200]) >= 3, f"Invisible digit {char!r} at {index}, box={(left, bottom, right, top)}"
            checked += 1
        # 24 body digits plus the current/total page counters.
        assert checked >= 26
    finally:
        text_page.close()


def test_mixed_cjk_digits_are_visible_in_pdfium(tmp_path):
    output = tmp_path / "mixed-digits.pdf"
    result = markdown_to_pdf(
        "# 中文报告\n\n数字 0123456789\n\n日期 2026-06-22\n\n版本 v0.2.2\n\n编号 IT-001\n",
        output,
    )
    assert result["ok"]
    with pdfium.PdfDocument(output) as pdf:
        page = pdf[0]
        try:
            bitmap = page.render(scale=2)
            try:
                image = bitmap.to_pil().copy()
            finally:
                bitmap.close()
            image.save(tmp_path / "mixed-digits.png")
            _assert_visible_digits(page, image)
        finally:
            page.close()
