"""Bundled KaTeX resources and standalone browser rendering."""
from importlib import resources
import re


def render_katex_to_html(content: str, *, display: str = "inline") -> str:
    from mdtopdf.core.browser import render_document
    from mdtopdf.core.markdown import _build_document, latex_to_html_math

    html = _build_document("Formula", latex_to_html_math(content, display=display), load_katex_css())
    result = render_document(html)
    if result.warnings:
        raise ValueError(result.warnings[0]["message"])
    return result.body


def load_katex_css() -> str:
    css = _resource_text("dist/katex.min.css")
    fonts_dir = resources.files("mdtopdf").joinpath("vendor", "katex", "dist", "fonts")

    def replace(match: re.Match[str]) -> str:
        font_name = match.group("font")
        font_uri = fonts_dir.joinpath(font_name).as_uri()
        return f"url({font_uri})"

    css = re.sub(r"url\((?:fonts/)?(?P<font>KaTeX_[^)]+)\)", replace, css)
    return css



def _resource_text(relative_path: str) -> str:
    return resources.files("mdtopdf").joinpath("vendor", "katex", relative_path).read_text(encoding="utf-8")
