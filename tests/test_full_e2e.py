from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from mdtopdf import markdown_file_to_html, markdown_file_to_pdf, markdown_to_pdf
from mdtopdf.core.pdf import convert_markdown_file


SAMPLE_MARKDOWN = r"""# Release Notes

This report checks Markdown PDF output.

| Area | Status |
| --- | --- |
| Parser | pass |
| PDF | pass |

- [x] Tables
- [x] Code
- [ ] Follow-up theme work

```python
print("pdf")
```

Footnote reference.[^1]

Inline formula $E = mc^2$ and block formula:

$$
\int_0^1 x^2 dx = \frac{1}{3}
$$

[^1]: Rendered through markdown-it-py.
"""


def _resolve_cli(name: str):
    force = os.environ.get("MDTOPDF_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: python -m pip install -e .")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m mdtopdf")
    return [sys.executable, "-m", "mdtopdf"]


def _assert_pdf(path):
    assert path.exists()
    assert path.stat().st_size > 0
    with path.open("rb") as fh:
        assert fh.read(5) == b"%PDF-"


def _assert_html(path):
    assert path.exists()
    assert path.stat().st_size > 0
    text = path.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    assert '<main class="document">' in text


def test_python_api_generates_real_pdf(tmp_path):
    source = tmp_path / "report.md"
    output = tmp_path / "report.pdf"
    source.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    result = markdown_file_to_pdf(source, output_path=output, overwrite=True)

    assert result["action"] == "convert"
    assert result["title"] == "report"
    assert result["page_header"] == "report"
    _assert_pdf(output)
    print(f"\n  PDF: {output} ({output.stat().st_size:,} bytes)")


def test_python_api_generates_real_html(tmp_path):
    source = tmp_path / "report.md"
    output = tmp_path / "report.html"
    source.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

    result = markdown_file_to_html(source, output_path=output, overwrite=True)

    assert result["action"] == "html"
    assert result["title"] == "report"
    assert result["page_header"] == "report"
    _assert_html(output)
    print(f"\n  HTML: {output} ({output.stat().st_size:,} bytes)")


def test_public_markdown_text_api_generates_obsidian_compatible_pdf(tmp_path):
    output = tmp_path / "api.pdf"
    markdown_text = (
        "---\n"
        "created: 2021-08-09 10:18\n"
        "tags:\n"
        "  - usage\n"
        "---\n\n"
        "# API Report\n\n"
        "%% hidden comment %%\n\n"
        "==marked==\n"
    )

    result = markdown_to_pdf(markdown_text, output, title="API Report", overwrite=True)

    assert result["action"] == "convert"
    assert result["source"] == "markdown_text"
    assert result["title"] == "API Report"
    assert result["page_header"] == "API Report"
    _assert_pdf(output)
    print(f"\n  Public API PDF: {output} ({output.stat().st_size:,} bytes)")


def test_python_api_generates_mermaid_pdf(tmp_path):
    source = tmp_path / "diagram.md"
    output = tmp_path / "diagram.pdf"
    source.write_text(
        """# Mermaid Diagram

```mermaid
graph TD
  A[Markdown] --> B[Mermaid SVG]
  B --> C[WeasyPrint PDF]
```
""",
        encoding="utf-8",
    )

    result = convert_markdown_file(source, output_path=output, overwrite=True)

    assert result["action"] == "convert"
    _assert_pdf(output)
    print(f"\n  Mermaid PDF: {output} ({output.stat().st_size:,} bytes)")


class TestMdtopdfCli:
    CLI_BASE = _resolve_cli("mdtopdf")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
            timeout=90,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert "Convert Markdown files to themed PDFs" in result.stdout

    def test_cli_convert_json(self, tmp_path):
        source = tmp_path / "report.md"
        output = tmp_path / "report.pdf"
        source.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

        result = self._run(
            [
                "convert",
                str(source),
                "-o",
                str(output),
                "--header",
                "Custom Header",
                "--footer",
                "Draft",
                "--theme",
                "default",
                "--overwrite",
                "--json",
            ]
        )
        data = json.loads(result.stdout)

        assert data["ok"] is True
        assert data["action"] == "convert"
        assert data["output"] == str(output.resolve())
        assert data["theme"] == "default"
        assert data["page_header"] == "Custom Header"
        assert data["page_footer"] == "Draft"
        assert data["page_numbers"] is True
        _assert_pdf(output)
        print(f"\n  CLI PDF: {output} ({output.stat().st_size:,} bytes)")

    def test_cli_html_json(self, tmp_path):
        source = tmp_path / "report.md"
        output = tmp_path / "report.html"
        source.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

        result = self._run(
            [
                "html",
                str(source),
                "-o",
                str(output),
                "--overwrite",
                "--json",
            ]
        )
        data = json.loads(result.stdout)

        assert data["ok"] is True
        assert data["action"] == "html"
        assert data["output"] == str(output.resolve())
        assert data["theme"] == "default"
        assert data["page_header"] == "report"
        _assert_html(output)
        print(f"\n  CLI HTML: {output} ({output.stat().st_size:,} bytes)")

    def test_doctor_json(self):
        result = self._run(["doctor", "--json"])
        data = json.loads(result.stdout)

        assert "ok" in data
        assert "packages" in data
        assert "weasyprint" in data["packages"]
        assert "mini-racer" in data["packages"]
        assert "latex2mathml" in data["packages"]
        assert "matplotlib" in data["packages"]
        assert "tools" in data
        assert "mermaid" in data["tools"]
        assert "recommendations" in data

    def test_themes_list_json(self):
        result = self._run(["themes", "list", "--json"])
        data = json.loads(result.stdout)

        assert data["ok"] is True
        assert data["themes"] == ["default"]

    def test_pdfinfo_when_available(self, tmp_path):
        pdfinfo = shutil.which("pdfinfo")
        source = tmp_path / "report.md"
        output = tmp_path / "report.pdf"
        source.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

        self._run(["convert", str(source), "-o", str(output), "--overwrite"])
        _assert_pdf(output)

        if not pdfinfo:
            print("\n  pdfinfo not found; PDF magic bytes verified instead")
            return

        result = subprocess.run(
            [pdfinfo, str(output)],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert "Page size:" in result.stdout
        assert "A4" in result.stdout
        assert "Pages:" in result.stdout
