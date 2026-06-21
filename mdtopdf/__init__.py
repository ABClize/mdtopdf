"""Markdown to PDF conversion with Obsidian-compatible defaults.

Import ``markdown_to_html`` for Markdown text to HTML,
``markdown_file_to_html`` for file-based HTML output, ``markdown_to_pdf`` for
converting Markdown text directly to PDF, or ``markdown_file_to_pdf`` for
file-based PDF conversion. The public helpers use the same rendering path as the
``mdtopdf`` command.
"""

from mdtopdf.api import (
    markdown_file_to_html,
    markdown_file_to_pdf,
    markdown_to_html,
    markdown_to_pdf,
)
from mdtopdf.core.doctor import run_doctor
from mdtopdf.core.html import convert_markdown_file_to_html, derive_html_output_path
from mdtopdf.core.markdown import RenderedHTML, available_themes
from mdtopdf.core.pdf import convert_markdown_file, derive_output_path

__version__ = "0.1.0"

__all__ = [
    "RenderedHTML",
    "__version__",
    "available_themes",
    "convert_markdown_file_to_html",
    "convert_markdown_file",
    "derive_html_output_path",
    "derive_output_path",
    "markdown_file_to_html",
    "markdown_file_to_pdf",
    "markdown_to_html",
    "markdown_to_pdf",
    "run_doctor",
]
