"""Diagnose the installed browser, bundled renderers, and document fonts."""
from __future__ import annotations

import importlib
from importlib import metadata, resources
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mdtopdf.core.browser import BROWSER_ENV, inspect_browser
from mdtopdf.core.fonts import inspect_recommended_font_groups


def run_doctor(*, render_check=False):
    system = platform.system()
    result = {
        "ok": False,
        "platform": {"system": system, "release": platform.release(), "machine": platform.machine()},
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "environment": {name: os.environ.get(name) for name in (
            BROWSER_ENV, "PUPPETEER_EXECUTABLE_PATH", "PLAYWRIGHT_BROWSERS_PATH",
        )},
        "packages": {"playwright": _check_python_package("playwright")},
        "tools": {"browser": inspect_browser()},
        "native_libraries": [],
        "fonts": _inspect_fonts(system),
        "recommendations": [],
    }
    root = resources.files("mdtopdf")
    for name, path in (("mermaid", "vendor/mermaid/mermaid.min.js"), ("katex", "vendor/katex/dist/katex.min.js")):
        exists = root.joinpath(path).is_file()
        result["tools"][name] = {"ok": exists, "backend": "bundled-javascript", "optional": False,
                                 "requires_network": False, "error": None if exists else "Bundled asset is missing."}
    if system == "Linux":
        result["tools"]["fontconfig"] = _inspect_fontconfig()
    result["ok"] = all(info["ok"] for info in result["packages"].values()) and all(
        result["tools"][name]["ok"] for name in ("browser", "mermaid", "katex")
    )
    if render_check:
        result["render_checks"] = _run_render_checks()
        result["ok"] = result["ok"] and all(check["ok"] for check in result["render_checks"].values())
    result["recommendations"] = _recommendations(result)
    return result


def _run_render_checks():
    from mdtopdf.core.browser import render_document
    from mdtopdf.core.markdown import render_markdown_to_html
    try:
        rendered = render_markdown_to_html(
            "# Render check\n\n0123456789 v0.2.2 IT-001\n\n$x^2+1$\n\n```mermaid\ngraph TD; A-->B\n```",
            _defer_browser=True,
        )
        with tempfile.TemporaryDirectory(prefix="mdtopdf-doctor-") as directory:
            path = Path(directory) / "probe.pdf"
            probe = render_document(rendered.html, output_path=path)
            return {
                "pdf": {"ok": path.read_bytes().startswith(b"%PDF-") and not probe.warnings,
                        "file_size": path.stat().st_size, "warnings": probe.warnings, "browser_version": probe.version},
                "mermaid": {"ok": "<svg" in probe.body},
                "katex": {"ok": "katex-html" in probe.body},
            }
    except Exception as exc:
        failure = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        for field in ("error_code", "hint"):
            if getattr(exc, field, None):
                failure[field] = getattr(exc, field)
        return {"pdf": failure}


def _check_python_package(name):
    try:
        importlib.import_module(name)
        return {"ok": True, "version": metadata.version(name), "error": None}
    except Exception as exc:
        return {"ok": False, "version": None, "error": f"{type(exc).__name__}: {exc}"}


def _inspect_fonts(platform_system=None):
    return inspect_recommended_font_groups(platform_system)


def _inspect_fontconfig():
    executable = shutil.which("fc-match")
    result = {"ok": False, "executable": executable, "sample": None, "error": None}
    if executable:
        try:
            proc = subprocess.run([executable, "-f", "%{family}\n", "sans-serif"], check=True,
                                  capture_output=True, text=True, timeout=5)
            result.update(ok=True, sample=proc.stdout.strip())
        except Exception as exc:
            result["error"] = str(exc)
    else:
        result["error"] = "fc-match was not found on PATH."
    return result


def _recommendations(result):
    recommendations = []
    tools = result.get("tools", {})
    if not result.get("packages", {}).get("playwright", {}).get("ok"):
        recommendations.append("Install Python dependencies: python -m pip install agent-markdown-pdf")
    if not tools.get("browser", {}).get("ok"):
        recommendations.append(tools.get("browser", {}).get("hint") or
                               "Install the browser: python -m playwright install chromium --no-shell")
    for name in ("mermaid", "katex"):
        if not tools.get(name, {}).get("ok"):
            recommendations.append(f"The bundled {name} asset is missing; reinstall agent-markdown-pdf.")
    if result.get("platform", {}).get("system") == "Linux":
        if not tools.get("fontconfig", {}).get("ok"):
            recommendations.append("Install fontconfig for font diagnostics: sudo apt-get install fontconfig")
        if not result.get("ok"):
            recommendations.append("If Chromium cannot load system libraries: python -m playwright install-deps chromium")
    fonts = result.get("fonts", {})
    if fonts.get("error"):
        recommendations.append("Font inspection failed; inspect the reported error and verify the PDF visually.")
    for name, group in fonts.get("groups", {}).items():
        if not group.get("ok"):
            preferred = ", ".join(group.get("preferred", group.get("recommended", group.get("missing", []))))
            recommendations.append(f"Provide a {name} font: {preferred}. See the README platform font setup.")
    for name, check in result.get("render_checks", {}).items():
        if not check.get("ok"):
            recommendations.append(check.get("hint") or f"Inspect render_checks.{name} errors and warnings before retrying.")
    return recommendations or ["No action needed."]


def format_doctor_text(result):
    lines = [f"mdtopdf doctor: {'OK' if result.get('ok') else 'NEEDS ATTENTION'}",
             f"Python: {result['python']['version']} ({result['python']['executable']})",
             f"Platform: {result['platform']['system']}"]
    for title, records in (("Packages", result.get("packages", {})), ("Tools", result.get("tools", {})),
                           ("Fonts", result.get("fonts", {}).get("groups", {})),
                           ("Render checks", result.get("render_checks", {}))):
        if records:
            lines.extend(["", title + ":"])
            for name, item in records.items():
                detail = item.get("error") or item.get("executable") or ", ".join(item.get("found", []))
                lines.append(f"  - {name}: {'OK' if item.get('ok') else 'FAIL'} {detail or ''}".rstrip())
    lines.extend(["", "Recommendations:", *[f"  - {item}" for item in result.get("recommendations", [])]])
    return "\n".join(lines)
