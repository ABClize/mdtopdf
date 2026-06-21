from __future__ import annotations

import importlib
import sys
import types
from urllib.parse import quote

import pytest

from mdtopdf import markdown_to_html
from mdtopdf.core import doctor
from mdtopdf.core import katex as katex_core
from mdtopdf.core import markdown as markdown_core
from mdtopdf.core import mermaid as mermaid_core
from mdtopdf.core.html import convert_markdown_file_to_html, derive_html_output_path
from mdtopdf.core.katex import load_katex_css, render_katex_to_html
from mdtopdf.core.mermaid import inspect_mermaid_backend, normalize_mermaid_source, prepare_mermaid_svg
from mdtopdf.core.markdown import (
    DEFAULT_THEME,
    available_themes,
    compose_css,
    latex_to_html_math,
    latex_to_mathml,
    load_theme_css,
    render_markdown_to_html,
)
from mdtopdf.core.pdf import convert_markdown_file, derive_output_path, resolve_base_url


SAMPLE_MARKDOWN = r"""# Demo Report

- [x] Finished task
- [ ] Open task

| Name | Value |
| --- | ---: |
| alpha | 42 |

Some ~~removed~~ text and a footnote.[^1]

Inline math $E = mc^2$ and block math:

$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
$$

```python
print("hello")
```

<script>alert("no")</script>

[^1]: Footnote text.
"""


def test_markdown_rendering_features():
    rendered = render_markdown_to_html(SAMPLE_MARKDOWN)

    assert "<h1" in rendered.body
    assert 'id="demo-report"' in rendered.body
    assert "<table>" in rendered.body
    assert "task-list-item" in rendered.body
    assert "<s>removed</s>" in rendered.body
    assert "footnote" in rendered.body
    assert 'class="highlight"' in rendered.body
    assert 'class="language-python"' in rendered.body
    assert "katex-display" in rendered.body
    assert "katex-html" in rendered.body


def test_softbreaks_render_as_hardbreaks_in_paragraphs_and_lists():
    rendered = render_markdown_to_html(
        "1. first line\n"
        "   same list item\n"
        "2. second line\n"
        "   same second item\n\n"
        "paragraph line\n"
        "soft paragraph line\n"
    )

    assert "first line<br" in rendered.body
    assert "same list item" in rendered.body
    assert "second line<br" in rendered.body
    assert "paragraph line<br" in rendered.body
    assert "soft paragraph line" in rendered.body


def test_obsidian_underscore_emphasis_inside_cjk_text():
    italic_prefix = "\u8fd9\u53c8\u662f\u4e00\u6bb5\u659c\u4f53\u4e2d"
    bold_prefix = "\u8fd9\u53c8\u662f\u4e00\u6bb5\u7c97\u4f53\u4e2d"
    underscore_bold_prefix = "\u8fd9\u4e5f\u662f\u4e00\u6bb5\u7c97\u4f53\u4e2d"
    inner = "\u5305\u542b\u7c97\u4f53"
    italic_inner = "\u5305\u542b\u659c\u4f53"
    suffix = "\u7684\u6587\u5b57"
    rendered = render_markdown_to_html(
        f"*{italic_prefix}__{inner}__{suffix}*\n"
        f"**{bold_prefix}_{italic_inner}_{suffix}**\n"
        f"__{underscore_bold_prefix}_{italic_inner}_{suffix}__\n"
        f"`*{italic_prefix}__{inner}__{suffix}*`\n"
        "$x_i + y_i$\n"
    )

    assert f"<em>{italic_prefix}<strong>{inner}</strong>{suffix}</em>" in rendered.body
    assert f"<strong>{bold_prefix}<em>{italic_inner}</em>{suffix}</strong>" in rendered.body
    assert f"<strong>{underscore_bold_prefix}<em>{italic_inner}</em>{suffix}</strong>" in rendered.body
    assert f"<code>*{italic_prefix}__{inner}__{suffix}*</code>" in rendered.body
    assert "katex" in rendered.body


def test_obsidian_loose_closing_emphasis_markers():
    rendered = render_markdown_to_html(
        "- **Obsidian **\u4e2d\uff0c\u5982\u679c\u60f3\u8ba9\u5f15\u7528\u9000\u56de\u4e00\u5c42\n"
        "- *loose *text\n"
        "- `**literal **`\n"
    )

    assert "<strong>Obsidian</strong> \u4e2d" in rendered.body
    assert "<em>loose</em> text" in rendered.body
    assert "<code>**literal **</code>" in rendered.body


def test_safe_html_kbd_bold_after_regular_bold_text():
    rendered = render_markdown_to_html(
        "**Obsidian** \u4e2d\u7684\u56fe\u7247\u662f\u4ee5**\u53cc\u94fe**\u7684\u683c\u5f0f\u5f15\u7528"
        "\u5728\u76ee\u6807\u7b14\u8bb0\u4e2d\uff0c\u7528 **<kbd>!</kbd>** \u4f7f\u5b83\u53ef\u89c1\n"
        "**Obsidian**\u7684\u56fe\u7247\u8bbe\u7f6e\u5927\u5c0f\u662f\u7528 **<kbd>|</kbd>** \u5206\u9694\n"
        "\u8fd9\u4e2a**<kbd>\u7a7a\u683c</kbd>** \u4e0d\u6253\u4e5f\u6ca1\u4e8b\n"
    )

    assert "<strong><kbd>!</kbd></strong>" in rendered.body
    assert "<strong><kbd>|</kbd></strong>" in rendered.body
    assert "<strong><kbd>\u7a7a\u683c</kbd></strong>" in rendered.body
    assert "**<kbd>\u7a7a\u683c</kbd>**" not in rendered.body
    assert "** <kbd>" not in rendered.body
    assert "用** " not in rendered.body


