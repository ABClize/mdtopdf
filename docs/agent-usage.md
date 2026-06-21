# Agent Usage Guide

This page is for agents and automation runners that need to install and use
`mdtopdf` on a new machine.

## Names

| Use case | Name |
| --- | --- |
| PyPI distribution | `agent-markdown-pdf` |
| CLI command | `mdtopdf` |
| Python import package | `mdtopdf` |

Install the PyPI distribution, then call the CLI command:

```shell
python -m pip install agent-markdown-pdf
mdtopdf --version
```

Do not use `mdtopdf` as the PyPI package name; that is not this project.

## Recommended Agent Flow

Start with a machine check:

```shell
mdtopdf doctor --json
```

For a simple conversion:

```shell
mdtopdf convert INPUT.md -o OUTPUT.pdf --overwrite --json
```

When layout needs review before the final PDF:

```shell
mdtopdf html INPUT.md -o preview.html --overwrite --json
mdtopdf convert INPUT.md -o OUTPUT.pdf --overwrite --json
```

## Native Dependencies

`mdtopdf` uses WeasyPrint for PDF output. WeasyPrint needs native Pango, GLib,
and Cairo libraries.

On Linux containers, install the native packages before installing `mdtopdf`.
The repository Dockerfile is a working reference.

On Windows, run:

```powershell
mdtopdf doctor --json
```

If native DLLs are missing, install MSYS2 Pango and point `mdtopdf` to the DLL
directory:

```powershell
pacman -S mingw-w64-x86_64-pango
setx WEASYPRINT_DLL_DIRECTORIES "D:\Environment\msys64\mingw64\bin"
```

The exact MSYS2 path may differ on another machine.

## Docker

Build the image from a checkout:

```shell
docker build -t mdtopdf .
```

Run the CLI inside the container:

```shell
docker run --rm -v "$PWD:/work" mdtopdf doctor --json
docker run --rm -v "$PWD:/work" mdtopdf convert INPUT.md -o OUTPUT.pdf --overwrite --json
```

On PowerShell, use `${PWD}` for the mounted path:

```powershell
docker run --rm -v "${PWD}:/work" mdtopdf doctor --json
```

## Failure Handling

- If `mdtopdf` is not found, install `agent-markdown-pdf`, then retry.
- If PDF conversion fails with a native library error, run `mdtopdf doctor --json`.
- If Mermaid diagrams do not render, install local `mmdc`; Mermaid support is
  optional and never uses Mermaid.ink.
- If an agent only needs a final PDF, skip HTML preview and call `convert --json`
  directly after `doctor --json`.
