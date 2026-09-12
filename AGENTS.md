# Project Agent Notes

## Project Identity

- PyPI distribution: `agent-markdown-pdf`
- CLI command: `mdtopdf`
- Python package: `mdtopdf`
- License: MIT
- Supported Python versions: 3.10 through 3.14
- Public positioning: agent-friendly Markdown-to-PDF CLI with HTML preview and JSON diagnostics.

Keep the CLI name, Python import path, entry point, JSON result fields, and
public API stable unless the user explicitly asks for a breaking change.

## Branch And Release Flow

- Do feature work on `feature/*` branches. Do not commit directly to `main`.
- Merge through PR after CI passes.
- Release versions are controlled by `pyproject.toml`.
- Release tags must be `vX.Y.Z` and must match `pyproject.toml`.
- Publishing is done by GitHub Actions release workflow using PyPI Trusted
  Publishing. Do not add PyPI tokens to repository secrets.
- Do not reuse an existing PyPI version. Use a patch version for compatible
  fixes such as docs, doctor checks, runtime guidance, and rendering stability
  fixes.

## CI Contract

Daily CI lives in `.github/workflows/ci.yml`. It and the release workflow call
`.github/workflows/tests.yml`; platform font setup is shared through
`.github/actions/setup-native/action.yml`.

- Runs on pushes to `main`, pull requests, and manual dispatch.
- Tests Python 3.10, 3.11, 3.12, 3.13, and 3.14.
- Also tests Python 3.12 on Windows and macOS.
- Installs the Linux font baseline and prepares Chromium after installing the package.
- Runs `mdtopdf doctor --render-check --json`.
- Runs `python -m pytest tests/ -q`.
- Builds and checks distributions with `python -m build` and
  `python -m twine check dist/*`.
- Requires real PDF, Mermaid, and KaTeX rendering on every matrix entry.
  Linux uses system Chrome through `MDTOPDF_BROWSER_EXECUTABLE` for its
  AppArmor sandbox profile; Windows/macOS install Playwright Chromium.
- Rasterizes mixed CJK/digit PDFs with PDFium and checks visible digit pixels,
  including page counters. Uploads test PNGs/PDFs for review.
- Installs the built wheel into a clean environment and runs
  `scripts/wheel_smoke.py` outside the checkout.

Release CI lives in `.github/workflows/release.yml`.

- Runs on `v*` tag push.
- Repeats the Python test matrix.
- Verifies the tag matches `pyproject.toml`.
- Builds source and wheel distributions.
- Publishes to PyPI through `pypa/gh-action-pypi-publish@release/v1`.

## Local Verification

Use PowerShell on Windows. Prefer `py` over `python` on this machine.

Before opening a PR or release tag, run:

```powershell
py -m mdtopdf --version
py -m mdtopdf doctor --json
py -m pytest tests\ -q
Remove-Item -Recurse -Force -LiteralPath dist, build, agent_markdown_pdf.egg-info -ErrorAction SilentlyContinue
py -m build
py -m twine check dist\*
git diff --check
```

Only remove `dist`, `build`, or `agent_markdown_pdf.egg-info` after confirming
the command runs inside the repository root. Do not delete unrelated user files.

## Runtime Dependencies

Chromium is the only rendering engine, controlled by Python Playwright.
Resolution order: `MDTOPDF_BROWSER_EXECUTABLE`, legacy `PUPPETEER_EXECUTABLE_PATH`,
installed Playwright Chromium, then system Chrome/Edge/Chromium. Invalid explicit
paths must fail rather than fall back. Doctor and rendering use the same resolver.
Install with `python -m playwright install chromium --no-shell` only if needed.
Linux may need `python -m playwright install-deps chromium`.
There is no separate Node.js, Mermaid CLI, MiniRacer, or WeasyPrint requirement.

Keep browser sandboxing enabled. On Linux use a non-root account and working
user-namespace/AppArmor policies. Do not auto-download on conversion or add an
implicit no-sandbox fallback. Check the README and CI action for font packages.
Document scripts are blocked during conversion, but images/styles/fonts may
still access local/remote resources; this is not a network/filesystem sandbox.

## Font Policy

The default theme uses a PDFium-safe Latin-first body font stack. Do not
casually reorder `mdtopdf/themes/default.css` font stacks.

- Latin fonts must stay before CJK fonts in the body and page-margin stacks so
  ASCII digits, dates, versions, and page counters do not land in CJK font
  subsets that Chrome/PDFium can render invisibly.
- Chinese text still falls back to CJK fonts. In the CJK fallback list,
  Linux should use redistributable open fonts such as `Noto Sans CJK SC`.
- Code blocks prefer `Cascadia Mono` / `Cascadia Code`, then system monospace
  fallbacks.
- Emoji spans use system emoji fonts. Linux should prefer monochrome
  `Noto Emoji`; `Noto Color Emoji` is a fallback pending renderer-specific visual verification.
- `mdtopdf` may reference proprietary system font names in CSS, but must not
  bundle, download, or redistribute Microsoft font files.
- Public Linux environments should use the open-font baseline: Liberation or
  DejaVu for Latin/digits, Noto CJK for Chinese, Cascadia where available for
  code blocks, STIX for math, and monochrome Noto Emoji for emoji where
  available.

`doctor --json` must distinguish runtime support from visual parity. Missing
Linux fonts should recommend installable open packages, not Microsoft YaHei or
Segoe UI Emoji.

## Rendering Checks

For ordinary style changes, use HTML preview first and PDF output as the final
layout check.

For Linux/PDFium issues, a passing text extraction check is not enough. Verify
visual rendering through Chrome/PDFium or `pypdfium2`, especially for:

- ASCII digits in mixed CJK documents
- dates such as `2026-06-22`
- versions such as `0.2.0` and `v1.0`
- identifiers such as `IT-001`
- page headers and footers

## Documentation Rules

- `README.md` is the English GitHub/PyPI long description.
- `README_CN.md` is the Chinese GitHub entry point.
- Keep commands in both READMEs consistent with the real CLI.
- Also maintain `README.es-ES.md` when changing installation or runtime behavior.
- Follow `docs/releasing.md` before a release; keep unreleased features distinct
  from the current PyPI version.
- The bundled skill is `mdtopdf/skills/SKILL.md`; README files should mention
  this path when describing Agent usage.
- Do not add a Dockerfile unless the user explicitly asks for a maintained
  container image. Runtime package snippets are enough for now.

## Scope Control

- Keep changes tightly scoped to the requested behavior.
- Preserve user changes in the working tree.
- Do not refactor adjacent code, rewrite generated vendor files, or regenerate
  README screenshots unless the task requires it.
- Preserve explicit same-path conversion with overwrite. Strict failures must
  not replace existing output; without overwrite, existing files remain protected.
- Add regression tests for fixes and include JSON usage errors, material render
  warnings, nested code blocks, and platform-independent resource resolution.
- `convert -` reads UTF-8 stdin, requires a PDF output path, and uses the working
  directory or `--base-url` for resources. Keep the existing file-input behavior.
- Use `apply_patch` for manual edits.
