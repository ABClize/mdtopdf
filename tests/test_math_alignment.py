import pytest
from playwright.sync_api import sync_playwright

from mdtopdf import markdown_to_html
from mdtopdf.core.browser import _resolve_executable


@pytest.mark.parametrize('media', ['screen', 'print'])
def test_inline_fraction_denominator_is_centered(tmp_path, media):
    source = tmp_path / 'fraction.html'
    source.write_text(markdown_to_html(
        r'The quadratic formula $x = \frac{-b\pm\sqrt{b^2-4ac}}{2a}$, and the result.'
    ).html, encoding='utf-8')
    with sync_playwright() as driver:
        executable, kind = _resolve_executable(driver.chromium.executable_path)
        options = {'channel': 'chromium'} if kind == 'playwright' else {'executable_path': executable}
        browser = driver.chromium.launch(headless=True, chromium_sandbox=True, **options)
        try:
            page = browser.new_page()
            page.emulate_media(media=media)
            page.goto(source.as_uri())
            page.wait_for_selector('.katex .mfrac')
            page.evaluate('() => document.fonts.ready')
            geometry = page.locator('.mfrac').evaluate('''el => {
                const line = el.querySelector('.frac-line').getBoundingClientRect();
                const denominator = [...el.querySelectorAll('.vlist > span > span')]
                    .find(node => node.textContent === '2a');
                const range = document.createRange();
                range.selectNodeContents(denominator);
                const rect = range.getBoundingClientRect();
                return {line: (line.left + line.right) / 2,
                        denominator: (rect.left + rect.right) / 2};
            }''')
            assert abs(geometry['line'] - geometry['denominator']) < 1, geometry
        finally:
            browser.close()
