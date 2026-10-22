"""Compatibility contracts for Mermaid fences rendered through bundled Pele."""

import base64
from html import unescape
from html.parser import HTMLParser
from importlib import resources
import json
import re

import pytest
from click.testing import CliRunner

from mdtopdf import markdown_to_html, markdown_to_pdf
from mdtopdf.core import browser
from mdtopdf.core.mermaid import find_mermaid_backend, render_mermaid_to_svg
from mdtopdf.mdtopdf_cli import cli


class _Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)

    def matching(self, tag, class_name=None):
        return [attrs for name, attrs in self.elements if name == tag and (
            class_name is None or class_name in attrs.get("class", "").split()
        )]


DIAGRAMS = [
    ("flowchart", "flowchart LR\n A[Markdown] --> B[PDF]", "Markdown"),
    ("sequence", "sequenceDiagram\n Alice->>Bob: Render report\n Bob-->>Alice: Complete", "Render report"),
    ("class", "classDiagram\n class Report {\n +String title\n +render()\n }", "Report"),
    ("state", "stateDiagram-v2\n [*] --> Draft\n Draft --> Published\n Published --> [*]", "Published"),
    ("er", "erDiagram\n CUSTOMER ||--o{ ORDER : places", "CUSTOMER"),
    ("gantt", "gantt\n dateFormat YYYY-MM-DD\n section Release\n Build :a1, 2026-10-01, 2d", "Build"),
    ("gitGraph", 'gitGraph\n commit id: "Initial"\n branch feature\n checkout feature\n commit id: "Renderer"', "Renderer"),
    ("pie", 'pie title Status\n "Ready" : 8\n "Pending" : 2', "Ready"),
    ("mindmap", "mindmap\n root((Report))\n  Source\n  Output", "Source"),
    ("timeline", "timeline\n title Release\n 2026 : Render\n 2027 : Publish", "Publish"),
    ("xychart", 'xychart-beta\n x-axis [Jan, Feb, Mar]\n y-axis "Count" 0 --> 10\n bar [2, 5, 8]', "Count"),
    ("sankey", "sankey-beta\n Source,Target,10", "Target"),
]


@pytest.mark.parametrize(("kind", "source", "label"), DIAGRAMS, ids=[item[0] for item in DIAGRAMS])
def test_mermaid_diagram_families_render_with_pele(kind, source, label):
    result = markdown_to_html(f"```mermaid\n{source}\n```\n")
    document = _Elements(result.body)
    roots = document.matching("svg", "pele")
    assert len(roots) == 1, kind
    assert "mermaid-rendered" in roots[0]["class"].split()
    assert label in "".join(document.text)
    assert "data-mdtopdf-mermaid" not in result.html
    assert "<script" not in result.html
    assert not result.warnings


def test_mermaid_and_mmd_fences_render_inside_quotes_and_lists():
    result = markdown_to_html(
        '> ```mermaid\n> graph TD\n> A[引用 2026] --> B[完成]\n> ```\n\n'
        '- Nested diagram:\n\n'
        '    ~~~mmd\n    graph LR\n    A[列表 IT-001] --> B[完成]\n    ~~~\n'
    )
    document = _Elements(result.body)
    assert len(document.matching("svg", "pele")) == 2
    assert len(document.matching("figure", "mermaid-diagram")) == 2
    assert "引用 2026" in "".join(document.text)
    assert "列表 IT-001" in "".join(document.text)
    assert "<blockquote>" in result.body and "<li>" in result.body
    assert not result.warnings


def test_frontmatter_directives_and_explicit_diagram_styles_survive():
    result = markdown_to_html('''```mermaid
---
title: Publication pipeline
config:
  flowchart:
    curve: linear
---
%%{init: {"flowchart": {"nodeSpacing": 30}}}%%
flowchart LR
  accTitle: Publication diagram
  accDescr: Draft passes through review
  A[Draft] --> B[Review]:::review --> C[Done]
  classDef review fill:#fef3c7,stroke:#92400e,color:#78350f
  style C fill:#dcfce7,stroke:#166534
  linkStyle 0 stroke:#9a3f65
```
''')
    assert "Publication pipeline" in result.body
    assert "Publication diagram" in result.body
    assert "Draft passes through review" in result.body
    for color in ("#fef3c7", "#92400e", "#78350f", "#dcfce7", "#166534", "#9a3f65"):
        assert color in result.body
    assert not result.warnings


