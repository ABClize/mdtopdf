---
name: "mdtopdf"
description: "Convert Markdown to PDF or static HTML with mdtopdf. Use for local document export, Obsidian resources, custom CSS, math, Mermaid, or diagnosing the rendering environment."
---

# mdtopdf

Install package `agent-markdown-pdf`; the command and Python import are `mdtopdf`.

## Setup

```shell
python -m pip install "agent-markdown-pdf>=0.3.0"
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
Microsoft fonts. Pele (for Mermaid syntax) and KaTeX are bundled; no separate mmdc, npm, or
WeasyPrint installation is needed.

This checkout's Pele migration is unreleased; PyPI 0.3.0 still uses Mermaid.js.
Keep `mermaid` / `mmd` fences. Use shared `--mdtopdf-*` palette variables at
`:root` through `--css` to coordinate document and diagram colors, or local
`--pele-*` overrides for diagrams. Mermaid `theme` / `themeVariables` do not apply.
Inspect existing diagrams after migration because Pele has its own layout.
See the README's Pele compatibility section for supported labels and plugins.

## Updates

Update only when requested, using the original environment and installation method.
For pip-installed releases: `python -m pip install --upgrade agent-markdown-pdf`,
then `python -m mdtopdf --version`. Keep pipx/uv tool and source installs under
their original manager/checkout. Do not replace pinned versions during conversion.
For 0.3.0+, rerun `doctor --render-check --json` after an upgrade; follow browser
setup if Playwright needs a new managed browser. There is no `mdtopdf update`.

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

In the unreleased Pele pipeline, diagrams use the configured `@page` geometry;
matching first/left/right styles use the smallest available area before
pagination. On `diagram_text_too_small`, review the PDF and consider wider paper,
larger labels, or splitting the diagram. The default threshold is 8pt;
`--mdtopdf-diagram-min-font-size` on `.mermaid-diagram` adjusts the warning check,
not the font size. `--strict` preserves existing output on these warnings too.

Failures return an error message and, for browser or diagram failures,
`error_code` and `hint`. For `diagram_render_failed`, inspect `error_details`
for the diagram index, excerpt, and available original Markdown/diagram
locations; fix that source block. `renderer_line` / `renderer_column` are Pele's
preprocessed positions and may differ. Use `doctor --render-check --json` after
repairing an environment failure. See the README's Pele section for palette
variables, diagnostic fields, and compatibility limits.
Exit codes: 0 success, 1 runtime/strict failure, 2 invalid arguments.
Images, fonts, and CSS may access local/remote resources: isolate untrusted input.
