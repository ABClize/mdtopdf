<h1 align="center">mdtopdf: Agent-friendly Markdown-to-PDF CLI</h1>

<p align="center">
  <strong>Agents write Markdown. People need PDFs. mdtopdf handles the step in between.</strong><br>
  Local rendering, HTML preview, and JSON diagnostics give agents and scripts a stable document output path.
</p>

<p align="center">
  <a href="https://github.com/ABClize/mdtopdf/blob/main/README_CN.md">中文文档</a>
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Quick_Start-2_min-blue?style=for-the-badge" alt="Quick Start"></a>
  <a href="#agent-workflow"><img src="https://img.shields.io/badge/Agent_Friendly-JSON_Output-green?style=for-the-badge" alt="Agent Friendly"></a>
  <a href="#visual-output"><img src="https://img.shields.io/badge/PDF_Pages-Rendered-purple?style=for-the-badge" alt="Rendered PDF pages"></a>
  <a href="https://pypi.org/project/mdtopdf/"><img src="https://img.shields.io/pypi/v/mdtopdf.svg?style=for-the-badge" alt="PyPI version"></a>
  <a href="https://github.com/ABClize/mdtopdf/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/pypi/pyversions/mdtopdf.svg" alt="Python versions">
  <img src="https://img.shields.io/badge/output-JSON_%2B_Human-blueviolet" alt="JSON and human output">
  <img src="https://img.shields.io/badge/backend-WeasyPrint-2f855a" alt="WeasyPrint backend">
  <img src="https://img.shields.io/badge/status-alpha-f59e0b" alt="Alpha status">
</p>

**One command** gives agents a controlled Markdown-to-PDF path.

<p align="center">
  <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/cover.png" alt="mdtopdf cover" width="900">
</p>

---

## Why it works for agents

Agents are good at writing Markdown. The problem is the handoff: PDFs exported
through ad hoc paths rarely share the same style. `mdtopdf` gives the user a
command-line interface where the style can be defined up front.

- **Agent-friendly** - `mdtopdf --help` is an interface description an agent can read.
- **JSON when it matters** - conversion, HTML preview, environment checks, and theme listing can return machine-readable output.
- **Local files in, local files out** - no browser dependency, no upload step, no remote rendering service.
- **More than plain Markdown** - Obsidian links, highlights, frontmatter, comments, and callouts are rendered.

## Quick start

Install from PyPI:

```shell
python -m pip install mdtopdf
```

Check the machine:

```shell
mdtopdf doctor --json
```

Convert a file:

```shell
mdtopdf convert report.md -o report.pdf --overwrite
```

Try the bundled visual test document:

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e .[dev]
mdtopdf html examples/visual-test-en.md -o visual-test-en.html --overwrite
mdtopdf convert examples/visual-test-en.md -o visual-test-en.pdf --overwrite --json
```

The same visual test is also available in Chinese at
`examples/visual-test-cn.md`.

## Agent workflow

```shell
mdtopdf doctor --json
mdtopdf convert report.md -o report.pdf --overwrite --json
```

Use HTML preview when layout needs a quick look:

```shell
mdtopdf html report.md -o report.html --overwrite --json
mdtopdf convert report.md -o report.pdf --overwrite --json
```

`convert --json` returns the input path, output path, file size, theme, and
render method. If conversion fails in JSON mode, the error is structured enough
for an agent to show the command, explain the likely cause, and retry after a
fix.

## Visual output

The gallery below is rendered from the final PDF produced by
`examples/visual-test-en.md`. It shows the actual pages an agent can hand back
to a user: headings, callouts, tables, code, math, images, Mermaid, and
pagination.

| Page 1 | Page 2 |
| --- | --- |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-1.png" alt="PDF page 1" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-2.png" alt="PDF page 2" width="420"> |
| Page 3 | Page 4 |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-3.png" alt="PDF page 3" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-4.png" alt="PDF page 4" width="420"> |
| Page 5 | Page 6 |
| <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-5.png" alt="PDF page 5" width="420"> | <img src="https://raw.githubusercontent.com/ABClize/mdtopdf/main/assets/readme/pdf-page-en-6.png" alt="PDF page 6" width="420"> |

## How it works

```text
Markdown -> markdown-it-py HTML -> theme/custom CSS -> WeasyPrint PDF
```

Mermaid rendering is optional. If a local `mmdc` command exists, Mermaid blocks
render to SVG. If it is missing, conversion still succeeds and Mermaid blocks
remain visible as highlighted code.

## Features

| Feature | Notes |
| --- | --- |
| JSON output | `--json` is available for conversion, HTML preview, doctor, and theme listing. |
| Environment checks | `doctor --json` checks Python imports, native WeasyPrint libraries, Windows DLL paths, and Mermaid availability. |
| Local rendering | Markdown, CSS, math, Mermaid SVG generation, and PDF export stay on the machine. |
| HTML preview | Generate standalone HTML before PDF export for fast visual inspection. |
| Obsidian compatibility | Wikilinks, aliases, frontmatter hiding, comments, highlights, and typed callouts. |
| Document Markdown | Tables, task lists, footnotes, heading anchors, fenced code, and Pygments highlighting. |
| KaTeX math | Inline and block TeX render with bundled KaTeX assets, without a CDN. |
| Safe HTML default | Common inline document tags are allowed; unsafe raw HTML stays escaped unless opted in. |
| Python API | Convert Markdown strings or files from your own code. |

## Commands

Render a PDF:

```shell
mdtopdf convert report.md -o report.pdf
mdtopdf convert report.md -o report.pdf --overwrite
```

Preview HTML:

```shell
mdtopdf html report.md -o report.html --overwrite
```

Set document metadata and page chrome:

```shell
mdtopdf convert report.md -o report.pdf --title "Report"
mdtopdf convert report.md -o report.pdf --header "Report" --footer "Draft"
mdtopdf convert report.md -o report.pdf --no-header --no-footer
```

Use extra CSS or resource lookup paths:

```shell
mdtopdf convert report.md -o report.pdf --css print.css
mdtopdf convert report.md -o report.pdf --base-url assets
mdtopdf convert report.md -o report.pdf --resource-dir attachments
```

Return JSON:

```shell
mdtopdf --json convert report.md -o report.pdf --overwrite
mdtopdf doctor --json
mdtopdf themes list --json
```

Allow raw HTML only for trusted local Markdown:

```shell
mdtopdf convert trusted.md -o trusted.pdf --unsafe-html
```

## Python API

```python
from mdtopdf import (
    markdown_file_to_html,
    markdown_file_to_pdf,
    markdown_to_html,
    markdown_to_pdf,
)