def test_safe_html_kbd_can_display_backtick_key():
    rendered = render_markdown_to_html(
        "\u8f93\u5165\u4e24\u4e2a **<kbd>`</kbd>** \u53cd\u5f15\u53f7\uff0c\u5728\u4e2d\u95f4\u5199\u4ee3\u7801\u5185\u5bb9\n"
        "Use `<kbd>` literally.\n"
    )

    assert "<strong><kbd>`</kbd></strong>" in rendered.body
    assert "&lt;kbd&gt;`&lt;/kbd&gt;" not in rendered.body
    assert "<code>&lt;kbd&gt;</code>" in rendered.body


def test_obsidian_code_span_emphasis_adjacent_text():
    rendered = render_markdown_to_html(
        "\u4e5f\u53ef\u4ee5\u4f5c\u4e3a**`\u7740\u91cd\u6807\u8bb0`**\uff0c\u7a81\u51fa\u663e\u793a\u5185\u5bb9\n"
        "prefix*`italic code`*suffix\n"
        "prefix***`bold italic code`***suffix\n"
        "prefix_`underscore italic code`_suffix\n"
        "prefix___`underscore bold italic code`___suffix\n"
        r"\**`literal`**" "\n"
        "```md\n"
        "**`literal in fence`**\n"
        "```\n"
    )

    assert "<strong><code>\u7740\u91cd\u6807\u8bb0</code></strong>" in rendered.body
    assert "**<code>\u7740\u91cd\u6807\u8bb0</code>**" not in rendered.body
    assert "<em><code>italic code</code></em>" in rendered.body
    assert "<em><strong><code>bold italic code</code></strong></em>" in rendered.body
    assert "<em><code>underscore italic code</code></em>" in rendered.body
    assert "<em><strong><code>underscore bold italic code</code></strong></em>" in rendered.body
    assert "**<code>literal</code>**" in rendered.body
    assert "<code>literal in fence</code>" not in rendered.body
    assert "**`literal in fence`**" in rendered.body


def test_obsidian_blockquote_marker_line_continues_next_line():
    rendered = render_markdown_to_html(
        ">111\n"
        ">>222\n"
        ">>>333\n"
        ">\n"
        ">>444\n"
        ">>>555\n"
        ">>\n"
        ">666\n"
        ">\n"
        "777\n"
    )

    text_position = rendered.body.find("777")
    assert text_position != -1
    assert rendered.body.rfind("<blockquote>", 0, text_position) != -1
    assert rendered.body.rfind("</blockquote>") > text_position
    assert "</blockquote>\n<p>777</p>" not in rendered.body


def test_obsidian_callouts_get_typed_blockquote_classes():
    rendered = render_markdown_to_html(
        "> [!warning] Risk\n"
        "> Watch out\n\n"
        "> [!tip]\n"
        "> Useful detail\n\n"
        "> Normal quote\n"
    )

    assert '<blockquote class="callout callout-warning" data-callout="warning">' in rendered.body
    assert '<p class="callout-title">Risk</p>' in rendered.body
    assert "<p>Watch out</p>" in rendered.body
    assert '<blockquote class="callout callout-tip" data-callout="tip">' in rendered.body
    assert '<p class="callout-title">Tip</p>' in rendered.body
    assert "[!warning]" not in rendered.body
    assert "[!tip]" not in rendered.body
    assert "<blockquote>\n<p>Normal quote</p>\n</blockquote>" in rendered.body


def test_file_conversion_resolves_bare_image_targets_from_resource_dir(tmp_path):
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    obsidian_image = "Pasted image 20221113221400.png"
    markdown_image = "plain.png"
    (attachments / obsidian_image).write_bytes(b"placeholder")
    (attachments / markdown_image).write_bytes(b"placeholder")
    source = tmp_path / "note.md"
    output = tmp_path / "note.html"
    source.write_text(f"![[{obsidian_image}]]\n\n![plain]({markdown_image})\n", encoding="utf-8")

    result = convert_markdown_file_to_html(source, output_path=output, resource_dir=attachments, overwrite=True)

    html = output.read_text(encoding="utf-8")
    assert 'src="attachments/Pasted%20image%2020221113221400.png"' in html
    assert 'src="attachments/plain.png"' in html
    assert f'alt="{obsidian_image}"' in html
    assert result["resource_dir"] == str(attachments.resolve())


def test_file_conversion_does_not_guess_attachment_directory(tmp_path):
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    image_name = "Pasted image 20221113221400.png"
    (attachments / image_name).write_bytes(b"placeholder")
    source = tmp_path / "note.md"
    output = tmp_path / "note.html"
    source.write_text(f"![[{image_name}]]\n", encoding="utf-8")

    convert_markdown_file_to_html(source, output_path=output, overwrite=True)

    html = output.read_text(encoding="utf-8")
    assert 'src="Pasted%20image%2020221113221400.png"' in html
    assert "attachments/Pasted" not in html


def test_obsidian_deep_tab_indented_list_markers():
    rendered = render_markdown_to_html(
        "- parent\n"
        "  - child\n"
        "    - `image|width`\n"
        "\t\t\t\t\t- resize\n"
        "\t\t\t\t\t\t- `image|widthxheight`\n"
        "\t\t\t\t\t\t\t- detail\n"
        "\t\t\t\t\t- sibling\n"
        "```md\n"
        "\t\t\t\t\t- literal\n"
        "```\n"
    )

    assert "<br />\n- resize" not in rendered.body
    assert "<li>resize\n<ul>" in rendered.body
    assert "<li><code>image|widthxheight</code>\n<ul>" in rendered.body
    assert "<li>sibling</li>" in rendered.body
    assert "<pre" in rendered.body
    assert "literal" in rendered.body


