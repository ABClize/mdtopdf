# mdtopdf Architecture

## Purpose

`mdtopdf` is an agent-friendly, one-shot Markdown-to-PDF converter for scripts
and local report workflows. Conversion stays local, and the CLI exposes the
parts agents usually need: environment checks through `doctor --json`, optional
HTML previews, PDF export, and JSON results. The 0.x series intentionally avoids
project files, sessions, REPL mode, undo/redo, and preview state. The conversion
pipeline is fixed:

```text
Markdown -> markdown-it-py HTML -> default/custom CSS -> Chromium PDF
```

Pandoc is not used or required.

## Backend

`core/browser.py` owns one isolated headless Chromium session via Python
Playwright. The Markdown parser emits encoded math/Mermaid placeholders;
`vendor/browser-render.js` renders them with bundled KaTeX/mhchem and Mermaid.
PDF conversion defers placeholder resolution until this session, waits for
fonts/images, then prints with CSS page size, margins, backgrounds, tags, and
outline. No separate Mermaid process or second PDF engine is retained.

The synchronous API works inside an existing asyncio loop by running its
private event loop in a worker thread. Each conversion closes its browser in
a finally block and has a bounded timeout. There is no persistent daemon or
personal browser profile.

HTML export returns static rendered math/SVG rather than browser bootstrap
scripts. Plain HTML without math/Mermaid does not need Chromium. File-based
HTML uses the same resource base as PDF; standalone resource URLs may still
refer to files in the installed package.

`core/output.py` writes to a temporary sibling and atomically replaces the
destination only after warning checks pass. Strict failures preserve the old
output. Explicit same-path conversion with overwrite remains supported.
`core/diagnostics.py` isolates warnings per conversion. Invalid KaTeX falls
back to visible source with a warning; a Mermaid render failure is an error,
not a silent code-block fallback.

`doctor --json` checks Python imports, browser executable, bundled render
assets, and fonts. It does not launch Chromium. `--render-check` exercises
PDF, KaTeX, and Mermaid together; a successful probe is not a visual-parity
guarantee. Browser failures preserve the original error, error_code, and hint.
The CLI returns 1 for failed doctor/runtime/strict checks and 2 for usage errors.

Font discovery prefers Fontconfig, otherwise fontTools reads system font
directories and Windows font registrations. CSS font stacks and local font
files are checked statically; remote fonts remain unverified until rendering.
Body/code/emoji fonts are not distributed. Keep the Latin-first theme order,
Linux open fonts, and the existing Windows font stack. See README platform
notes for setup.

Code blocks are protected using CommonMark source maps before Obsidian and
safe-HTML preprocessing. Their contents are restored before final parsing.

## Security Boundary

Chromium's OS sandbox stays enabled. Linux callers need a non-root account
and host/container policies permitting the browser sandbox. Conversion never
installs browsers or turns off the sandbox automatically.

A restrictive CSP is inserted before document content. Only nonce-bearing
package scripts execute; document scripts, frames, objects, and connections
are blocked, including with unsafe HTML. Playwright routes allow the local
document plus image/style/font resources. This is **not** filesystem or network
isolation: allowed resources can read local or remote URLs. Isolate untrusted
documents at the deployment boundary. Exported unsafe HTML remains trusted
content when opened elsewhere.

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
  rendered offline to static KaTeX HTML in Chromium.
  The package vendors KaTeX JavaScript, CSS, and fonts, so users do not need
  Node.js, remote JavaScript, or CDN assets for math rendering.
- Mermaid fenced code blocks rendered to SVG using bundled Mermaid in Chromium

Raw HTML input is disabled by default except for the safe authoring subset. This
keeps untrusted Markdown from being passed straight through to the PDF renderer
as active HTML. Trusted local Markdown can opt into raw HTML with
`convert --unsafe-html`.
This filtering is not a resource sandbox: Chromium can still load local and
remote resources referenced by ordinary Markdown images and CSS. Callers must
provide filesystem and network isolation when rendering untrusted documents.

## Command Surface

- `mdtopdf doctor --json`
  - Checks Python imports, Chromium discovery, bundled Mermaid/KaTeX
    assets, recommended fallback fonts, and returns recommendations for the
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

## Browser Installation

Browser inspection and rendering share one resolver: explicit
`MDTOPDF_BROWSER_EXECUTABLE`, legacy `PUPPETEER_EXECUTABLE_PATH`, installed
Playwright Chromium, then system browser paths. Invalid explicit paths fail;
there is no download or retry with a different browser on launch failure.
If none is found, explicitly run `python -m playwright install chromium --no-shell`.
The CLI's `convert -` reads UTF-8 stdin and calls the existing text-to-PDF API;
it requires an output file and resolves relative resources from the working
directory or `--base-url`. No temporary Markdown file is created.
Linux system dependencies can
be prepared with `python -m playwright install-deps chromium`.
Browser/driver versions should be pinned by the deployment when reproducibility
is required. Old WeasyPrint-specific custom CSS may require adjustment: the
default theme is preserved, but Chromium is not an identical paged-media engine.