def test_multiple_diagrams_have_distinct_ids_and_valid_local_references():
    source = "flowchart LR\n accTitle: Pipeline\n A[Source] --> B[Output]"
    sankey = "sankey-beta\n Source,Target,10"
    result = markdown_to_html("\n\n".join(f"```mermaid\n{diagram}\n```" for diagram in (source, source, sankey, sankey)))
    document = _Elements(result.body)
    assert len(document.matching("svg", "pele")) == 4
    ids = [attrs["id"] for _, attrs in document.elements if "id" in attrs]
    assert ids and len(ids) == len(set(ids)), "SVG IDs must not collide between diagrams"
    references = re.findall(r"url\(#([^\)]+)\)", result.body)
    for _, attrs in document.elements:
        references.extend(attrs.get("aria-labelledby", "").split())
        references.extend(attrs.get("aria-describedby", "").split())
        href = attrs.get("href", attrs.get("xlink:href", ""))
        if href.startswith("#"):
            references.append(href[1:])
    assert references
    assert set(references) <= set(ids)
    assert not result.warnings


def _inspect_static_svg(svg):
    """Inspect exported SVG without the document stylesheet or renderer scripts."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        executable, source_kind = browser._resolve_executable(driver.chromium.executable_path)
        options = {"headless": True, "chromium_sandbox": True}
        if source_kind == "playwright":
            options["channel"] = "chromium"
        else:
            options["executable_path"] = executable
        with driver.chromium.launch(**options) as renderer:
            page = renderer.new_page()
            page.set_content(svg)
            return page.evaluate("""() => {
                const svg = document.querySelector('svg');
                const node = svg.querySelector('.pele-node');
                const shape = node.querySelector('rect, path, polygon, circle, ellipse');
                const label = [...svg.querySelectorAll('.pele-label')].find(element => element.textContent);
                const math = svg.querySelector('math');
                const mathFrame = svg.querySelector('foreignObject.pele-math');
                const bounds = svg.getBoundingClientRect();
                return {
                    fill: getComputedStyle(shape).fill,
                    color: getComputedStyle(label).fill,
                    font: getComputedStyle(label).fontFamily,
                    size: getComputedStyle(label).fontSize,
                    width: bounds.width,
                    height: bounds.height,
                    mathColor: math ? getComputedStyle(math).color : null,
                    mathWidth: math ? math.getBoundingClientRect().width : null,
                    mathHeight: math ? math.getBoundingClientRect().height : null,
                    mathFrameWidth: mathFrame ? mathFrame.getBoundingClientRect().width : null,
                    mathFrameHeight: mathFrame ? mathFrame.getBoundingClientRect().height : null,
                };
            }""")


def test_custom_diagram_theme_and_fonts_survive_standalone_svg_export():
    result = markdown_to_html(
        "```mermaid\nflowchart LR\n A[Themed 2026] --> B[Report]\n```",
        custom_css="""
            .mermaid-diagram {
                --pele-surface: #e0f2fe;
                --pele-fg: #123456;
                --pele-font: monospace;
                --pele-font-mono: monospace;
                font-size: 18px;
            }
        """,
    )
    svg = re.search(r"<svg\b.*</svg>", result.body, re.S).group(0)
    computed = _inspect_static_svg(svg)
    assert computed["fill"] == "rgb(224, 242, 254)"
    assert computed["color"] == "rgb(18, 52, 86)"
    assert computed["font"] == "monospace"
    assert computed["size"] == "18px"
    assert computed["width"] > computed["height"] > 0
    assert not result.warnings


def test_public_svg_api_uses_the_document_theme_and_preserves_lr_direction():
    svg = render_mermaid_to_svg("graph LR\n A[First] --> B[Second] --> C[Third]")
    assert find_mermaid_backend().name == "pele.global.js"
    computed = _inspect_static_svg(svg)
    assert computed["color"] == "rgb(48, 40, 63)"
    assert computed["width"] > computed["height"] > 0
    # The Latin-first stack also applies to diagram digits in mixed CJK labels.
    assert computed["font"].index("Arial") < computed["font"].index("Noto Sans CJK SC")


def test_font_used_only_by_diagrams_is_loaded_before_label_measurement():
    font = resources.files("mdtopdf").joinpath("vendor/katex/dist/fonts/KaTeX_Main-Regular.woff2")
    encoded = base64.b64encode(font.read_bytes()).decode("ascii")
    css = (
        '@font-face { font-family: DiagramOnly; src: url("data:font/woff2;base64,' + encoded + '"); }\n'
        '.mermaid-diagram { --pele-font: DiagramOnly, monospace; }'
    )
    source = "```mermaid\nflowchart LR\n A[iiiiiiiiiiiiiiiiiiiiiiii] --> B[WWWWWWWWWWWW]\n```"
    diagram_only = markdown_to_html(source, custom_css=css)
    preloaded = markdown_to_html("Preload the diagram font.\n\n" + source, custom_css=css + "body { font-family: DiagramOnly, monospace; }")
    measured = _Elements(diagram_only.body).matching("svg", "pele")[0]
    expected = _Elements(preloaded.body).matching("svg", "pele")[0]
    assert measured["viewbox"] == expected["viewbox"]
    assert not diagram_only.warnings and not preloaded.warnings


def test_missing_diagram_font_warns_uses_fallback_and_strict_preserves_output(tmp_path):
    missing_font = (tmp_path / "missing-diagram-font.woff2").as_uri()
    css = (
        '@font-face { font-family: MissingDiagramFont; src: url("' + missing_font + '"); }\n'
        '.mermaid-diagram { --pele-font: MissingDiagramFont, monospace; }'
    )
    source = "```mermaid\nflowchart LR\n A[Font fallback 2026] --> B[Rendered]\n```"
    rendered = markdown_to_html(source, custom_css=css)
    fallback = markdown_to_html(source, custom_css=".mermaid-diagram { --pele-font: monospace; }")
    actual_svg = _Elements(rendered.body).matching("svg", "pele")[0]
    fallback_svg = _Elements(fallback.body).matching("svg", "pele")[0]
    assert actual_svg["viewbox"] == fallback_svg["viewbox"]
    assert any(w["type"] == "resource_load_failed" and w.get("url") == missing_font for w in rendered.warnings)

    target = tmp_path / "fallback.pdf"
    result = markdown_to_pdf(source, target, custom_css=css)
    assert result["ok"] and target.read_bytes().startswith(b"%PDF-")
    assert any(w["type"] == "resource_load_failed" for w in result["warnings"])
    original = target.read_bytes()
    with pytest.raises(RuntimeError) as caught:
        markdown_to_pdf(source, target, custom_css=css, overwrite=True, strict=True)
    assert any(w["type"] == "resource_load_failed" for w in caught.value.warnings)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob(".mdtopdf-*"))


def test_diagram_math_uses_bundled_katex_without_document_math():
    result = markdown_to_html(r'''```mermaid
flowchart LR
  A["$$E = mc^2$$"] --> B["$$\frac{1}{2}$$"]
```
''')
    assert "pele-math" in result.body
    assert "<math" in result.body
    assert "<mfrac>" in result.body
    assert "data-mdtopdf-math" not in result.html
    assert not result.warnings


def test_standalone_svg_math_and_text_share_custom_foreground_and_math_size():
    result = markdown_to_html(
        '```mermaid\nflowchart LR\n A["$$\\frac{x^2}{2}$$"] --> B[Plain label]\n```',
        custom_css=".mermaid-diagram { --pele-fg: white; --pele-surface: black; }",
    )
    svg = re.search(r"<svg\b.*</svg>", result.body, re.S).group(0)
    computed = _inspect_static_svg(svg)
    assert computed["fill"] == "rgb(0, 0, 0)"
    assert computed["color"] == "rgb(255, 255, 255)"
    assert computed["mathColor"] == "rgb(255, 255, 255)"
    assert computed["mathFrameWidth"] == pytest.approx(computed["mathWidth"], abs=0.1)
    assert computed["mathFrameHeight"] == pytest.approx(computed["mathHeight"], abs=0.1)
    assert not result.warnings


def test_invalid_diagram_math_warns_and_strict_preserves_existing_output(tmp_path):
    source = r'```mermaid' + '\nflowchart LR\n A["$$\\notARealKatexCommand$$"] --> B[Done]\n```'
    result = markdown_to_html(source)
    assert any(w["type"] == "math_fallback" for w in result.warnings)
    assert r"\notARealKatexCommand" in unescape(result.body)
    target = tmp_path / "keep.pdf"
    target.write_bytes(b"previous valid PDF")
    with pytest.raises(RuntimeError) as caught:
        markdown_to_pdf(source, target, overwrite=True, strict=True)
    assert any(w["type"] == "math_fallback" for w in caught.value.warnings)
    assert target.read_bytes() == b"previous valid PDF"


@pytest.mark.parametrize("command,extension", [("convert", "pdf"), ("html", "html")])
def test_invalid_diagram_is_json_failure_and_preserves_existing_output(tmp_path, command, extension):
    source = tmp_path / "invalid.md"
    source.write_text("```mermaid\nflowchart LR\n A[Unclosed\n```\n", encoding="utf-8")
    target = tmp_path / f"keep.{extension}"
    target.write_bytes(b"previous valid output")
    result = CliRunner().invoke(cli, [command, str(source), "-o", str(target), "--overwrite", "--json"])
    data = json.loads(result.stdout)
    assert result.exit_code == 1
    assert data["ok"] is False
    assert data["error"]
    assert not result.stderr
    assert target.read_bytes() == b"previous valid output"
    assert not list(tmp_path.glob(".mdtopdf-*"))