def test_latex_to_mathml():
    mathml = latex_to_mathml(r"\frac{a}{b}", display="inline")

    assert "<math" in mathml
    assert "<mfrac>" in mathml


def test_latex_to_html_math_uses_katex():
    html = latex_to_html_math(r"\frac{a}{b}", display="block")

    assert "katex-display" in html
    assert "katex-html" in html
    assert "mfrac" in html


def test_katex_supports_mhchem_and_array():
    chemistry = render_katex_to_html(r"\ce{CO2 + C -> 2 CO}", display="block")
    array = render_katex_to_html(r"\begin{array}{ll}a&=b\\c&=d\end{array}", display="block")

    assert "katex-display" in chemistry
    assert "mathrm" in chemistry
    assert "katex-display" in array
    assert "mtable" in array


def test_katex_css_rewrites_font_urls_to_package_files():
    css = load_katex_css()

    assert "@font-face" in css
    assert "file:///" in css
    assert "url(fonts/" not in css


def test_katex_context_can_be_closed(monkeypatch):
    katex_core.close_katex_context()

    class FakeMiniRacer:
        def __init__(self):
            self.closed = 0

        def eval(self, source: str) -> None:
            assert isinstance(source, str)

        def call(self, name: str, latex: str, options: dict[str, object]) -> str:
            assert name == "katex.renderToString"
            assert latex == "x"
            assert options["output"] == "html"
            return "<span>x</span>"

        def close(self) -> None:
            self.closed += 1

    fake = FakeMiniRacer()
    monkeypatch.setitem(sys.modules, "py_mini_racer", types.SimpleNamespace(MiniRacer=lambda: fake))
    monkeypatch.setattr(katex_core, "_resource_text", lambda relative_path: "")

    assert katex_core.render_katex_to_html("x") == "<span>x</span>"

    katex_core.close_katex_context()
    katex_core.close_katex_context()

    assert fake.closed == 1


def test_latex_to_html_math_falls_back_to_svg_when_katex_fails(monkeypatch):
    def fail_katex(content: str, *, display: str = "inline") -> str:
        raise RuntimeError("no katex")

    monkeypatch.setattr(markdown_core, "render_katex_to_html", fail_katex)
    html = latex_to_html_math(r"\frac{a}{b}", display="block")

    assert 'class="math-svg math-display"' in html
    assert "data:image/svg+xml;base64," in html


def test_safe_html_subset_and_mark_rendering_do_not_confuse_math():
    rendered = render_markdown_to_html(
        "- **<kbd>$</kbd>** + inline formula marker + **<kbd>$</kbd>**\n\n"
        "<br><br>\n\n"
        "- Writing can ==focus== thinking.\n\n"
        '<iframe src="https://example.test"></iframe>\n'
    )

    assert "<kbd>$</kbd>" in rendered.body
    assert "<br><br>" in rendered.body
    assert "<mark>focus</mark>" in rendered.body
    assert "math-svg" not in rendered.body
    assert "&lt;iframe" in rendered.body


def test_obsidian_wikilink_aliases_render_inside_tables_but_not_code():
    rendered = render_markdown_to_html(
        "### 例2 表格内 单元格中的竖杠\n\n"
        "| 表头1 | 表头2 |\n"
        "|:---:|:---:|\n"
        "| [[#例2 表格内 单元格中的竖杠\\|单元格中的竖杠]] | "
        "[[#例3 不会变成代码的反引号\\|不会变成代码的反引号]] |\n\n"
        "`[[#例2 表格内 单元格中的竖杠\\|单元格中的竖杠]]`\n\n"
        "```md\n"
        "[[#例2 表格内 单元格中的竖杠\\|单元格中的竖杠]]\n"
        "```\n"
    )

    assert 'id="例2-表格内-单元格中的竖杠"' in rendered.body
    example2_href = "#" + quote("例2-表格内-单元格中的竖杠")
    example3_href = "#" + quote("例3-不会变成代码的反引号")
    assert f'<a href="{example2_href}">单元格中的竖杠</a>' in rendered.body
    assert f'<a href="{example3_href}">不会变成代码的反引号</a>' in rendered.body
    assert rendered.body.count("[[#例2") == 2


def test_safe_html_inside_code_span_stays_literal():
    rendered = render_markdown_to_html("Use `<kbd>$</kbd>` literally.\n")

    assert "<code>&lt;kbd&gt;$&lt;/kbd&gt;</code>" in rendered.body
    assert "<kbd>$</kbd>" not in rendered.body


def test_safe_html_with_attributes_stays_escaped():
    rendered = render_markdown_to_html('<mark onclick="alert(1)">bad</mark>\n')

    assert "<mark" not in rendered.body
    assert "</mark>" not in rendered.body
    assert "&lt;mark onclick=" in rendered.body
    assert "&lt;/mark&gt;" in rendered.body


def test_balanced_safe_html_preserves_inner_markdown():
    rendered = render_markdown_to_html(
        "<small>*quiet*</small> and <sup>2</sup>\n"
        "<big>**large**</big>\n"
        "**<big>large</big>**\n"
        "*<small>quiet</small>*\n"
        "***<small>mixed</small>***\n"
        "<kbd>**key**</kbd>\n"
    )

    assert "<small><em>quiet</em></small>" in rendered.body
    assert "<sup>2</sup>" in rendered.body
    assert "<big><strong>large</strong></big>" in rendered.body
    assert "<strong><big>large</big></strong>" in rendered.body
    assert "<em><small>quiet</small></em>" in rendered.body
    assert "<em><strong><small>mixed</small></strong></em>" in rendered.body
    assert "<kbd><strong>key</strong></kbd>" in rendered.body


