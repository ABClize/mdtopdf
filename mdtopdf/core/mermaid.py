"""Bundled Mermaid rendering, without an external CLI or Node installation."""
import base64
from importlib import resources

from mdtopdf.core.browser import render_document


def find_mermaid_backend():
    path = resources.files("mdtopdf").joinpath("vendor/mermaid/mermaid.min.js")
    return path if path.is_file() else None


def inspect_mermaid_backend():
    found = find_mermaid_backend() is not None
    return {"ok": found, "backend": "bundled-javascript", "executable": None,
            "requires_network": False, "optional": False,
            "error": None if found else "Bundled Mermaid asset is missing; reinstall agent-markdown-pdf."}


def render_mermaid_to_html(source: str) -> str:
    from mdtopdf.core.markdown import _build_document, load_theme_css

    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    body = f'<figure class="mermaid-diagram" data-mdtopdf-mermaid="{encoded}"></figure>'
    return render_document(_build_document("Mermaid", body, load_theme_css())).body


def render_mermaid_to_svg(source: str, *, timeout: int = 90) -> str:
    from mdtopdf.core.markdown import _build_document, load_theme_css

    encoded = base64.b64encode(source.encode("utf-8")).decode("ascii")
    body = f'<figure class="mermaid-diagram" data-mdtopdf-mermaid="{encoded}"></figure>'
    result = render_document(_build_document("Mermaid", body, load_theme_css()), timeout=timeout)
    start = result.body.index("<svg")
    end = result.body.rindex("</svg>") + len("</svg>")
    return result.body[start:end]
