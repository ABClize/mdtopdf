import asyncio
from pathlib import Path

import pytest

from mdtopdf import markdown_to_html, markdown_to_pdf
from mdtopdf.core import browser
from mdtopdf.core.markdown import render_markdown_to_html


def test_browser_renders_math_mermaid_and_pdf_in_one_session(monkeypatch, tmp_path):
    from mdtopdf.core import output
    calls = []
    real = output.render_document
    def render(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setattr(output, "render_document", render)
    path = tmp_path / "browser.pdf"
    result = markdown_to_pdf("# Browser\n\n$x^2$\n\n```mermaid\ngraph TD; A-->B\n```", path)
    assert path.read_bytes().startswith(b"%PDF-")
    assert result["method"] == "markdown-it-py+chromium"
    assert calls == [1]
    assert not result["warnings"]


def test_html_is_static_after_browser_render():
    result = markdown_to_html("# Formula\n\n$\\ce{2H2 + O2 -> 2H2O}$\n\n```mermaid\ngraph TD; A-->B\n```")
    assert "katex-html" in result.body
    assert "<svg" in result.body
    assert "data-mdtopdf-math" not in result.html
    assert "data-mdtopdf-mermaid" not in result.html
    assert not result.warnings


def test_missing_browser_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setenv(browser.BROWSER_ENV, str(tmp_path / "missing-browser"))
    with pytest.raises(browser.BrowserRenderError) as caught:
        markdown_to_pdf("# Test", tmp_path / "missing.pdf")
    assert caught.value.error_code == "browser_missing"
    assert "install chromium" in caught.value.hint
    assert not (tmp_path / "missing.pdf").exists()


def test_sync_api_works_from_async_agent(tmp_path):
    async def run():
        return markdown_to_pdf("# Async Agent", tmp_path / "async.pdf")
    assert asyncio.run(run())["ok"]


def test_document_scripts_never_execute(tmp_path):
    rendered = render_markdown_to_html(
        '# Safe\n<script>document.querySelector("main").textContent="INJECTED"</script>',
        unsafe_html=True, _defer_browser=True,
    )
    result = browser.render_document(rendered.html)
    assert '<h1 id="safe">Safe</h1>' in result.body


def test_invalid_formula_warns_and_strict_preserves_output(tmp_path):
    output = tmp_path / "keep.pdf"
    output.write_bytes(b"original")
    with pytest.raises(Exception) as caught:
        markdown_to_pdf(r"$\notARealKatexCommand$", output, strict=True, overwrite=True)
    assert any(w["type"] == "math_fallback" for w in caught.value.warnings)
    assert output.read_bytes() == b"original"


def test_html_math_uses_document_resource_base(tmp_path):
    from importlib import resources
    from mdtopdf import markdown_file_to_html
    font = resources.files("mdtopdf").joinpath("vendor/katex/dist/fonts/KaTeX_Main-Regular.woff2")
    (tmp_path / "local.woff2").write_bytes(font.read_bytes())
    source = tmp_path / "report.md"
    source.write_text("# Local font\n\n$x^2$", encoding="utf-8")
    css = tmp_path / "print.css"
    css.write_text('@font-face{font-family:Local;src:url(local.woff2)} h1{font-family:Local}', encoding="utf-8")
    result = markdown_file_to_html(source, custom_css_path=css)
    assert not [w for w in result["warnings"] if w["type"] == "resource_load_failed"]


def test_http_resource_failure_is_reported(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    class MissingResource(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), MissingResource)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        document = render_markdown_to_html(
            '# Font\n<link rel="stylesheet" href="http://127.0.0.1:' + str(port) + '/missing.css">',
            unsafe_html=True, _defer_browser=True,
        )
        result = browser.render_document(document.html)
        assert any(w.get("status") == 404 for w in result.warnings)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
