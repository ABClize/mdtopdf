---
name: "mdtopdf"
description: "Agent-friendly Markdown-to-PDF CLI with HTML preview, JSON diagnostics, Obsidian-compatible Markdown, KaTeX math, Mermaid support, and Python WeasyPrint output."
---

# mdtopdf

Use `mdtopdf` when an agent needs to turn local Markdown into a PDF without
Pandoc or a remote renderer. It is designed for agent-written reports,
Obsidian-style notes, and technical documents that need a real output file plus
machine-readable command results.

## Agent Workflow

Check the machine first when the environment is new or unknown:

```powershell
mdtopdf doctor --json
```

Use HTML preview when layout matters:

```powershell
mdtopdf html .\input.md -o .\preview.html --overwrite --json
```

Generate the final PDF:

```powershell
mdtopdf convert .\input.md -o .\output.pdf --overwrite --json
```

For simple reports, skip the preview and call `convert --json` directly after
`doctor --json`. In JSON mode, failures return structured data that an agent can
show or act on.

## Requirements

- Python 3.10+
- The installed PyPI package: `python -m pip install agent-markdown-pdf`
- The CLI command installed by that package: `mdtopdf`
- Native WeasyPrint libraries: Pango, GLib, Cairo

The PyPI distribution is `agent-markdown-pdf`. Do not use `mdtopdf` as the PyPI
package name; the command name and distribution name are intentionally different.

On Windows, native libraries are not installed automatically. Run:

```powershell
mdtopdf doctor --json
```

If needed, install MSYS2 Pango and set the DLL directory:

```powershell
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

## Useful Options

- `--theme default`: use the built-in print theme.
- `--css custom.css`: append custom CSS after the selected theme.
- `--title TITLE`: set the HTML/PDF document title.
- `--header TEXT`: set the page header text; by default it uses the input file stem.
- `--footer TEXT`: set footer text before page numbers.
- `--no-header`: disable the page header.
- `--no-footer`: disable the page footer.
- `--no-page-numbers`: disable page numbers in the footer.
- `--base-url PATH_OR_URL`: resolve relative images and links from a path or URL.
- `--resource-dir PATH`: resolve bare image names such as `![[image.png]]` or
  `![](image.png)` from one explicit local directory.
- `--overwrite`: replace an existing output file.
- `--unsafe-html`: allow raw HTML in trusted Markdown input.
- `--json`: return machine-readable output.

## Markdown Support

Markdown supports CommonMark plus tables, task lists, footnotes, fenced code,
Obsidian-style `==highlight==`, Obsidian-style `[[target|alias]]` wikilinks
including table-safe `[[target\|alias]]`, Obsidian-style `%%comment%%`
comments outside code, Obsidian-style `> [!note]` callouts, and a small safe
HTML subset for document authoring.

Markdown supports `$inline$`, `$$block$$`, and common `amsmath` environments for
LaTeX formulas. Formulas render offline through bundled KaTeX assets inside the
Python process with `mini-racer`; users do not need Node.js, remote JavaScript,
or CDN assets.

Mermaid diagrams are supported with fenced `mermaid` code blocks. The CLI
renders them to SVG only through local `mmdc` when available. It does not call
Mermaid.ink or download Mermaid CLI through `npx` during conversion. If `mmdc`
is missing, Mermaid blocks remain highlighted code.

## Python API

The installed package exposes the same Obsidian-compatible pipeline through a
public Python API:

```python
from mdtopdf import markdown_file_to_html, markdown_file_to_pdf, markdown_to_html, markdown_to_pdf
```

Use `markdown_to_html(markdown_text)` for rendered HTML,
`markdown_file_to_html(input_path, output_path=..., ...)` for file-based HTML,
`markdown_to_pdf(markdown_text, output_path, ...)` for Markdown text to PDF, and
`markdown_file_to_pdf(input_path, output_path=..., ...)` for file-based PDF
conversion.

## Agent Guidance

- Prefer `--json` for commands an agent runs.
- Use `doctor --json` before conversion on a new machine or when native library
  state is unknown.
- Use `html` for quick layout checks and `convert` for the final PDF.
- If conversion fails with a WeasyPrint or DLL error, run `doctor --json` and
  use the recommendations field for the next system-level fix.
- Do not look for Pandoc; this CLI uses `markdown-it-py` plus WeasyPrint.
- Version `0.1.0` ships the built-in theme `default`.
