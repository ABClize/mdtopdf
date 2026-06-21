"""Public Obsidian-compatible Markdown conversion API.

These functions are the supported import surface for Python callers. They use
the same pipeline as the CLI: markdown-it-py parsing, Obsidian compatibility
preprocessing, safe HTML filtering, KaTeX math, Mermaid diagrams, theme CSS, and
WeasyPrint PDF output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mdtopdf.core.doctor import add_weasyprint_dll_directories
from mdtopdf.core.fonts import inspect_css_font_usage, summarize_font_usage
from mdtopdf.core.html import convert_markdown_file_to_html
from mdtopdf.core.markdown import DEFAULT_THEME, RenderedHTML, render_markdown_to_html
from mdtopdf.core.obsidian import build_resource_resolver, resolve_resource_dir
from mdtopdf.core.pdf import convert_markdown_file


def markdown_to_html(
    markdown_text: str,
    *,
    title: str | None = None,
    theme: str = DEFAULT_THEME,
    custom_css: str | None = None,
    unsafe_html: bool = False,
    resource_dir: str | Path | None = None,
    page_header: str | None = None,
    page_footer: str | None = None,
    include_page_header: bool = True,
    include_page_footer: bool = True,
    page_numbers: bool = True,
) -> RenderedHTML:
    """Convert Markdown text to a complete Obsidian-compatible HTML document.

    Args:
        markdown_text: Source Markdown text.
        title: Optional document title. When omitted, the first level-one
            heading is used; otherwise the fallback title is "Markdown Document".
        theme: Built-in theme name. The v1 package includes ``default``.
        custom_css: Raw CSS appended after the built-in theme, KaTeX, Pygments,
            and page margin CSS.
        unsafe_html: Allow arbitrary raw HTML in the Markdown source. The
            default is safer and only keeps a small allowed HTML subset.
        resource_dir: Optional local directory used to resolve bare image names.
        page_header: Header text for paged output. Defaults to the resolved
            document title when headers are enabled.
        page_footer: Optional footer text for paged output.
        include_page_header: Whether to include page header CSS.
        include_page_footer: Whether to include page footer CSS.
        page_numbers: Whether the footer includes the current page number.

    Returns:
        A ``RenderedHTML`` object containing the resolved title, body HTML,
        combined CSS, and full HTML document.
    """

    resolved_resource_dir = resolve_resource_dir(resource_dir)
    synthetic_source = Path.cwd() / "markdown.md"
    return render_markdown_to_html(
        markdown_text,
        title=title,
        theme=theme,
        custom_css=custom_css,
        unsafe_html=unsafe_html,
        obsidian_embed_resolver=build_resource_resolver(None, synthetic_source, resolved_resource_dir),
        page_header=page_header,
        page_footer=page_footer,
        include_page_header=include_page_header,
        include_page_footer=include_page_footer,
        page_numbers=page_numbers,
    )


def markdown_to_pdf(
    markdown_text: str,
    output_path: str | Path,
    *,
    title: str | None = None,
    theme: str = DEFAULT_THEME,
    custom_css: str | None = None,
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
    """Convert Markdown text to an Obsidian-compatible PDF file.

    Args:
        markdown_text: Source Markdown text.
        output_path: Destination PDF path.
        title: Optional document title passed through to HTML rendering.
        theme: Built-in theme name. The v1 package includes ``default``.
        custom_css: Raw CSS appended after built-in rendering CSS.
        base_url: Base directory or URL used by WeasyPrint to resolve relative
            image, stylesheet, and link targets.
        resource_dir: Optional local directory used to resolve bare image names.
        overwrite: Replace an existing output file when true.
        unsafe_html: Allow arbitrary raw HTML in the Markdown source.
        page_header: Header text for paged output. Defaults to the resolved
            document title when headers are enabled.
        page_footer: Optional footer text for paged output.
        include_page_header: Whether to include page header CSS.
        include_page_footer: Whether to include page footer CSS.
        page_numbers: Whether the footer includes the current page number.

    Returns:
        A JSON-serializable result dictionary matching the CLI ``--json`` shape.

    Raises:
        FileExistsError: If ``output_path`` exists and ``overwrite`` is false.
        RuntimeError: If WeasyPrint or its native dependencies cannot load.
    """

    output = Path(output_path).expanduser()
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output PDF already exists: {output}. Use overwrite=True to replace it.")

    pdf_base_url = _resolve_base_url(base_url)
    resolved_resource_dir = resolve_resource_dir(resource_dir)
    synthetic_source = Path.cwd() / "markdown.md"
    rendered = render_markdown_to_html(
        markdown_text,
        title=title,
        theme=theme,
        custom_css=custom_css,
        unsafe_html=unsafe_html,
        obsidian_embed_resolver=build_resource_resolver(
            pdf_base_url,
            synthetic_source,
            resolved_resource_dir,
        ),
        page_header=page_header,
        page_footer=page_footer,
        include_page_header=include_page_header,
        include_page_footer=include_page_footer,
        page_numbers=page_numbers,
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
    effective_header = (
        page_header if page_header is not None else rendered.title
    ) if include_page_header else None
    effective_footer = page_footer if include_page_footer else None
    return {
        "ok": True,
        "action": "convert",
        "source": "markdown_text",
        "input": None,
        "output": str(output.resolve()),
        "file_size": output.stat().st_size,
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


def markdown_file_to_pdf(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Convert a Markdown file to an Obsidian-compatible PDF file.

    This is the import-friendly alias for ``convert_markdown_file``. It accepts
    the same arguments as the file-based core converter, including
    ``input_path``, ``output_path``, ``custom_css_path``, ``base_url``,
    ``resource_dir``, and ``overwrite``.
    """

    return convert_markdown_file(*args, **kwargs)


def markdown_file_to_html(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Convert a Markdown file to an Obsidian-compatible HTML file.

    This is the import-friendly alias for ``convert_markdown_file_to_html``. It
    accepts the same arguments, including ``input_path``, ``output_path``,
    ``custom_css_path``, ``base_url``, ``resource_dir``, and ``overwrite``.
    """

    return convert_markdown_file_to_html(*args, **kwargs)


def _resolve_base_url(base_url: str | Path | None) -> str | None:
    """Normalize a caller-provided base URL or local filesystem path."""

    if base_url is None:
        return None

    value = str(base_url)
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "file"}:
        return value
    return str(Path(value).expanduser().resolve())
