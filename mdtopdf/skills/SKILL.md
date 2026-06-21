---
name: "mdtopdf"
description: "Convert Markdown files to themed PDFs using markdown-it-py and Python WeasyPrint."
---

# mdtopdf

Use `mdtopdf` when you need a scriptable Markdown to PDF conversion
tool that does not depend on Pandoc.

## Requirements

- Python 3.10+
- The installed `mdtopdf` Python package
- Native WeasyPrint libraries: Pango, GLib, Cairo

On Windows, native libraries are not installed automatically. Run:

```powershell
mdtopdf doctor
```

If needed, install MSYS2 Pango and set the DLL directory:

```powershell
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

## Commands

### Convert

```powershell
mdtopdf convert .\input.md -o .\output.pdf --overwrite
```

### HTML Preview

```powershell
mdtopdf html .\input.md -o .\preview.html --overwrite
```

Use this for fast browser-based style checks. It runs the same Markdown,
Obsidian compatibility, math, Mermaid, theme, and custom CSS pipeline as PDF
conversion, but writes standalone HTML instead of calling WeasyPrint.

Useful options:

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

Markdown supports CommonMark plus tables, task lists, footnotes, fenced code,
Obsidian-style `==highlight==`, Obsidian-style `[[target|alias]]` wikilinks
including table-safe `[[target\|alias]]`, Obsidian-style `%%comment%%`
comments outside code, Obsidian-style `> [!note]` callouts, and a small safe
HTML subset for document authoring:
`<br>`, `<kbd>`, `<big>`, `<small>`, `<sup>`, `<sub>`,
`<mark>`, `<strong>`, `<em>`, `<b>`, `<i>`, `<u>`, `<s>`, `<del>`, `<ins>`,
`<span>`, `<ruby>`, `<rt>`, `<rp>`, `<abbr>`, `<hr>`, and `<wbr>`. Legacy
`<font color="...">` is converted to safe color-only `<span>` output, and
color-only styles on text-formatting tags are preserved. Other raw HTML stays
escaped by default. HTML comments outside code are hidden instead of printed.
For trusted local Markdown, pass `--unsafe-html` to allow raw HTML through.

Markdown supports `$inline$`, `$$block$$`, and common `amsmath` environments for
LaTeX formulas. The CLI renders formulas offline through bundled KaTeX assets
inside the Python process with `mini-racer`; users do not need Node.js, remote
JavaScript, or CDN assets. SVG, MathML, chemistry HTML, and array-table rendering
remain fallbacks for unsupported TeX.

Mermaid diagrams are supported with fenced `mermaid` code blocks. The CLI renders
them to SVG only through local `mmdc` when available. It does not call
Mermaid.ink or download `@mermaid-js/mermaid-cli` through `npx` during
conversion. If `mmdc` is missing, Mermaid blocks remain highlighted code.

`--base-url` and `--resource-dir` have different jobs. `--base-url` is passed to
the HTML/PDF renderer as the base path for relative resources. `--resource-dir`
is a Markdown preprocessing hint for bare image names only; it does not search
recursively and does not guess Obsidian attachment folder names.

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

### Doctor

```powershell
mdtopdf doctor --json
```

Use this before conversion when diagnosing WeasyPrint installation problems. The
JSON includes package import status, `WEASYPRINT_DLL_DIRECTORIES`, Windows DLL
probes, and recommendations.

### Themes

```powershell
mdtopdf themes list --json
```

Version 1 ships `default`.

## Agent Guidance

- Prefer `--json` for automation.
- Use `html` for fast style preview and `convert` for final PDF verification.
- If `convert` fails with a WeasyPrint or DLL error, run `doctor --json` and use
  the recommendations field to explain the next system-level fix.
- Do not look for Pandoc; this CLI intentionally uses `markdown-it-py` plus
  WeasyPrint.
