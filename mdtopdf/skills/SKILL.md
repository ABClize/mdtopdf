---
name: "mdtopdf"
description: "Convert Markdown to PDF or static HTML with mdtopdf. Use for local document export, Obsidian resources, custom CSS, math, Mermaid, or diagnosing the rendering environment."
---

# mdtopdf

Install package `agent-markdown-pdf`; the command and Python import are `mdtopdf`.

## Setup

This guide targets 0.3.0 (in preparation), not the published 0.2.x renderer.
Until release, install the development branch shown in the README.

```shell
python -m pip install -U agent-markdown-pdf
mdtopdf doctor --render-check --json
```

Browser selection: `MDTOPDF_BROWSER_EXECUTABLE`, legacy `PUPPETEER_EXECUTABLE_PATH`,
installed Playwright Chromium, then system Chrome/Edge/Chromium. Invalid explicit
paths fail without fallback. If none is found, install with
`python -m playwright install chromium --no-shell` during setup.
Linux may also need `python -m playwright install-deps chromium`. Run as a
non-root user with browser sandbox support. Do not disable the sandbox or
install browsers during conversion retries.

Fonts come from the environment. On Linux use Liberation/DejaVu for Latin,
Noto Sans CJK SC for Chinese, and Cascadia or an available monospace font for
code. Follow the README for emoji and platform details. Do not download
Microsoft fonts. Mermaid and KaTeX are bundled; no separate mmdc, npm, or
WeasyPrint installation is needed.

## Convert

```shell
mdtopdf convert INPUT.md -o OUTPUT.pdf --json
```

For piped UTF-8 Markdown, use `mdtopdf convert - -o OUTPUT.pdf --json`.
Output is required; relative assets use the working directory or `--base-url`.
Use `--title` to replace the default `stdin` title/header. Empty input fails.
In Windows PowerShell 5.1, set `$OutputEncoding = [System.Text.UTF8Encoding]::new($false)`
before piping non-ASCII text. The `html` command still takes a file path.

Add `--overwrite` only when replacing the output is intended. It also allows
input and output to be the same file. Read `warnings` even when `ok` is true.
Use `--strict` to reject warnings without replacing an existing output.

- `--css print.css`: custom styles and font-family/@font-face rules.
- `--base-url PATH_OR_URL`: base for relative images, fonts, and CSS resources.
- `--resource-dir PATH`: lookup directory for bare image names/Obsidian embeds.
- `--title TEXT`, `--header TEXT`, `--footer TEXT`: document metadata/page chrome.
- `--no-header`, `--no-footer`: remove page chrome.
- `--unsafe-html`: trusted raw HTML only; conversion does not execute document JS.

For layout debugging, run `mdtopdf html INPUT.md -o preview.html --json`.
Math and Mermaid are already rendered in the exported HTML; plain HTML export
does not verify image loading. Inspect the final PDF for pagination and glyphs.

Failures return an error message and, for browser failures, `error_code` and
`hint`. Use `doctor --render-check --json` after repairing the environment.
Exit codes: 0 success, 1 runtime/strict failure, 2 invalid arguments.
Images, fonts, and CSS may access local/remote resources: isolate untrusted input.
