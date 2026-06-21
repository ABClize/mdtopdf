---
name: "mdtopdf"
description: "Use when an agent needs to install or run mdtopdf: an agent-friendly Markdown-to-PDF CLI with JSON diagnostics, HTML preview, Obsidian-compatible Markdown, local KaTeX math, optional local Mermaid rendering, and WeasyPrint environment checks."
---

# mdtopdf

Use this skill to turn local Markdown into a local PDF with the `mdtopdf` CLI.
Prefer the CLI over the Python API unless the user explicitly asks for code
integration.

## Names

| Purpose | Name |
| --- | --- |
| PyPI distribution | `agent-markdown-pdf` |
| CLI command | `mdtopdf` |
| Python import | `mdtopdf` |

Install the package when the command is missing:

```powershell
python -m pip install agent-markdown-pdf
```

## Workflow

Check a new or unknown machine first:

```powershell
mdtopdf doctor --json
```

Generate a PDF:

```powershell
mdtopdf convert .\input.md -o .\output.pdf --overwrite --json
```

Use HTML preview only when layout needs debugging:

```powershell
mdtopdf html .\input.md -o .\preview.html --overwrite --json
mdtopdf convert .\input.md -o .\output.pdf --overwrite --json
```

## Resource Paths

- Use `--base-url PATH_OR_URL` when the Markdown contains relative images or links.
- Use `--resource-dir PATH` for Obsidian-style image names such as `![[image.png]]`.
- Use `--css custom.css` when the user provides print CSS.
- Use `--unsafe-html` only for trusted local Markdown.

## Environment Fixes

`mdtopdf` uses WeasyPrint, so PDF output needs native Pango, GLib, and Cairo
libraries.

On Windows, run `mdtopdf doctor --json` before guessing. If the JSON output says
native DLLs are missing, install MSYS2 Pango and set the DLL directory for that
machine, for example:

```powershell
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

The exact MSYS2 path may differ.

On Linux containers, install the native WeasyPrint packages before installing
`agent-markdown-pdf`. If working from this repository, the `Dockerfile` is the
reference container setup.

## Failure Handling

- Prefer `--json` so failures are structured.
- If conversion fails with a WeasyPrint, Pango, GLib, Cairo, or DLL error, run
  `mdtopdf doctor --json` and follow its recommendations.
- If Mermaid diagrams do not render, check whether local `mmdc` is installed.
  Mermaid is optional; `mdtopdf` does not call Mermaid.ink or download Mermaid
  CLI during conversion.
- Do not look for Pandoc; this CLI uses `markdown-it-py` and WeasyPrint.
- Report the exact command, JSON error, and output path when handing results
  back to the user.
