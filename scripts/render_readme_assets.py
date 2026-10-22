"""Regenerate README page images and the cover using the current checkout.

Install the editable package with its dev dependencies, then run:
    python scripts/render_readme_assets.py

Uses the normal browser resolver, including MDTOPDF_BROWSER_EXECUTABLE.
Intermediate PDFs/HTML and a render manifest stay under tmp/readme-refresh/.
Review every generated page before committing the assets.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pypdfium2 as pdfium

import mdtopdf
from mdtopdf import markdown_file_to_html, markdown_file_to_pdf
from mdtopdf.core.browser import render_document


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "readme"
WORK = ROOT / "tmp" / "readme-refresh"


def rasterize(source: Path, prefix: str, scale: float) -> list[Path]:
    paths = []
    with pdfium.PdfDocument(source) as pdf:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                try:
                    output = WORK / f"{prefix}-{index + 1}.png"
                    bitmap.to_pil().save(output, optimize=True)
                    paths.append(output)
                finally:
                    bitmap.close()
            finally:
                page.close()
    return paths


def main() -> None:
    if Path(mdtopdf.__file__).resolve().parent != ROOT / "mdtopdf":
        raise SystemExit('Install this checkout first: python -m pip install -e ".[dev]"')
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = {}
    generated = []
    for language in ("cn", "en"):
        stem = f"visual-test-{language}"
        source = ROOT / "examples" / f"{stem}.md"
        markdown_file_to_html(source, output_path=WORK / f"{stem}.html", overwrite=True, strict=True)
        result = markdown_file_to_pdf(source, output_path=WORK / f"{stem}.pdf", overwrite=True, strict=True)
        pages = rasterize(WORK / f"{stem}.pdf", f"pdf-page-{language}", scale=1.5)
        # README tables and the cover reference these six pages explicitly.
        if len(pages) != 6:
            raise RuntimeError(f"{stem} has {len(pages)} pages; update the README gallery before publishing")
        generated.extend(pages)
        manifest[language] = {"pages": len(pages), "render": result}

    cover_html = (ASSETS / "cover.html").read_text(encoding="utf-8")
    cover_pdf = WORK / "cover.pdf"
    cover_result = render_document(cover_html, base_url=WORK, output_path=cover_pdf)
    if cover_result.warnings:
        raise RuntimeError(f"Cover rendering warnings: {cover_result.warnings}")
    cover_pages = rasterize(cover_pdf, "cover", scale=8 / 3)
    if len(cover_pages) != 1:
        raise RuntimeError("The README cover must fit on one page")
    for source in generated:
        shutil.copyfile(source, ASSETS / source.name)
    shutil.copyfile(cover_pages[0], ASSETS / "cover.png")
    manifest["cover"] = {"browser": cover_result.version, "warnings": cover_result.warnings}
    (WORK / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"page_images": len(generated), "cover": str(ASSETS / "cover.png"),
                      "manifest": str(WORK / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
