"""Exercise print-page CSS through Chromium, including named and conditional pages."""

from importlib import resources

from playwright.sync_api import sync_playwright
import pypdfium2 as pdfium
import pytest

from mdtopdf import markdown_to_pdf
from mdtopdf.core.browser import _resolve_executable


@pytest.fixture(scope="module")
def renderer():
    with sync_playwright() as driver:
        executable, source_kind = _resolve_executable(driver.chromium.executable_path)
        options = {"channel": "chromium"} if source_kind == "playwright" else {"executable_path": executable}
        with driver.chromium.launch(headless=True, chromium_sandbox=True, **options) as browser:
            yield browser


@pytest.fixture
def print_page(renderer):
    page = renderer.new_page()
    page.emulate_media(media="print")
    yield page
    page.close()


def _page_area(page, css, *, body='<main class="document"></main>', action="measure"):
    page.set_content("<!DOCTYPE html><html><head><style>"
                     "html { font-size: 13px; } body, main, figure { margin: 0; padding: 0; }"
                     + css + "</style></head><body>" + body + "</body></html>")
    script = resources.files("mdtopdf").joinpath("vendor/page-layout.js").read_text(encoding="utf-8")
    return page.evaluate(script, {"action": action})


@pytest.mark.parametrize(("css", "expected"), [
    ("""
        @page { size: 400px 600px; margin: 10px; }
        @page chapter { size: 600px 800px; margin: 30px 40px; }
        .document { page: chapter; }
    """, (520, 740)),
    ("""
        @page { size: 400px 600px; margin: 10px; }
        @page:first { margin-top: 80px; }
        @page:left { margin-left: 70px; }
        @page:right { margin-right: 50px; }
    """, (320, 510)),
    ("""
        @page { size: 400px 600px; margin: 10px; }
        @page chapter { margin: 20px; }
        @page:left { margin-left: 70px; }
        .document { page: chapter; }
    """, (360, 560)),
    ("""
        @page { size: 400px 600px; margin: 10px; }
        @media print {
            @supports (display: grid) { @page { size: 500px 600px; margin: 40px; } }
            @supports (mdtopdf-unsupported-property: yes) { @page { size: 30px; margin: 0; } }
        }
        @media screen { @page { size: 100px; margin: 0; } }
    """, (420, 520)),
    ("""
        :root { --paper-width: 400px; --inset: 10px; }
        @page {
            size: calc(var(--paper-width) - calc(20px + 20px)) calc(300px * 2);
            margin: calc(5% + var(--inset)) 10%;
        }
    """, (288, 520)),
    ("""
        @page { size: 200px 300px; margin: 10%; }
    """, (160, 240)),
    ("""
        @page { size: 200px 300px; font-size: 20px; margin: 2em; }
    """, (120, 220)),
    ("""
        :root { font-size: 20px; }
        @page { size: 400px 600px; font-size: 150%; margin: 2em; }
    """, (280, 480)),
    ("""
        :root { font-size: 20px; }
        @page { size: 200px 300px; margin: 2em; }
    """, (120, 220)),
], ids=["named-page", "first-left-right", "named-specificity", "print-supports",
        "vars-calc-percent", "physical-percent", "page-em",
        "relative-page-font", "inherited-page-font"])
def test_printable_area_follows_active_page_css(print_page, css, expected):
    area = _page_area(print_page, css)
    assert area["width"] == pytest.approx(expected[0], abs=0.1)
    assert area["height"] == pytest.approx(expected[1], abs=0.1)


def test_nested_diagrams_use_their_own_named_page_area(print_page):
    css = """
        @page { size: 400px 600px; margin: 10px; }
        @page appendix { size: 300px 400px; margin: 20px; }
        .appendix { page: appendix; }
    """
    body = '''<main class="document">
        <figure class="mermaid-diagram"></figure>
        <section class="appendix"><figure class="mermaid-diagram"></figure></section>
    </main>'''
    areas = _page_area(print_page, css, body=body, action="prepare")
    assert [(area["width"], area["height"]) for area in areas] == [(380, 580), (260, 360)]


def test_padded_diagram_reserves_its_border_and_padding_on_a_named_page(print_page):
    css = """
        @page { size: 800px 1000px; margin: 20px; }
        @page small { size: 400px 600px; margin: 10px; }
        figure { page: small; padding: 10mm; border: 1mm solid; }
    """
    body = '<main class="document"><figure class="mermaid-diagram"></figure></main>'
    area, = _page_area(print_page, css, body=body, action="prepare")
    insets = 22 * 96 / 25.4
    # CSS borders snap to device pixels; allow their subpixel rounding while
    # checking that both axes reserve the figure's complete non-content box.
    assert area["width"] == pytest.approx(380 - insets, abs=2)
    assert area["height"] == pytest.approx(580 - insets, abs=2)


def test_page_em_geometry_matches_chromium_pdf_margins(tmp_path, print_page):
    css = "@page { size: 200px 300px; font-size: 20px; margin: 2em; }"
    assert _page_area(print_page, css) == {"width": 120, "height": 220}
    target = tmp_path / "page-em-geometry.pdf"
    result = markdown_to_pdf(
        'PAGEBOX\n\n```mermaid\nflowchart LR\n A[Left] --> B[Right]\n```\n',
        target, custom_css=css, include_page_header=False, include_page_footer=False,
    )
    assert result["ok"]
    with pdfium.PdfDocument(target) as document:
        assert len(document) == 1
        page = document[0]
        try:
            assert page.get_width() == pytest.approx(150, abs=1)
            assert page.get_height() == pytest.approx(225, abs=1)
            text = page.get_textpage()
            try:
                offset = text.get_text_range().index("PAGEBOX")
                left = text.get_charbox(offset)[0]
                # 2em at the page's 20px font is a 40px / 30pt left margin.
                assert 30 <= left <= 32
            finally:
                text.close()
            bitmap = page.render(scale=3)
            try:
                bitmap.to_pil().save(tmp_path / "page-em-geometry.png")
            finally:
                bitmap.close()
        finally:
            page.close()
