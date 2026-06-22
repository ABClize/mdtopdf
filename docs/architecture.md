# mdtopdf Architecture

## Purpose

`mdtopdf` is an agent-friendly, one-shot Markdown-to-PDF converter for scripts
and local report workflows. Conversion stays local, and the CLI exposes the
parts agents usually need: environment checks through `doctor --json`, optional
HTML previews, PDF export, and JSON results. The 0.x series intentionally avoids
project files, sessions, REPL mode, undo/redo, and preview state. The conversion
pipeline is fixed:

```text
Markdown -> markdown-it-py HTML -> default/custom CSS -> WeasyPrint PDF
```

Pandoc is not used or required.

## Backend

The rendering backend is the Python `weasyprint` package. WeasyPrint itself
still depends on native libraries for text layout and drawing, including Pango,
GLib, and Cairo. Those native libraries are not bundled by this package and are
not installed automatically on Windows.

The CLI provides `doctor --json` so callers can detect whether Python
dependencies, native libraries, recommended fallback fonts, and the optional
Mermaid renderer are available before attempting a conversion.
Conversion also checks the final CSS font stacks after theme and custom CSS are
combined. Missing fonts are surfaced as warnings in text output and as
structured `warnings` entries in JSON results; they do not stop PDF generation.

The default theme uses a PDFium-safe Latin-first body font stack. Latin fonts
come before CJK fonts so ASCII digits, dates, versions, and page counters are
not embedded into CJK font subsets that some Chrome/PDFium renderers display
incorrectly. Chinese text still falls back to the CJK side of the stack, where
Microsoft YaHei is the first preferred CJK font. If it is not installed, the
CSS stack falls back to PingFang SC, Noto Sans SC / Noto Sans CJK SC /
Source Han Sans SC, and other available CJK fonts. Code blocks prefer Cascadia
Mono / Cascadia Code before Consolas and other monospace fallbacks. Emoji spans
prefer Segoe UI Emoji on every platform, including Linux, then fall back to
Apple Color Emoji, Noto Emoji, Noto Color Emoji, and other installed emoji
fonts. Color rendering in PDFs depends on the WeasyPrint/Pango/Cairo stack and
the PDF viewer.

These body, code, and emoji fonts are not bundled in the Python wheel. Linux
containers should provide the preferred fonts themselves when they need closer
Windows-like Chinese/code typography, or install usable open-font fallbacks such
as fontconfig, Noto CJK, Liberation/DejaVu, and Cascadia Code where available.

## Markdown Support

The parser is `markdown-it-py` with selected plugins:

- CommonMark baseline
- Tables
- Strikethrough
- Task lists
- Footnotes
- Heading anchors
- Fenced code blocks with Pygments highlighting
- Obsidian-style `==highlight==` marks
- Obsidian-style `[[target|alias]]` wikilinks, including table-safe
  `[[target\|alias]]` aliases
- Obsidian-style `%%comment%%` comments outside code are hidden
- Safe authoring HTML subset: `<br>`, `<kbd>`, `<big>`, `<small>`, `<sup>`,
  `<sub>`, `<mark>`, `<strong>`, `<em>`, `<b>`, `<i>`, `<u>`, `<s>`,
  `<del>`, `<ins>`, `<span>`, `<ruby>`, `<rt>`, `<rp>`, `<abbr>`, `<hr>`,
  and `<wbr>`. Legacy `<font color="...">` is converted to safe color-only
  `<span>` output, and color-only styles on text-formatting tags are preserved.
  HTML comments outside code are hidden instead of printed.
- LaTeX math formulas via `mdit-py-plugins` dollar math and amsmath plugins,
  rendered offline to static KaTeX HTML with the Python `mini-racer` package.
  The package vendors KaTeX JavaScript, CSS, and fonts, so users do not need
  Node.js, remote JavaScript, or CDN assets for math rendering.
- Mermaid fenced code blocks rendered to SVG only through local Mermaid CLI
  (`mmdc`); when `mmdc` is missing, Mermaid blocks remain highlighted code

Raw HTML input is disabled by default except for the safe authoring subset. This
keeps untrusted Markdown from being passed straight through to the PDF renderer
as active HTML. Trusted local Markdown can opt into raw HTML with
`convert --unsafe-html`.

## Command Surface

- `mdtopdf doctor --json`
  - Checks Python imports, WeasyPrint native libraries, optional Mermaid
    support, recommended fallback fonts, and returns recommendations for the
    caller.
- `mdtopdf html INPUT.md -o OUTPUT.html [--json] [--unsafe-html]`
  - Uses the same Markdown, Obsidian compatibility, math, Mermaid, theme, and
    custom CSS pipeline as PDF conversion.
  - Writes standalone HTML for fast browser style preview before final PDF
    verification.
- `mdtopdf convert INPUT.md -o OUTPUT.pdf [--json] [--unsafe-html]`
  - Adds a page header and footer by default. The header uses the input file
    stem, and the footer shows page numbers.
  - Use `--theme default` for the built-in theme.
  - Use `--header TEXT`, `--footer TEXT`, `--no-header`, `--no-footer`, and
    `--no-page-numbers` to control page furniture.
  - Use `--base-url PATH_OR_URL` to set the renderer's base path for relative
    resources already present in the generated HTML.
  - Use `--resource-dir PATH` to resolve bare image names such as
    `![[image.png]]` or `![](image.png)` from one explicit local directory.
- `mdtopdf themes list --json`

Every command supports JSON output through either the top-level `--json` flag or
the command-local `--json` flag.

`--resource-dir` is intentionally explicit. The CLI does not read Obsidian vault
settings and does not guess folder names such as `attachments`; callers pass the
resource folder when they want bare image names resolved from a separate
directory.

## Python API Surface

The public Python API is exposed from `mdtopdf` and is Obsidian-compatible by
default:

- `markdown_to_html(markdown_text, ...)`
- `markdown_file_to_html(input_path, output_path=..., ...)`
- `markdown_to_pdf(markdown_text, output_path, ...)`
- `markdown_file_to_pdf(input_path, output_path=..., ...)`

These API functions use the same Markdown pipeline as the CLI, including
frontmatter hiding, Obsidian comments, wikilinks, emphasis compatibility, safe
HTML handling, Obsidian callouts, KaTeX math, Mermaid diagrams, and the selected
PDF theme.

## Windows Native Dependency Notes

On Windows, a typical MSYS2 setup is:

```powershell
winget install MSYS2.MSYS2
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

The CLI does not run these commands automatically. `doctor --json` reports the
current environment and suggests fixes when native libraries are missing.