rendered = markdown_to_html("# Report\n\n==highlight==")
print(rendered.html)

markdown_to_pdf("# Report\n\nBody", "report.pdf", title="Report", overwrite=True)
markdown_file_to_html("report.md", output_path="report.html", overwrite=True)
markdown_file_to_pdf("report.md", output_path="report.pdf", overwrite=True)
```

## Markdown support

`mdtopdf` supports:

- CommonMark
- Tables
- Strikethrough
- Task lists
- Footnotes
- Heading anchors
- Fenced code blocks with Pygments highlighting
- Obsidian-style `==highlight==` marks
- Obsidian-style `[[target|alias]]` wikilinks
- Obsidian-style `%%comment%%` comments outside code
- Obsidian/YAML frontmatter hiding at the start of the file
- Obsidian-style callouts such as `> [!note] Title`
- Safe inline HTML tags such as `<br>`, `<kbd>`, `<mark>`, `<sup>`, and `<sub>`
- TeX math through `$inline$`, `$$block$$`, and common `amsmath` environments
- Mermaid diagrams through local `mmdc`, when installed

Raw HTML is disabled by default except for the safe subset above. For trusted
local Markdown, pass `--unsafe-html`.

## Mermaid diagrams

Install a persistent local renderer:

```shell
npm install -g @mermaid-js/mermaid-cli
```

`mdtopdf` does not call Mermaid.ink and does not download Mermaid CLI through
`npx` during conversion. Run `mdtopdf doctor --json` to check whether Mermaid
rendering is available.

## Platform notes

`mdtopdf` requires Python 3.10+ and installs its Python dependencies from PyPI:
`click`, `markdown-it-py`, `mdit-py-plugins`, `pygments`, `latex2mathml`,
`matplotlib`, `mini-racer`, and `weasyprint`.

WeasyPrint also needs native libraries such as Pango, GLib, and Cairo. Linux
and macOS package managers usually provide them through system packages.

On Windows, install the native libraries separately. A common MSYS2 setup is:

```powershell
winget install MSYS2.MSYS2
```

Then install Pango from an MSYS2 MINGW64 shell:

```shell
pacman -S mingw-w64-x86_64-pango
```

Finally, point WeasyPrint at the DLL directory from PowerShell. Adjust the path
if MSYS2 is installed somewhere else:

```powershell
setx WEASYPRINT_DLL_DIRECTORIES "C:\msys64\mingw64\bin"
```

Run this after installation:

```shell
mdtopdf doctor --json
```

## Development

```shell
git clone https://github.com/ABClize/mdtopdf.git
cd mdtopdf
python -m pip install -e .[dev]
python -m pytest tests/ -q
```

Build and check the package:

```shell
python -m build
python -m twine check dist/*
```

## License

Apache-2.0. Bundled KaTeX assets are distributed under the MIT license; see
`mdtopdf/vendor/katex/LICENSE`.
