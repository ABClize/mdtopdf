from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mdtopdf.core.fonts import inspect_css_font_usage, summarize_font_usage
from mdtopdf.core.markdown import (
    DEFAULT_THEME,
    load_custom_css,
    render_markdown_to_html,
)
from mdtopdf.core.obsidian import build_resource_resolver, resolve_resource_dir
from mdtopdf.core.pdf import resolve_base_url


def derive_html_output_path(input_path: str | Path) -> Path:
    """Return the default HTML preview path for a Markdown input path."""

    path = Path(input_path)
    return path.with_suffix(".html")


def convert_markdown_file_to_html(
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
    """Convert a Markdown file to a standalone Obsidian-compatible HTML file.

    This is the file-based HTML companion to the PDF converter. It uses the same
    Markdown renderer, bundled theme, custom CSS ordering, Obsidian compatibility
    patches, KaTeX math, and Mermaid handling as PDF conversion, then writes the
    complete HTML document to disk. The generated file includes a ``<base>`` tag
    so relative images and links resolve from ``base_url`` or the Markdown file's
    directory when opened directly in a browser.

    Args:
        input_path: Source Markdown file.
        output_path: Optional destination HTML path. When omitted, the input
            suffix is changed to ``.html``.
        theme: Built-in theme name.
        custom_css_path: Optional CSS file appended after built-in styles.
        title: Optional document title. Defaults to the input filename stem.
        base_url: Base directory or URL for resolving relative images and links.
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
    """

    source = Path(input_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Input Markdown file not found: {source}")
    if not source.is_file():
        raise IsADirectoryError(f"Input path is not a file: {source}")

    output = Path(output_path).expanduser() if output_path else derive_html_output_path(source)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output HTML already exists: {output}. Use --overwrite to replace it.")

    markdown_text = source.read_text(encoding="utf-8")
    custom_css = load_custom_css(str(custom_css_path)) if custom_css_path else None
    resolved_page_header = page_header if page_header is not None else source.stem
    html_base_url = resolve_base_url(base_url, source)
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
        obsidian_embed_resolver=build_resource_resolver(html_base_url, source, resolved_resource_dir),
    )
    font_usage = inspect_css_font_usage(rendered.css, document_text=markdown_text)

    html = _inject_base_href(rendered.html, _base_href(html_base_url))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")

    effective_header = resolved_page_header if include_page_header else None
    effective_footer = page_footer if include_page_footer else None
    return {
        "ok": True,
        "action": "html",
        "input": str(source.resolve()),
        "output": str(output.resolve()),
        "file_size": output.stat().st_size,
        "theme": theme,
        "title": rendered.title,
        "base_url": html_base_url,
        "resource_dir": str(resolved_resource_dir) if resolved_resource_dir else None,
        "unsafe_html": unsafe_html,
        "page_header": effective_header,
        "page_footer": effective_footer,
        "page_numbers": bool(include_page_footer and page_numbers),
        "font_check": summarize_font_usage(font_usage),
        "warnings": font_usage.get("warnings", []),
        "method": "markdown-it-py+html",
    }


def _base_href(resolved_base_url: str) -> str:
    parsed = urlparse(resolved_base_url)
    if parsed.scheme in {"http", "https"}:
        return resolved_base_url.rstrip("/") + "/"
    if parsed.scheme == "file":
        return resolved_base_url.rstrip("/") + "/"
    return Path(resolved_base_url).resolve().as_uri().rstrip("/") + "/"


def _inject_base_href(html: str, href: str) -> str:
    base_tag = f'  <base href="{escape(href, quote=True)}">\n'
    return html.replace('  <meta charset="utf-8">\n', f'  <meta charset="utf-8">\n{base_tag}', 1)