def test_color_safe_html_preserves_nested_markdown():
    rendered = render_markdown_to_html(
        '<font color="orange">orange</font>\n'
        "**<font color=teal>bold teal</font>**\n"
        "<font color=#1474b4>**blue bold**</font>\n"
        '<strong style="color: rgb(20, 116, 180);">strong blue</strong>\n'
        '***<font color="teal">bold italic teal</font>***\n'
        '<font color="javascript:alert(1)">bad</font>\n'
    )

    assert '<span style="color: orange;">orange</span>' in rendered.body
    assert '<strong><span style="color: teal;">bold teal</span></strong>' in rendered.body
    assert '<span style="color: #1474b4;"><strong>blue bold</strong></span>' in rendered.body
    assert '<strong style="color: rgb(20, 116, 180);">strong blue</strong>' in rendered.body
    assert '<em><strong><span style="color: teal;">bold italic teal</span></strong></em>' in rendered.body
    assert '<span style="color: javascript' not in rendered.body
    assert "&lt;font color=" in rendered.body


def test_safe_html_emphasis_after_bold_label_does_not_cross_markers():
    rendered = render_markdown_to_html(
        "- **效果：** <font color=teal>***This is a bold italic teal text***</font>\n"
    )

    assert "<li><strong>效果：</strong> " in rendered.body
    assert (
        '<span style="color: teal;"><em><strong>This is a bold italic teal text</strong></em></span>'
        in rendered.body
    )
    assert "</strong><em>" not in rendered.body


def test_extended_safe_authoring_html_tags():
    rendered = render_markdown_to_html(
        "<u>under</u> <ins>inserted</ins> <s>old</s> <del>gone</del>\n"
        '<span style="color: #1474b4;">blue</span>\n'
        "<ruby>汉<rp>(</rp><rt>han</rt><rp>)</rp></ruby>\n"
        '<abbr title="Hyper Text">HTML</abbr>\n'
        "soft<wbr>break\n\n"
        "<hr>\n\n"
        '<span onclick="alert(1)">bad</span>\n'
        '<abbr onclick="alert(1)">bad</abbr>\n'
    )

    assert "<u>under</u>" in rendered.body
    assert "<ins>inserted</ins>" in rendered.body
    assert "<s>old</s>" in rendered.body
    assert "<del>gone</del>" in rendered.body
    assert '<span style="color: #1474b4;">blue</span>' in rendered.body
    assert "<ruby>汉<rp>(</rp><rt>han</rt><rp>)</rp></ruby>" in rendered.body
    assert '<abbr title="Hyper Text">HTML</abbr>' in rendered.body
    assert "soft<wbr>break" in rendered.body
    assert "<hr>" in rendered.body
    assert "<p><hr></p>" not in rendered.body
    assert '<span onclick="alert(1)">' not in rendered.body
    assert '<abbr onclick="alert(1)">' not in rendered.body
    assert "&lt;span onclick=" in rendered.body
    assert "&lt;abbr onclick=" in rendered.body


def test_chemistry_formula_falls_back_to_readable_html():
    html = latex_to_html_math(r"\ce{CO2 + C ->[heat] 2 CO}")

    assert "katex" in html
    assert "mathrm" in html
    assert "heat" in html
    assert r"\ce" not in html


def test_block_chemistry_formula_strips_latex_comments(monkeypatch):
    def fail_katex(content: str, *, display: str = "inline") -> str:
        raise RuntimeError("no katex")

    monkeypatch.setattr(markdown_core, "render_katex_to_html", fail_katex)
    html = latex_to_html_math("% chemistry\n" r"\ce{Zn^2+ <=>[a][b] Zn(OH)2 v}", display="block")

    assert "chemistry-display" in html
    assert "% chemistry" not in html
    assert "Zn<sup>2+</sup>" in html
    assert "OH)<sub>2</sub>" in html


def test_array_formula_uses_katex():
    html = latex_to_html_math(
        r"""\begin{array}{lll}
\nabla\times E &=& -\;\frac{\partial{B}}{\partial{t}}
\ \nabla\times H &=& \frac{\partial{D}}{\partial{t}}+J
\ \nabla\cdot D &=& \rho
\ \nabla\cdot B &=& 0
\ \end{array}""",
        display="block",
    )

    assert "katex-display" in html
    assert "mtable" in html


def test_array_formula_falls_back_to_html_table_when_katex_fails(monkeypatch):
    def fail_katex(content: str, *, display: str = "inline") -> str:
        raise RuntimeError("no katex")

    monkeypatch.setattr(markdown_core, "render_katex_to_html", fail_katex)
    html = latex_to_html_math(
        r"""\begin{array}{lll}
\nabla\times E &=& -\;\frac{\partial{B}}{\partial{t}}
\ \nabla\times H &=& \frac{\partial{D}}{\partial{t}}+J
\ \nabla\cdot D &=& \rho
\ \nabla\cdot B &=& 0
\ \end{array}""",
        display="block",
    )

    assert 'class="math-array"' in html
    assert html.count("<tr>") == 4
    assert "data:image/svg+xml;base64," in html


