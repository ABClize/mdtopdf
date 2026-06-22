---
name: "mdtopdf"
description: "Install and run mdtopdf, an agent-friendly Markdown-to-PDF CLI. Use when converting Markdown to PDF or HTML, checking WeasyPrint/mdtopdf runtime health, using Obsidian-style resources, custom CSS, KaTeX, Mermaid, fonts, or JSON diagnostics."
---

# mdtopdf

## Names

- PyPI package: `agent-markdown-pdf`
- CLI command: `mdtopdf`
- Python import: `mdtopdf`

## Basic Flow

Install or upgrade if the command is missing:

```shell
python -m pip install -U agent-markdown-pdf
```

Check the runtime before converting on a new machine:

```shell
mdtopdf doctor --json
```

Convert Markdown to PDF:

```shell
mdtopdf convert INPUT.md -o OUTPUT.pdf --overwrite --json
```

Use HTML preview only when layout needs debugging:

```shell
mdtopdf html INPUT.md -o preview.html --overwrite --json
mdtopdf convert INPUT.md -o OUTPUT.pdf --overwrite --json
```

## Useful Options

- `--base-url PATH_OR_URL`: resolve relative images and links.
- `--resource-dir PATH`: resolve Obsidian-style image names such as `![[image.png]]`.
- `--css print.css`: apply custom print CSS.
- `--unsafe-html`: allow raw HTML only for trusted local Markdown.
- `--json`: prefer this for agent workflows.

## Environment

`mdtopdf` uses WeasyPrint. If PDF export fails, run:

```shell
mdtopdf doctor --json
```

Windows usually needs MSYS2 Pango/GLib/Cairo DLLs:

```powershell
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

Linux containers need native libraries and fonts:

```shell
apt-get update
apt-get install -y --no-install-recommends \
  fontconfig \
  libcairo2 \
  libffi-dev \
  libgdk-pixbuf-2.0-0 \
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  shared-mime-info \
  fonts-liberation \
  fonts-dejavu-core \
  fonts-noto-cjk \
  fonts-stix
fc-cache -f
```

For emoji-heavy documents on Linux, prefer a monochrome emoji font such as
Noto Emoji. `fonts-noto-color-emoji` is a fallback, but it can render too small
or misaligned in PDF viewers.

Install optional support only when needed:

```shell
npm install -g @mermaid-js/mermaid-cli
```

Use Cascadia Code for closer default code-block styling when available:

```shell
apt-get install -y --no-install-recommends fonts-cascadia-code
```

## Failure Handling

- Read JSON errors first; do not guess from stderr alone.
- If conversion fails with WeasyPrint, Pango, GLib, Cairo, or DLL errors, fix the items reported by `doctor --json`.
- If images are missing, add `--base-url` or `--resource-dir`.
- If Mermaid diagrams do not render, install local `mmdc`; `mdtopdf` does not call Mermaid.ink or auto-download Mermaid CLI.
- If CJK text renders as boxes, install a CJK font such as Noto CJK or provide the intended system font.
- If digits disappear in Chrome/PDFium output, verify the runtime has Latin fonts such as Liberation Sans or DejaVu Sans and render a PDFium screenshot to confirm.
- Do not look for Pandoc; this CLI uses `markdown-it-py` and WeasyPrint.
