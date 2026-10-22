"""Diagram source locations survive Markdown and Pele preprocessing."""

from html.parser import HTMLParser
import json

import pytest
from click.testing import CliRunner

from mdtopdf import markdown_to_html, markdown_to_pdf
from mdtopdf.core.diagram_diagnostics import DiagramRenderError
from mdtopdf.core.markdown import render_markdown_to_html
from mdtopdf.core.mermaid import render_mermaid_to_svg
from mdtopdf.mdtopdf_cli import cli


class _DiagramSources(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.lines = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-mdtopdf-mermaid" in attrs:
            self.lines.append(int(attrs["data-mdtopdf-source-line"]))


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_source_lines_survive_frontmatter_comments_and_nested_repeated_fences(newline):
    source = """---
title: Source mapping
---
<!-- A hidden block:
```mermaid
graph TD
A --- B
```
-->

> ```mermaid
> graph TD
> A --- B
> ```

- A nested block:

    ~~~mmd
    graph TD
    A --- B
    ~~~

```mermaid
graph TD
A --- B
```
""".replace("\n", newline)
    rendered = render_markdown_to_html(source, _defer_browser=True)
    # The first repeated block is stripped with its HTML comment. Its identity
    # must not be accidentally reused for the visible blockquote or list.
    assert _DiagramSources(rendered.body).lines == [12, 19, 24]


def test_json_error_identifies_second_nested_diagram_and_original_markdown_line(tmp_path):
    source = """---
title: Diagnostics
---
<!-- Removed comment -->
```mermaid
flowchart TD
 A --> B
```

> ```mmd
> flowchart TD
>  A --> B
>  @bad
> ```
"""
    input_path = tmp_path / "diagrams.md"
    input_path.write_text(source, encoding="utf-8")
    result = CliRunner().invoke(cli, ["html", str(input_path), "--json"])
    assert result.exit_code == 1
    assert not result.stderr
    error = json.loads(result.stdout)
    assert error["error_code"] == "diagram_render_failed"
    assert error["error_type"] == "DiagramRenderError"
    assert "install" not in error["hint"].lower()
    details = error["error_details"]
    assert details["code"] == "syntax"
    assert details["diagram_index"] == 2
    assert details["diagram_type"] == "flowchart"
    assert details["diagram_line"] == 3
    assert details["diagram_column"] == 2
    assert details["source_line"] == 13
    assert "@bad" in details["snippet"]


def test_error_maps_past_diagram_frontmatter_multiline_directive_and_comments():
    source = """# Diagram metadata

```mermaid
---
title: Source map
config:
  flowchart:
    nodeSpacing: 30
---
%%{init: {
  "flowchart": {"curve": "linear"}
}}%%
%% Introductory comment
flowchart TD
 A --> B
 @bad
```
"""
    with pytest.raises(DiagramRenderError) as caught:
        markdown_to_html(source)
    details = caught.value.error_details
    assert details["source_line"] == 16
    assert details["diagram_line"] == 13
    assert details["renderer_line"] != details["diagram_line"]
    assert "@bad" in details["snippet"]


def test_unclosed_diagram_is_anchored_to_end_of_input_and_preserves_pdf(tmp_path):
    target = tmp_path / "keep.pdf"
    target.write_bytes(b"previous valid PDF")
    with pytest.raises(DiagramRenderError) as caught:
        markdown_to_pdf("# Broken\n\n```mermaid\nflowchart LR\n A[Unclosed\n```", target, overwrite=True)
    details = caught.value.error_details
    assert details["at_end"] is True
    assert details["source_line"] == 5
    assert details["diagram_line"] == 2
    assert details["diagram_column"] == len(" A[Unclosed") + 1
    assert details["snippet"].endswith("^")
    assert target.read_bytes() == b"previous valid PDF"
    assert not list(tmp_path.glob(".mdtopdf-*"))


def test_unknown_type_is_actionable_without_inventing_a_source_location():
    with pytest.raises(DiagramRenderError) as caught:
        render_mermaid_to_svg("unknownDiagram\nA --> B")
    details = caught.value.error_details
    assert details["code"] == "unsupported-diagram"
    assert details["diagram_index"] == 1
    assert "diagram_line" not in details
    assert "source_line" not in details
    assert "unknownDiagram" in details["snippet"]


def test_successful_diagrams_remove_source_mapping_metadata():
    result = markdown_to_html("```mermaid\nflowchart TD\n A --> B\n```\n")
    assert "<svg" in result.body
    assert "data-mdtopdf-source" not in result.html
    assert "data-mdtopdf-mermaid" not in result.html


def test_diagram_source_containing_timeout_is_not_a_browser_timeout():
    with pytest.raises(DiagramRenderError) as caught:
        markdown_to_html("```mermaid\nflowchart TD\n @timeout\n```\n")
    assert caught.value.error_code == "diagram_render_failed"
    assert caught.value.error_details["code"] == "syntax"
    assert "@timeout" in caught.value.error_details["snippet"]
