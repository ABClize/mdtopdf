"""One isolated Chromium session for math, diagrams, and paged PDF output."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import escape
from importlib import resources
import os
import platform
import secrets
from pathlib import Path
import tempfile
from urllib.parse import urlparse


BROWSER_ENV = "MDTOPDF_BROWSER_EXECUTABLE"
INSTALL_HINT = "Run python -m playwright install chromium --no-shell during environment setup."


class BrowserRenderError(RuntimeError):
    def __init__(self, message, *, error_code="browser_render_failed", hint=None):
        super().__init__(message)
        self.error_code = error_code
        self.hint = hint or "Run mdtopdf doctor --render-check --json and inspect the original error."


@dataclass
class BrowserResult:
    body: str
    warnings: list[dict]
    version: str


def _execute(coroutine_factory):
    # A synchronous public API must also work when called by an async Agent.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine_factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coroutine_factory())).result()


def _configured_executable():
    return os.environ.get(BROWSER_ENV) or os.environ.get("PUPPETEER_EXECUTABLE_PATH")


def _system_browser_candidates():
    system = platform.system()
    names = ("chrome.exe", "msedge.exe", "chromium.exe") if system == "Windows" else (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
        "microsoft-edge", "microsoft-edge-stable",
    )
    # Ignore relative/empty PATH entries rather than executing a document-local binary.
    for directory in os.get_exec_path():
        if directory and Path(directory).is_absolute():
            for name in names:
                yield Path(directory) / name
    if system == "Windows":
        for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(key)
            if root and Path(root).is_absolute():
                for relative in ("Google/Chrome/Application/chrome.exe",
                                 "Microsoft/Edge/Application/msedge.exe",
                                 "Chromium/Application/chrome.exe"):
                    yield Path(root) / relative
    elif system == "Darwin":
        for root in (Path("/Applications"), Path.home() / "Applications"):
            for name in ("Google Chrome", "Microsoft Edge", "Chromium"):
                yield root / f"{name}.app" / "Contents" / "MacOS" / name
    else:
        for name in names:
            yield Path("/usr/bin") / name
        yield Path("/opt/google/chrome/chrome")
        yield Path("/opt/microsoft/msedge/msedge")


def _is_executable(path):
    return path.is_file() and os.access(path, os.X_OK)


def _resolve_executable(managed_path):
    for name in (BROWSER_ENV, "PUPPETEER_EXECUTABLE_PATH"):
        configured = os.environ.get(name)
        if configured:
            path = Path(configured).expanduser()
            if not _is_executable(path):
                raise BrowserRenderError(
                    "Configured browser executable was not found or is not executable: " + str(path),
                    error_code="browser_missing",
                    hint=f"Correct {name} or remove it to allow automatic discovery. " + INSTALL_HINT,
                )
            return str(path.absolute()), name
    path = Path(managed_path)
    if _is_executable(path):
        return str(path.absolute()), "playwright"
    for path in _system_browser_candidates():
        if _is_executable(path):
            # Keep launcher symlinks intact (for example /snap/bin/chromium).
            return str(path.absolute()), "system"
    raise BrowserRenderError(
        "No installed Chromium, Chrome, or Edge executable was found.",
        error_code="browser_missing",
        hint=INSTALL_HINT + f" Or set {BROWSER_ENV} to an installed recent Chrome/Edge executable.",
    )


def inspect_browser():
    async def inspect():
        from playwright.async_api import async_playwright
        async with async_playwright() as driver:
            path, source = _resolve_executable(driver.chromium.executable_path)
            return {"ok": True, "executable": path, "source": source, "backend": "chromium",
                    "requires_network": False, "optional": False,
                    "error": None,
                    "hint": None}
    try:
        return _execute(inspect)
    except BrowserRenderError as exc:
        return {"ok": False, "backend": "chromium", "executable": _configured_executable(),
                "optional": False, "requires_network": False, "error": str(exc),
                "error_code": exc.error_code, "hint": exc.hint}
    except Exception as exc:
        return {"ok": False, "backend": "chromium", "executable": None, "optional": False,
                "requires_network": False, "error": str(exc),
                "hint": "Install agent-markdown-pdf and its Playwright dependency. " + INSTALL_HINT}


def _failure(exc):
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timeout" in lowered:
        return BrowserRenderError(message or "Browser rendering timed out.", error_code="browser_timeout",
                                  hint="Run doctor --render-check --json; check slow resources or simplify the document.")
    if "no usable sandbox" in lowered or "running as root without --no-sandbox" in lowered:
        return BrowserRenderError(message, error_code="browser_sandbox_unavailable", hint=(
            "Run as a non-root user with working browser sandbox support. Check host/container "
            "user-namespace and AppArmor policies; do not disable the sandbox by default. "
            "An explicitly configured system Chrome may be required on Ubuntu."
        ))
    if "executable doesn't exist" in lowered or "executable was not found" in lowered:
        return BrowserRenderError(message, error_code="browser_missing", hint=INSTALL_HINT)
    return BrowserRenderError(message)


def render_document(html, *, base_url=None, output_path=None, timeout=90):
    async def run():
        return await asyncio.wait_for(_render(html, base_url=base_url, output_path=output_path), timeout)
    try:
        return _execute(run)
    except BrowserRenderError:
        raise
    except Exception as exc:
        raise _failure(exc) from exc


def _base_uri(base_url):
    if base_url is None:
        return Path.cwd().as_uri() + "/"
    value = str(base_url)
    if urlparse(value).scheme in {"http", "https", "file"}:
        return value.rstrip("/") + "/"
    return Path(value).resolve().as_uri() + "/"


async def _render(html, *, base_url, output_path):
    from playwright.async_api import async_playwright

    warnings = []
    def warning(kind, message, **details):
        item = {"type": kind, "message": message, **details}
        if item not in warnings:
            warnings.append(item)

    # Match the old no-document-JavaScript behavior even with --unsafe-html.
    # Images/styles/fonts can still read local or remote resources: not an SSRF sandbox.
    nonce = secrets.token_urlsafe(24)
    policy = (f"default-src 'none'; script-src 'nonce-{nonce}'; connect-src 'none'; "
              "style-src 'unsafe-inline' file: http: https: data:; "
              "img-src file: http: https: data: blob:; font-src file: http: https: data:; "
              "form-action 'none'; frame-src 'none'; object-src 'none'")
    head = (f'<meta http-equiv="Content-Security-Policy" content="{escape(policy, quote=True)}">'
            f'<base href="{escape(_base_uri(base_url), quote=True)}">'
            '<style>html{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style>')
    secured = html.replace("<head>", "<head>" + head, 1)
    with tempfile.TemporaryDirectory(prefix="mdtopdf-browser-") as directory:
        source = Path(directory) / "document.html"
        source.write_text(secured, encoding="utf-8")
        async with async_playwright() as driver:
            executable, source_kind = _resolve_executable(driver.chromium.executable_path)
            options = {"headless": True, "chromium_sandbox": True, "timeout": 30000}
            if source_kind == "playwright":
                options["channel"] = "chromium"
            else:
                options["executable_path"] = executable
            browser = await driver.chromium.launch(**options)
            try:
                context = await browser.new_context(service_workers="block", accept_downloads=False)
                page = await context.new_page()
                page.set_default_timeout(30000)
                page.on("requestfailed", lambda request: warning(
                    "resource_load_failed", "Resource could not be loaded.", url=request.url,
                    error=request.failure,
                ))
                page.on("response", lambda response: warning(
                    "resource_load_failed", "Resource returned an HTTP error.",
                    url=response.url, status=response.status,
                ) if response.status >= 400 else None)
                async def route_request(route):
                    request = route.request
                    if request.resource_type in {"image", "stylesheet", "font"} or request.url == source.as_uri():
                        await route.continue_()
                    else:
                        await route.abort("blockedbyclient")
                await context.route("**/*", route_request)
                await page.emulate_media(media="print")
                await page.goto(source.as_uri(), wait_until="load")
                package = resources.files("mdtopdf")
                if await page.locator("[data-mdtopdf-math]").count():
                    for name in ("katex.min.js", "contrib/mhchem.min.js"):
                        await _load_script(page, package.joinpath("vendor/katex/dist", name), nonce)
                if await page.locator("[data-mdtopdf-mermaid]").count():
                    await _load_script(page, package.joinpath("vendor/mermaid/mermaid.min.js"), nonce)
                diagnostics = await page.evaluate(package.joinpath("vendor/browser-render.js").read_text(encoding="utf-8"))
                warnings.extend(diagnostics)
                await page.evaluate("async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode().catch(() => null))); }")
                missing = await page.locator("img").evaluate_all("images => images.filter(i => !i.naturalWidth).map(i => i.currentSrc || i.src)")
                for url in missing:
                    warning("resource_load_failed", "Image did not decode.", url=url)
                if output_path is not None:
                    await page.pdf(path=str(output_path), prefer_css_page_size=True, print_background=True,
                                   display_header_footer=False, tagged=True, outline=True)
                return BrowserResult(await page.locator("main.document").inner_html(), warnings, browser.version)
            finally:
                await browser.close()


async def _load_script(page, path, nonce):
    await page.evaluate("""({code, nonce}) => {
        const script = document.createElement('script');
        script.nonce = nonce;
        script.textContent = code;
        document.head.appendChild(script);
        script.remove();
    }""", {"code": path.read_text(encoding="utf-8"), "nonce": nonce})
