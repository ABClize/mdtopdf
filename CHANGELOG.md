# Changelog

## 0.3.0 - 2026-09-12

### Changed

- Replace WeasyPrint with one Chromium rendering pipeline for PDF, KaTeX and
  Mermaid. No separate Mermaid CLI, Node.js installation or MSYS2/Pango setup
  is required. Python Playwright and a compatible browser are required.
- Discover installed Chrome, Edge or Chromium when no explicit or managed
  browser is available. Invalid explicit browser paths still fail.
- Preserve CLI command names and Python API entry points. PDF layout and the
  JSON render-method value change with the engine; check custom printing CSS
  and representative documents before upgrading.

### Added

- UTF-8 stdin input with `mdtopdf convert - -o report.pdf --json`, including
  explicit resource bases, overwrite protection and structured usage errors.
- `doctor --render-check --json` to exercise PDF, math and Mermaid rendering.
- Strict conversion/HTML checks, structured browser errors and resource-load
  diagnostics for automated workflows.
- Cross-platform CI, PDFium raster checks and installed-wheel smoke tests.

### Fixed

- Fraction denominators inheriting paragraph last-line alignment.
- Code-block traffic lights disappearing or changing color in PDF viewers.
- Callout icons inheriting text/font alignment and blurred print decorations.
- Relative-resource handling and custom-font diagnostics.

### Upgrade Notes

- Install the new package in a virtual environment, then run
  `mdtopdf doctor --render-check --json`.
- If no compatible browser is found, explicitly install one with
  `python -m playwright install chromium --no-shell`. Conversion never downloads it.
- Linux deployments need browser libraries, document fonts and a non-root user
  with working sandbox support. There is no automatic no-sandbox fallback.
- Use `--strict` when warnings must prevent delivery; successful conversion
  otherwise may include warnings.
- CSS, images and fonts may still access local or remote resources. Document
  JavaScript is blocked during conversion; this is not a resource sandbox.
- There is no WeasyPrint fallback. Keep a separate 0.2.2 environment if you need
  to compare old output during migration.