def test_mermaid_fence_uses_diagram_renderer(monkeypatch):
    def fake_render(source: str) -> str:
        assert "graph TD" in source
        return '<figure class="mermaid-diagram"><img src="data:image/svg+xml;base64,abc"></figure>'

    monkeypatch.setattr(markdown_core, "find_mermaid_backend", lambda: object())
    monkeypatch.setattr(markdown_core, "render_mermaid_to_html", fake_render)
    rendered = markdown_core.render_markdown_to_html("```mermaid\ngraph TD; A-->B\n```\n")

    assert "mermaid-diagram" in rendered.body
    assert "data:image/svg+xml;base64,abc" in rendered.body
    assert "language-mermaid" not in rendered.body


def test_mermaid_fence_falls_back_to_code_when_mmdc_is_missing(monkeypatch):
    def fail_render(source: str) -> str:
        raise AssertionError("Mermaid renderer should not run without mmdc")

    monkeypatch.setattr(markdown_core, "find_mermaid_backend", lambda: None)
    monkeypatch.setattr(markdown_core, "render_mermaid_to_html", fail_render)
    rendered = markdown_core.render_markdown_to_html("```mermaid\ngraph TD; A-->B\n```\n")

    assert "mermaid-diagram" not in rendered.body
    assert "language-text" in rendered.body
    assert "graph TD" in rendered.body


def test_mermaid_backend_probe_shape():
    result = inspect_mermaid_backend()

    assert "ok" in result
    assert "backend" in result
    assert "executable" in result
    assert result["requires_network"] is False
    assert "error" in result


def test_mermaid_backend_only_uses_local_mmdc(monkeypatch):
    monkeypatch.setattr(mermaid_core.shutil, "which", lambda name: None)

    result = mermaid_core.inspect_mermaid_backend()

    assert result["ok"] is False
    assert result["backend"] is None
    assert result["optional"] is True
    assert result["requires_network"] is False

    def fake_which(name: str) -> str | None:
        if name == "npx":
            return r"C:\fake\npx.cmd"
        return None

    monkeypatch.setattr(mermaid_core.shutil, "which", fake_which)
    assert mermaid_core.find_mermaid_backend() is None


def test_mermaid_backend_detects_mmdc(monkeypatch):
    monkeypatch.setattr(mermaid_core.shutil, "which", lambda name: r"C:\fake\mmdc.cmd" if name == "mmdc" else None)

    backend = mermaid_core.find_mermaid_backend()

    assert backend is not None
    assert backend.kind == "mmdc"
    assert backend.command == [r"C:\fake\mmdc.cmd"]


def test_mermaid_source_disables_html_labels_by_default():
    source = normalize_mermaid_source("graph TD\n  A[One] --> B[Two]\n")

    assert "htmlLabels" in source
    assert "graph TD" in source


def test_prepare_mermaid_svg_rewrites_foreign_object_labels():
    svg = (
        '<svg viewBox="0 0 100 40">'
        '<g class="label" transform="translate(0, 0)"><rect/>'
        '<foreignObject width="80" height="24"><div><span><p>Node A</p></span></div></foreignObject>'
        "</g></svg>"
    )

    prepared = prepare_mermaid_svg(svg)

    assert "<foreignObject" not in prepared
    assert "<text" in prepared
    assert "Node A" in prepared


def test_raw_html_is_escaped():
    rendered = render_markdown_to_html(SAMPLE_MARKDOWN)

    assert "<script>" not in rendered.body
    assert "&lt;script&gt;" in rendered.body


def test_html_comments_are_hidden_outside_code():
    rendered = render_markdown_to_html(
        "Before\n\n"
        "<!-- hidden comment -->\n\n"
        "After <!-- inline hidden --> text\n\n"
        "<!-- multiline\n"
        "hidden comment -->\n\n"
        "`<!-- code comment -->`\n\n"
        "```md\n"
        "<!-- fenced comment -->\n"
        "```\n"
    )

    assert "hidden comment" not in rendered.body
    assert "After  text" in rendered.body
    assert "<code>&lt;!-- code comment --&gt;</code>" in rendered.body
    assert "&lt;!-- fenced comment --&gt;" in rendered.body


def test_obsidian_comments_are_hidden_outside_code():
    rendered = render_markdown_to_html(
        "Before\n\n"
        "%% hidden comment %%\n\n"
        "After %% inline hidden %% text\n\n"
        "%%\n"
        "hidden comment\n"
        "%%\n\n"
        "`%% code comment %%`\n\n"
        "```md\n"
        "%% fenced comment %%\n"
        "```\n"
        "\\%% escaped comment marker %%\n"
    )

    assert "hidden comment" not in rendered.body
    assert "After  text" in rendered.body
    assert "<code>%% code comment %%</code>" in rendered.body
    assert "%% fenced comment %%" in rendered.body
    assert "% escaped comment marker" in rendered.body


def test_obsidian_yaml_frontmatter_is_hidden_at_document_start():
    rendered = render_markdown_to_html(
        "---\n"
        "created: 2021-08-09 10:18\n"
        "modified: 2022-01-12 21:40\n"
        "aliases: [Markdown tutorial, MD tutorial]\n"
        "tags:\n"
        "  - usage\n"
        "---\n\n"
        "# Title\n\n"
        "Body\n"
    )

    assert "created:" not in rendered.body
    assert "modified:" not in rendered.body
    assert "Markdown tutorial" not in rendered.body
    assert "usage" not in rendered.body
    assert "<hr" not in rendered.body
    assert "<h1" in rendered.body
    assert "Title" in rendered.body


def test_utf8_bom_does_not_break_first_heading():
    rendered = render_markdown_to_html("\ufeff# Title\n\nBody\n")

    assert rendered.title == "Title"
    assert '<h1 id="title">Title</h1>' in rendered.body
    assert "<p># Title</p>" not in rendered.body
    assert "\ufeff" not in rendered.body


