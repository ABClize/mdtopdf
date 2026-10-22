import io
from urllib.parse import unquote
from xml.etree import ElementTree

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright
import pypdfium2 as pdfium
import pytest

from mdtopdf import markdown_to_html, markdown_to_pdf
from mdtopdf.core.browser import _resolve_executable


KINDS = ('note', 'tip', 'success', 'done', 'check', 'warning', 'caution',
         'attention', 'danger', 'error', 'fail', 'failure', 'missing',
         'question', 'help', 'faq', 'quote', 'custom')
SOURCE = '```text\nExample code\n```\n\n' + '\n\n'.join(
    f'> [!{kind}] {kind}\n> Example body.' for kind in KINDS
)
DOT_COLORS = ((255, 95, 86), (255, 189, 46), (39, 201, 63))


def assert_three_dots(image):
    pixels = image.convert('RGB')
    data = pixels.load()
    centers = []
    for color in DOT_COLORS:
        points = [(x, y) for y in range(pixels.height) for x in range(pixels.width)
                  if data[x, y] == color]
        assert len(points) >= 3, f'Missing solid circle: {color}'
        centers.append((sum(x for x, _ in points) / len(points),
                        sum(y for _, y in points) / len(points)))
    assert centers[0][0] < centers[1][0] < centers[2][0]
    assert max(y for _, y in centers) - min(y for _, y in centers) <= 1


@pytest.mark.parametrize('media', ['screen', 'print'])
def test_decorations_are_font_independent_and_solid(tmp_path, media):
    source = tmp_path / 'decorations.html'
    source.write_text(markdown_to_html(SOURCE).html, encoding='utf-8')
    with sync_playwright() as driver:
        options = {'headless': True, 'chromium_sandbox': True}
        executable, source_kind = _resolve_executable(driver.chromium.executable_path)
        options.update({'channel': 'chromium'} if source_kind == 'playwright'
                       else {'executable_path': executable})
        browser = driver.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={'width': 800, 'height': 1100}, device_scale_factor=2)
            page.emulate_media(media=media)
            page.goto(source.as_uri())
            page.evaluate('() => document.fonts.ready')
            rows = page.locator('.callout').evaluate_all('''items => items.map(el => {
                const box = getComputedStyle(el);
                const icon = getComputedStyle(el.querySelector('.callout-title'), '::before');
                return {content: icon.content, image: icon.backgroundImage,
                    border: box.borderLeftWidth, background: box.backgroundImage,
                    shadow: box.boxShadow};
            })''')
            assert len(rows) == len(KINDS)
            for row in rows:
                assert row['content'] == '\"\"', 'Icon must not contain a font glyph'
                assert row['image'].startswith('url("data:image/svg+xml,'), row
                svg = ElementTree.fromstring(unquote(row['image'].split(',', 1)[1][:-2]))
                assert not any(el.tag.endswith('text') for el in svg.iter())
                assert row['border'] == '5px'
                assert row['background'] == 'none'
                if media == 'print':
                    assert row['shadow'] == 'none'
            if media == 'print':
                assert page.locator('pre').evaluate('el => getComputedStyle(el).boxShadow') == 'none'
            assert_three_dots(Image.open(io.BytesIO(page.locator('pre').screenshot())))
            for kind in ('note', 'tip', 'warning', 'danger', 'question', 'quote', 'custom'):
                title = page.locator(f'.callout-{kind} .callout-title')
                width = round(title.evaluate('el => parseFloat(getComputedStyle(el, "::before").width)') * 2)
                image = Image.open(io.BytesIO(title.screenshot())).convert('RGB')
                white = [x for y in range(image.height) for x in range(width)
                         if min(image.getpixel((x, y))) > 250]
                assert len(white) >= 3, f'Missing icon symbol: {kind}'
                center = (min(white) + max(white)) / 2
                assert abs(center - (width - 1) / 2) <= width * 0.15, kind
            # Paragraph alignment overrides must not move anything inside a vector icon.
            icon = page.locator('.callout-title').first
            width = round(icon.evaluate('el => parseFloat(getComputedStyle(el, "::before").width)') * 2)
            before = Image.open(io.BytesIO(icon.screenshot())).convert('RGB')
            before = before.crop((0, 0, width, before.height))
            page.add_style_tag(content='.callout-title::before { text-align-last: right; text-align: right; font-family: monospace; }')
            after = Image.open(io.BytesIO(icon.screenshot())).convert('RGB')
            after = after.crop((0, 0, width, after.height))
            before.save(tmp_path / f'icon-before-{media}.png')
            after.save(tmp_path / f'icon-after-{media}.png')
            assert before.size == after.size
            # Compare the icon pixels, not PNG encoding or adjacent title text.
            # Permit small edge-antialiasing differences from fractional scrolling.
            difference = ImageChops.difference(before, after)
            assert max(ImageStat.Stat(difference).mean) < 2
        finally:
            browser.close()


def test_pdf_decorations_keep_three_dots_at_multiple_scales(tmp_path):
    target = tmp_path / 'decorations.pdf'
    markdown_to_pdf(SOURCE, target)
    with pdfium.PdfDocument(target) as document:
        page = document[0]
        try:
            for scale in (1, 2, 3):
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    image.save(tmp_path / f'decorations-{scale}.png')
                    assert_three_dots(image)
                finally:
                    bitmap.close()
        finally:
            page.close()


@pytest.mark.parametrize(('lead_height', 'line_count', 'first_code_page'), [
    (200, 60, 1),
    (80, 10, 0),
], ids=['keep-decoration-with-code', 'use-remaining-page-space'])
def test_code_decoration_stays_with_first_line_while_long_code_paginates(
    tmp_path, lead_height, line_count, first_code_page,
):
    lines = [f'LINE{index:03d}' for index in range(line_count)]
    source = 'INTRO\n\n```text\n' + '\n'.join(lines) + '\n```\n'
    target = tmp_path / 'code-page-break.pdf'
    # Test both a nearly full page and enough room to begin a block that could
    # fit on a fresh page. Avoiding breaks in the whole pre wastes the latter.
    result = markdown_to_pdf(
        source, target, strict=True,
        custom_css='@page { size: 400px 300px; margin: 20px; } '
                   f'p {{ height: {lead_height}px; margin: 0; }}',
        include_page_header=False, include_page_footer=False,
    )
    assert result['ok'] and not result['warnings']
    page_texts = []
    decoration_pages = []
    with pdfium.PdfDocument(target) as document:
        for index in range(len(document)):
            page = document[index]
            text_page = page.get_textpage()
            bitmap = page.render(scale=2)
            try:
                page_texts.append(text_page.get_text_range())
                image = bitmap.to_pil().copy().convert('RGB')
                image.save(tmp_path / f'code-page-break-{index + 1}.png')
                colors = {color: count for count, color in image.getcolors(image.width * image.height)}
                if all(colors.get(color, 0) >= 3 for color in DOT_COLORS):
                    decoration_pages.append(index)
            finally:
                bitmap.close()
                text_page.close()
                page.close()
    first_line_pages = [index for index, text in enumerate(page_texts) if lines[0] in text]
    assert first_line_pages == [first_code_page]
    assert decoration_pages == first_line_pages, 'Code decoration must accompany the first code line'
    assert sum(any(line in text for line in lines) for text in page_texts) > 1
    complete_text = '\n'.join(page_texts)
    for line in lines:
        assert complete_text.count(line) == 1, f'Missing or duplicated code line: {line}'
