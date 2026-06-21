from __future__ import annotations

import atexit
from importlib import resources
import re
from threading import RLock
from typing import Any


_CONTEXT_LOCK = RLock()
_CONTEXT: Any | None = None


def render_katex_to_html(content: str, *, display: str = "inline") -> str:
    latex = content.strip()
    if not latex:
        return ""

    options = {
        "displayMode": display == "block",
        "throwOnError": True,
        "trust": False,
        "strict": "ignore",
        "output": "html",
    }
    with _CONTEXT_LOCK:
        return str(_katex_context().call("katex.renderToString", latex, options))


def load_katex_css() -> str:
    css = _resource_text("dist/katex.min.css")
    fonts_dir = resources.files("mdtopdf").joinpath("vendor", "katex", "dist", "fonts")

    def replace(match: re.Match[str]) -> str:
        font_name = match.group("font")
        font_uri = fonts_dir.joinpath(font_name).as_uri()
        return f"url({font_uri})"

    css = re.sub(r"url\((?:fonts/)?(?P<font>KaTeX_[^)]+)\)", replace, css)
    return css


def _katex_context() -> Any:
    global _CONTEXT
    if _CONTEXT is not None:
        return _CONTEXT

    from py_mini_racer import MiniRacer

    ctx = MiniRacer()
    ctx.eval("var window = this; var self = this; var global = this;")
    ctx.eval(_resource_text("dist/katex.min.js"))
    ctx.eval(_resource_text("dist/contrib/mhchem.min.js"))
    _CONTEXT = ctx
    return _CONTEXT


def close_katex_context() -> None:
    global _CONTEXT
    with _CONTEXT_LOCK:
        ctx = _CONTEXT
        _CONTEXT = None
        if ctx is None:
            return
        close = getattr(ctx, "close", None)
        if callable(close):
            close()


def _resource_text(relative_path: str) -> str:
    path = resources.files("mdtopdf").joinpath("vendor", "katex", *relative_path.split("/"))
    return path.read_text(encoding="utf-8")


atexit.register(close_katex_context)