def test_public_html_api_is_obsidian_compatible_by_default():
    rendered = markdown_to_html(
        "---\n"
        "created: 2021-08-09 10:18\n"
        "tags:\n"
        "  - usage\n"
        "---\n\n"
        "# Public API\n\n"
        "%% hidden comment %%\n\n"
        "==marked== and [[#Public API|jump]]\n"
    )

    assert "created:" not in rendered.body
    assert "hidden comment" not in rendered.body
    assert "<mark>marked</mark>" in rendered.body
    assert ">jump</a>" in rendered.body


def test_leading_thematic_break_without_yaml_metadata_is_preserved():
    rendered = render_markdown_to_html("---\n\n# Title\n\n---\n\nBody\n")

    assert rendered.body.count("<hr") == 2
    assert "Title" in rendered.body
    assert "Body" in rendered.body


def test_unsafe_html_allows_raw_html_when_requested():
    source = '<div class="note">trusted</div>\n<script>alert(1)</script>\n'

    safe = render_markdown_to_html(source)
    unsafe = render_markdown_to_html(source, unsafe_html=True)

    assert '&lt;div class=&quot;note&quot;&gt;trusted&lt;/div&gt;' in safe.body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in safe.body
    assert '<div class="note">trusted</div>' in unsafe.body
    assert "<script>alert(1)</script>" in unsafe.body


def test_theme_loading():
    css = load_theme_css(DEFAULT_THEME)
    mark_block = css.rsplit("mark {", 1)[1].split("}", 1)[0]
    inline_code_block = css.rsplit("kbd,\ncode {", 1)[1].split("}", 1)[0]
    image_only_block = css.rsplit("p > img:only-child {", 1)[1].split("}", 1)[0]
    math_block = css.rsplit(".math.block,\n.math.amsmath {", 1)[1].split("}", 1)[0]
    math_display_block = css.rsplit(".math-display {", 1)[1].split("}", 1)[0]
    katex_display_block = css.rsplit("main.document .katex-display {", 1)[1].split("}", 1)[0]
    table_block = css.rsplit("table {", 1)[1].split("}", 1)[0]
    table_cell_block = css.rsplit("th,\ntd {", 1)[1].split("}", 1)[0]
    table_last_child_block = css.rsplit("tr > :last-child {", 1)[1].split("}", 1)[0]
    table_last_row_block = css.rsplit("tbody tr:last-child td {", 1)[1].split("}", 1)[0]
    table_top_left_block = css.rsplit("thead tr:first-child th:first-child {", 1)[1].split("}", 1)[0]
    table_bottom_right_block = css.rsplit("tbody tr:last-child td:last-child {", 1)[1].split("}", 1)[0]

    assert "@page" in css
    assert "A4" in css
    assert "kbd,\ncode {" in css
    assert "linear-gradient(180deg" in mark_block
    assert "border-radius: 3px;" in mark_block
    assert "box-decoration-break: clone;" in mark_block
    assert "color: inherit;" in mark_block
    assert "border-radius: 3px;" in inline_code_block
    assert "box-shadow: inset 0 -1px 0 #d7e1ea;" in css
    assert "font-weight: 500;" in css
    assert "strong code,\ncode strong,\nstrong kbd,\nkbd strong {" in css
    assert "font-weight: 800;" in css
    assert "pre code {\n  background: transparent;" in css
    assert "tab-size: 2;" in css
    assert "padding: 0.78em 0.88em 0.82em;" in css
    assert "pre::before {" in css
    assert "radial-gradient(circle at 4px 4px, #ff5f56" in css
    assert "radial-gradient(circle at 16px 4px, #ffbd2e" in css
    assert "radial-gradient(circle at 28px 4px, #27c93f" in css
    assert "width: 32px;" in css
    assert "border-radius: 8px;" in css
    assert "max-height: 230mm;" in css
    assert "object-fit: contain;" in css
    assert "display: block;" in image_only_block
    assert "margin: 1.15em auto 1.25em;" in image_only_block
    assert "break-inside: avoid;" in image_only_block
    assert "margin: 1.15em auto 1.25em;" in math_block
    assert "break-inside: avoid;" in math_block
    assert "margin: 1.15em auto 1.25em;" in math_display_block
    assert "page-break-inside: avoid;" in math_display_block
    assert "margin: 1.15em auto 1.25em;" in katex_display_block
    assert "break-inside: avoid;" in katex_display_block
    assert "box-shadow: none;" in css
    assert "margin-left: -1.35em;" not in css
    assert "blockquote.callout {" in css
    assert ".callout-warning" in css
    assert "border: 1px solid #d7e0ea;" in css
    assert "table-layout: fixed;" in css
    assert "border: 1px solid #cfdae8;" in table_block
    assert "border-radius: 8px;" in table_block
    assert "overflow: hidden;" in table_block
    assert "line-height: 1.35;" in table_cell_block
    assert "padding: 0.38em 0.62em;" in table_cell_block
    assert "vertical-align: middle;" in table_cell_block
    assert "border-right: 0;" in table_last_child_block
    assert "border-bottom: 0;" in table_last_row_block
    assert "border-top-left-radius: 7px;" in table_top_left_block
    assert "border-bottom-right-radius: 7px;" in table_bottom_right_block
    assert "th:first-child,\ntd:first-child {" not in css
    assert "thead th,\ntr:first-child th {" not in css
    assert "break-inside: avoid;" not in table_block
    assert "page-break-inside: avoid;" not in table_block
    assert "thead {\n  display: table-header-group;\n}" in css
    assert "tr {\n  break-inside: avoid;\n  page-break-inside: avoid;\n}" in css
    assert "tbody td strong {\n  color: inherit;" in css
    assert ".mermaid-diagram {" in css
    mermaid_block = css.rsplit(".mermaid-diagram {", 1)[1].split("}", 1)[0]
    assert "background:" not in mermaid_block
    assert "border:" not in mermaid_block
    assert "border-radius:" not in mermaid_block
    assert "margin: 1.15em auto 1.25em;" in mermaid_block
    assert "max-width: 100%;" in mermaid_block
    assert "padding:" not in mermaid_block
    assert "@media screen {" in css
    assert "max-width: 210mm;" in css
    assert "padding: 17mm 15mm;" in css


