"""Shared document colors must survive rendering into self-contained Pele SVGs."""

import re

import pytest
from playwright.sync_api import sync_playwright

from mdtopdf import markdown_to_html
from mdtopdf.core import browser


DOCUMENT = r"""# Report 2026

## Section 2

### Section 3

#### Section 4

##### Section 5

###### Section 6

Body text and [a link](https://example.com).

> [!note] Note
> A shared surface.

| Header | Value |
| --- | --- |
| Alpha | 42 |

```mermaid
flowchart LR
 A["$$\frac{x^2}{2}$$"] --> B[Label 2026]
```

```mermaid
pie title Palette
 "One" : 1
 "Two" : 1
 "Three" : 1
 "Four" : 1
 "Five" : 1
 "Six" : 1
```
"""


@pytest.fixture(scope="module")
def theme_page():
    with sync_playwright() as driver:
        executable, source = browser._resolve_executable(driver.chromium.executable_path)
        options = {"headless": True, "chromium_sandbox": True}
        if source == "playwright":
            options["channel"] = "chromium"
        else:
            options["executable_path"] = executable
        with driver.chromium.launch(**options) as renderer:
            yield renderer.new_page()


def _colors(page, html):
    page.emulate_media(media="print")
    page.set_content(html)
    return page.evaluate("""() => {
        const css = selector => getComputedStyle(document.querySelector(selector));
        return {
            body: css('body').color,
            background: css('body').backgroundColor,
            headings: Array.from({length: 6}, (_, i) => css(`h${i + 1}`).color),
            link: css('main p a').color,
            tableHeader: css('th').backgroundColor,
            calloutSurface: css('blockquote.callout').backgroundColor,
            calloutAccent: css('blockquote.callout').borderLeftColor,
            diagramText: css('.pele-flowchart .pele-label').fill,
            diagramSurface: css('.pele-flowchart .pele-node rect').fill,
            diagramBorder: css('.pele-flowchart .pele-node rect').stroke,
            diagramMath: css('.pele-flowchart math').color,
            series: [...document.querySelectorAll('.pele-slice')].map(
                element => getComputedStyle(element).fill),
        };
    }""")


@pytest.mark.parametrize("custom", [False, True], ids=["default", "custom-root-palette"])
def test_document_and_svg_share_palette_without_changing_default_colors(theme_page, custom):
    css = """:root {
        --mdtopdf-background: #182030;
        --mdtopdf-text: #e1e2e3;
        --mdtopdf-heading: #102030;
        --mdtopdf-heading-2: #203040;
        --mdtopdf-heading-3: #304050;
        --mdtopdf-heading-4: #405060;
        --mdtopdf-heading-5: #506070;
        --mdtopdf-heading-6: #607080;
        --mdtopdf-accent: #90b0d0;
        --mdtopdf-surface: #283040;
        --mdtopdf-border: #708090;
    }""" if custom else None
    result = markdown_to_html(DOCUMENT, custom_css=css)
    assert not result.warnings
    colors = _colors(theme_page, result.html)
    headings = (
        ["rgb(16, 32, 48)", "rgb(32, 48, 64)", "rgb(48, 64, 80)",
         "rgb(64, 80, 96)", "rgb(80, 96, 112)", "rgb(96, 112, 128)"]
        if custom else
        ["rgb(23, 59, 92)", "rgb(37, 111, 138)", "rgb(154, 63, 101)",
         "rgb(95, 85, 164)", "rgb(36, 118, 90)", "rgb(161, 92, 24)"]
    )
    assert colors["body"] == colors["diagramText"] == colors["diagramMath"] == (
        "rgb(225, 226, 227)" if custom else "rgb(23, 32, 51)"
    )
    assert colors["background"] == ("rgb(24, 32, 48)" if custom else "rgb(255, 255, 255)")
    assert colors["headings"] == headings
    assert colors["tableHeader"] == headings[0]
    assert colors["series"] == headings[1:] + headings[:1]
    assert colors["link"] == colors["calloutAccent"] == (
        "rgb(144, 176, 208)" if custom else "rgb(15, 110, 167)"
    )
    assert colors["calloutSurface"] == colors["diagramSurface"] == (
        "rgb(40, 48, 64)" if custom else "rgb(245, 249, 253)"
    )
    assert colors["diagramBorder"] == ("rgb(112, 128, 144)" if custom else "rgb(155, 178, 200)")

    # Preview paper and printed paper use the same configurable background.
    theme_page.emulate_media(media="screen")
    assert theme_page.locator(".document").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    ) == colors["background"]

    # No :root palette is available once a diagram is exported on its own.
    svg = re.search(r"<svg\b.*?</svg>", result.body, re.S).group(0)
    theme_page.set_content(svg)
    assert theme_page.locator("math").evaluate(
        "element => getComputedStyle(element).color"
    ) == colors["body"]
    assert theme_page.locator(".pele-node rect").first.evaluate(
        "element => getComputedStyle(element).fill"
    ) == colors["diagramSurface"]


def test_per_diagram_overrides_win_and_remain_in_standalone_svg(theme_page):
    result = markdown_to_html(DOCUMENT, custom_css="""
        :root { --mdtopdf-text: #112233; --mdtopdf-surface: #eeeeee; }
        .mermaid-diagram { --pele-fg: #abcdef; --pele-surface: #123456; }
    """)
    colors = _colors(theme_page, result.html)
    assert colors["body"] == "rgb(17, 34, 51)"
    assert colors["calloutSurface"] == "rgb(238, 238, 238)"
    assert colors["diagramText"] == colors["diagramMath"] == "rgb(171, 205, 239)"
    assert colors["diagramSurface"] == "rgb(18, 52, 86)"

    # Exported SVGs resolve shared tokens before leaving their document context.
    svg = re.search(r"<svg\b.*?</svg>", result.body, re.S).group(0)
    theme_page.set_content(svg)
    assert theme_page.locator("math").evaluate(
        "element => getComputedStyle(element).color"
    ) == "rgb(171, 205, 239)"
    assert theme_page.locator(".pele-node rect").first.evaluate(
        "element => getComputedStyle(element).fill"
    ) == "rgb(18, 52, 86)"
    assert not result.warnings
