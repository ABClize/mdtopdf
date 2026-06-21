from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mdtopdf.core.doctor import add_weasyprint_dll_directories
from mdtopdf.core.fonts import inspect_css_font_usage, summarize_font_usage
from mdtopdf.core.markdown import (
    DEFAULT_THEME,
    load_custom_css,
    render_markdown_to_html,
)
from mdtopdf.core.obsidian import build_resource_resolver, resolve_resource_dir


def derive_output_path(input_path: str | Path) -> Path:
    """Return the default PDF path for a Markdown input path."""

    path = Path(input_path)
    return path.with_suffix(".pdf")


def convert_markdown_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    theme: str = DEFAULT_THEME,
    custom_css_path: str | Path | None = None,
    title: str | None = None,
    base_url: str | Path | None = None,
    resource_dir: str | Path | None = None,
    overwrite: bool = False,
    unsafe_html: bool = False,
    page_header: str | None = None,
    page_footer: str | None = None,
    include_page_header: bool = True,
    include_page_footer: bool = True,
    page_numbers: bool = True,
) -> dict[str, Any]:
    """Convert a Markdown file to PDF using the package rendering pipeline.

    The file-based converter is the implementation behind the public CLI and
    ``markdown_file_to_pdf`` helper. It reads UTF-8 Markdown, applies the
    Obsidian-compatible Markdown-to-HTML renderer, resolves relative assets from
    ``base_url`` or the input file's directory, and writes the final PDF with
    WeasyPrint.

    Args:
        input_path: Source Markdown file.
        output_path: Optional destination PDF path. When omitted, the input
            suffix is changed to ``.pdf``.
        theme: Built-in theme name.
        custom_css_path: Optional CSS file appended after built-in styles.
        title: Optional document title. Defaults to the input filename stem.
        base_url: Base directory or URL for resolving relative assets.
        resource_dir: Optional local directory used to resolve bare image names.
        overwrite: Replace an existing output file when true.
        unsafe_html: Allow arbitrary raw HTML in the Markdown source.
        page_header: Header text. Defaults to the input filename stem.
        page_footer: Optional footer text.
        include_page_header: Whether to include page header CSS.
        include_page_footer: Whether to include page footer CSS.
        page_numbers: Whether the footer includes the current page number.

    Returns:
        A JSON-serializable result dictionary matching the CLI ``--json`` shape.

    Raises:
        FileNotFoundError: If ``input_path`` does not exist.
        IsADirectoryError: If ``input_path`` is a directory.
        FileExistsError: If the output exists and ``overwrite`` is false.
        RuntimeError: If WeasyPrint or its native dependencies cannot load.
    """

    source = Path(input_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Input Markdown file not found: {source}")
    if not source.is_file():
        raise IsADirectoryError(f"Input path is not a file: {source}")

    output = Path(output_path).expanduser() if output_path else derive_output_path(source)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output PDF already exists: {output}. Use --overwrite to replace it.")

    markdown_text = source.read_text(encoding="utf-8")
    custom_css = load_custom_css(str(custom_css_path)) if custom_css_path else None
    resolved_page_header = page_header if page_header is not None else source.stem
    pdf_base_url = resolve_base_url(base_url, source)
    resolved_resource_dir = resolve_resource_dir(resource_dir)
    rendered = render_markdown_to_html(
        markdown_text,
        title=title or source.stem,
        theme=theme,
        custom_css=custom_css,
        unsafe_html=unsafe_html,
        page_header=resolved_page_header,
        page_footer=page_footer,
        include_page_header=include_page_header,
        include_page_footer=include_page_footer,
        page_numbers=page_numbers,
        obsidian_embed_resolver=build_resource_resolver(pdf_base_url, source, resolved_resource_dir),
    )
    font_usage = inspect_css_font_usage(rendered.css, document_text=markdown_text)

    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        add_weasyprint_dll_directories()
        from weasyprint import HTML
    except Exception as exc:
        raise RuntimeError(
            "WeasyPrint could not be imported or initialized. Run "
            "`mdtopdf doctor` for native library diagnostics."
        ) from exc

    HTML(string=rendered.html, base_url=pdf_base_url).write_pdf(str(output))
    file_size = output.stat().st_size
    effective_header = resolved_page_header if include_page_header else None
    effective_footer = page_footer if include_page_footer else None
    return {
        "ok": True,
        "action": "convert",
        "input": str(source.resolve()),
        "output": str(output.resolve()),
        "file_size": file_size,
        "theme": theme,
        "title": rendered.title,
        "base_url": pdf_base_url,
        "resource_dir": str(resolved_resource_dir) if resolved_resource_dir else None,
        "unsafe_html": unsafe_html,
        "page_header": effective_header,
        "page_footer": effective_footer,
        "page_numbers": bool(include_page_footer and page_numbers),
        "font_check": summarize_font_usage(font_usage),
        "warnings": font_usage.get("warnings", []),
        "method": "markdown-it-py+weasyprint",
    }


def resolve_base_url(base_url: str | Path | None, source: Path) -> str:
    """Resolve the effective WeasyPrint base URL for a Markdown source file."""

    if base_url is None:
        return str(source.resolve().parent)

    value = str(base_url)
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "file"}:
        return value
    return str(Path(value).expanduser().resolve())