def test_default_theme_has_single_style_layer():
    css = load_theme_css(DEFAULT_THEME)

    assert "Report-style default theme refinements" not in css
    assert css.count("@page {") == 1
    assert css.count(":root {") == 1

    for selector in (
        "a",
        "table",
        "thead",
        "tfoot",
        "tr",
        "th",
        "pre",
        "pre::before",
        "blockquote",
        ".footnotes",
        ".mermaid-diagram",
    ):
        assert css.count(f"\n{selector} {{") == 1


def test_theme_styles_obsidian_callouts_as_document_components():
    css = load_theme_css(DEFAULT_THEME)
    regular_quote_block = css.rsplit("blockquote {", 1)[1].split("}", 1)[0]
    callout_block = css.rsplit("blockquote.callout {", 1)[1].split("}", 1)[0]

    assert (
        "background: linear-gradient(90deg, #d97706 0, #d97706 4px, "
        "#f7fafc 4px, #f7fafc 100%);"
    ) in regular_quote_block
    assert "border-left:" not in regular_quote_block
    assert "border-radius: 8px;" in regular_quote_block
    assert "padding: 0.58em 0.82em 0.58em 1.05em;" in regular_quote_block
    assert "blockquote.callout {" in css
    assert (
        "background: linear-gradient(90deg, #0f6ea7 0, #0f6ea7 5px, "
        "#f5f9fd 5px, #f5f9fd 100%);"
    ) in callout_block
    assert "border: 1px solid #d6e3ef;" in callout_block
    assert "border-radius: 8px;" in callout_block
    assert "box-shadow: 0 4px 12px rgba(15, 42, 67, 0.05);" in css
    assert "padding: 0.58em 0.82em 0.68em 1.2em;" in css
    assert "blockquote.callout p {\n  margin: 0.24em 0 0;\n}" in css
    assert "border-bottom: 1px solid #c9dff2;" in css
    assert "blockquote.callout .callout-title {" in css
    assert "blockquote.callout .callout-title::before {" in css
    assert "border-radius: 50%;" in css
    assert 'content: "i";' in css
    assert "height: 1.34em;" in css
    assert "width: 1.34em;" in css
    assert ".callout.callout-tip,\n.callout.callout-success,\n.callout.callout-done,\n.callout.callout-check {" in css
    assert "linear-gradient(90deg, #15803d 0, #15803d 5px, #f3fbf6 5px, #f3fbf6 100%);" in css
    assert ".callout.callout-tip .callout-title,\n.callout.callout-success .callout-title" in css
    assert 'content: "+";' in css
    assert ".callout.callout-warning,\n.callout.callout-caution,\n.callout.callout-attention {" in css
    assert "linear-gradient(90deg, #b45309 0, #b45309 5px, #fff8ed 5px, #fff8ed 100%);" in css
    assert ".callout.callout-warning .callout-title,\n.callout.callout-caution .callout-title" in css
    assert 'content: "!";' in css
    assert (
        ".callout.callout-danger,\n.callout.callout-error,\n.callout.callout-fail,\n"
        ".callout.callout-failure,\n.callout.callout-missing {"
    ) in css
    assert "linear-gradient(90deg, #b91c1c 0, #b91c1c 5px, #fff5f5 5px, #fff5f5 100%);" in css
    assert ".callout.callout-question,\n.callout.callout-help,\n.callout.callout-faq {" in css
    assert "linear-gradient(90deg, #6b4fc4 0, #6b4fc4 5px, #f7f5ff 5px, #f7f5ff 100%);" in css
    assert 'content: "?";' in css
    assert ".callout.callout-quote {" in css
    assert "linear-gradient(90deg, #777b82 0, #777b82 5px, #f8f8f6 5px, #f8f8f6 100%);" in css
    assert 'content: "\\"";' in css


def test_available_themes_only_lists_default():
    assert available_themes() == ["default"]


def test_unknown_theme_reports_supported_names():
    with pytest.raises(ValueError) as exc_info:
        load_theme_css("missing")

    message = str(exc_info.value)
    assert "Unknown theme 'missing'" in message
    assert "Supported themes: default" in message


def test_page_header_footer_css_defaults_to_title_and_page_numbers():
    rendered = render_markdown_to_html("# My Report\n\nBody\n")
    page_margin_css = rendered.css.rsplit("@page {", 1)[-1]

    assert "@top-center" in rendered.css
    assert 'content: "My Report";' in rendered.css
    assert page_margin_css.count("vertical-align: middle;") == 2
    assert "@bottom-center" in rendered.css
    assert 'content: "第 " counter(page) " 页 / 共 " counter(pages) " 页";' in rendered.css


def test_page_header_footer_can_be_disabled_or_overridden():
    disabled = render_markdown_to_html(
        "# My Report\n\nBody\n",
        include_page_header=False,
        include_page_footer=False,
    )
    custom = render_markdown_to_html(
        "# My Report\n\nBody\n",
        page_header='Quoted "Title"',
        page_footer="Draft",
        page_numbers=False,
    )

    assert "@top-center" not in disabled.css
    assert "@bottom-center" not in disabled.css
    assert 'content: "Quoted \\"Title\\"";' in custom.css
    assert 'content: "Draft";' in custom.css
    assert "counter(page)" not in custom.css


def test_theme_does_not_emphasize_regular_table_first_column():
    css = load_theme_css(DEFAULT_THEME)

    assert "tbody td:first-child {\n  color: #d11c17;" not in css
    assert "table.math-array tbody td:first-child" in css


def test_theme_uses_visible_italic_and_no_heading_underlines():
    css = load_theme_css(DEFAULT_THEME)

    assert "border-bottom: 4px solid #173b5c" not in css
    assert "border-bottom: 1.5px solid #b8d7ef" not in css
    assert "h1 {\n  color: #173b5c;\n  font-size: 18pt;" in css
    assert "h2 {\n  color: #256f8a;\n  font-size: 16.5pt;" in css
    assert "h3 {\n  color: #9a3f65;\n  font-size: 15pt;" in css
    assert "font-size: 23pt;" not in css
    assert "font-size: 27pt;" not in css
    assert "font-size: 28pt;" not in css
    assert "h4 {\n  color: #5f55a4;\n  font-size: 13.5pt;" in css
    assert "h5 {\n  color: #24765a;\n  font-size: 12.5pt;" in css
    assert "h6 {\n  color: #a15c18;\n  font-size: 11.5pt;" in css
    assert "em {" in css
    assert "font-style: italic;" in css
    assert "font-style: oblique;" not in css
    assert "padding-right: 0.04em;" in css
    assert "transform: skewX(-8deg);" in css
    assert "transform: skewX(-18deg);" not in css
    assert "KaiTi" not in css


def test_custom_css_is_appended_after_theme_and_pygments():
    theme_css = "body { color: black; }"
    custom_css = "body { color: red; }"
    merged = compose_css(theme_css, custom_css)

    assert merged.index(theme_css) < merged.index(".highlight")
    assert merged.index(".highlight") < merged.index(custom_css)


def test_derive_output_path():
    assert derive_output_path("notes/report.md").as_posix().endswith("notes/report.pdf")


def test_derive_html_output_path():
    assert derive_html_output_path("notes/report.md").as_posix().endswith("notes/report.html")


def test_file_html_export_includes_base_href_and_requires_overwrite(tmp_path):
    source = tmp_path / "notes.md"
    output = tmp_path / "preview.html"
    source.write_text("# Preview\n\n![img](assets/a.png)\n", encoding="utf-8")

    result = convert_markdown_file_to_html(source, output_path=output)

    assert result["action"] == "html"
    assert result["output"] == str(output.resolve())
    assert result["base_url"] == str(tmp_path.resolve())
    html = output.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert f'<base href="{tmp_path.resolve().as_uri()}/">' in html
    assert '<h1 id="preview">Preview</h1>' in html

    with pytest.raises(FileExistsError):
        convert_markdown_file_to_html(source, output_path=output)

    overwrite = convert_markdown_file_to_html(source, output_path=output, overwrite=True)
    assert overwrite["file_size"] == output.stat().st_size


def test_existing_output_requires_overwrite(tmp_path):
    source = tmp_path / "input.md"
    output = tmp_path / "input.pdf"
    source.write_text("# Title\n", encoding="utf-8")
    output.write_bytes(b"%PDF-old")

    with pytest.raises(FileExistsError):
        convert_markdown_file(source, output_path=output)


def test_resolve_base_url_defaults_to_source_directory(tmp_path):
    source = tmp_path / "docs" / "input.md"
    source.parent.mkdir()
    source.write_text("# Title\n", encoding="utf-8")

    assert resolve_base_url(None, source) == str(source.resolve().parent)


def test_doctor_json_shape():
    result = doctor.run_doctor()

    assert isinstance(result["ok"], bool)
    assert "python" in result
    assert "packages" in result
    assert "weasyprint" in result["packages"]
    assert "mini-racer" in result["packages"]
    assert "latex2mathml" in result["packages"]
    assert "matplotlib" in result["packages"]
    assert "tools" in result
    assert "mermaid" in result["tools"]
    assert "recommendations" in result


def test_doctor_reports_missing_mini_racer(monkeypatch):
    real_import = importlib.import_module

    def fake_import(name: str):
        if name == "py_mini_racer":
            raise ImportError("missing v8")
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    result = doctor.run_doctor()

    assert result["ok"] is False
    assert result["packages"]["mini-racer"]["ok"] is False
    assert "missing v8" in result["packages"]["mini-racer"]["error"]


def test_doctor_treats_missing_mermaid_as_optional(monkeypatch):
    monkeypatch.setattr(doctor, "_check_python_package", lambda name: {"ok": True, "version": "1.0", "error": None})
    monkeypatch.setattr(doctor, "_inspect_native_libraries", lambda: [])
    monkeypatch.setattr(
        doctor,
        "inspect_mermaid_backend",
        lambda: {
            "ok": False,
            "backend": None,
            "executable": None,
            "requires_network": False,
            "optional": True,
            "error": "`mmdc` was not found on PATH.",
        },
    )

    result = doctor.run_doctor()

    assert result["ok"] is True
    assert result["tools"]["mermaid"]["ok"] is False
    assert any(item.startswith("Optional: install Mermaid") for item in result["recommendations"])


def test_doctor_import_failure_shape(monkeypatch):
    real_import = importlib.import_module

    def fake_import(name: str):
        if name == "weasyprint":
            raise ImportError("missing package")
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    result = doctor.run_doctor()

    assert result["ok"] is False
    assert result["packages"]["weasyprint"]["ok"] is False
    assert "missing package" in result["packages"]["weasyprint"]["error"]
