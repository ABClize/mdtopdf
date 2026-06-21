from __future__ import annotations

from dataclasses import dataclass
from html import escape, unescape
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


class MermaidRenderError(RuntimeError):
    """Raised when Mermaid CLI rendering is unavailable or fails."""


@dataclass(frozen=True)
class MermaidBackend:
    kind: str
    command: list[str]
    executable: str | None


def find_mermaid_backend() -> MermaidBackend | None:
    mmdc = shutil.which("mmdc")
    if mmdc:
        return MermaidBackend(kind="mmdc", command=[mmdc], executable=mmdc)
    return None


def inspect_mermaid_backend() -> dict[str, Any]:
    backend = find_mermaid_backend()
    if backend is None:
        return {
            "ok": False,
            "backend": None,
            "executable": None,
            "requires_network": False,
            "optional": True,
            "error": "`mmdc` was not found on PATH; Mermaid code blocks will remain highlighted code.",
        }
    return {
        "ok": True,
        "backend": backend.kind,
        "executable": backend.executable,
        "requires_network": False,
        "optional": True,
        "error": None,
    }


def render_mermaid_to_html(source: str) -> str:
    svg = prepare_mermaid_svg(render_mermaid_to_svg(source))
    label = _diagram_label(source)
    return (
        f'<figure class="mermaid-diagram" aria-label="{label}">'
        f"{svg}"
        "</figure>\n"
    )


def render_mermaid_to_svg(source: str, *, timeout: int = 90) -> str:
    normalized_source = normalize_mermaid_source(source)
    backend = find_mermaid_backend()
    if backend is None:
        raise MermaidRenderError(
            "Mermaid rendering requires a local `mmdc` command. Install it with: "
            "npm install -g @mermaid-js/mermaid-cli"
        )
    return _render_mermaid_with_cli(normalized_source, backend, timeout=timeout)


def normalize_mermaid_source(source: str) -> str:
    stripped = source.lstrip()
    if stripped.startswith("%%{init:") or stripped.startswith("%%{initialize:"):
        return source
    return '%%{init: {"flowchart": {"htmlLabels": false}} }%%\n' + source


def prepare_mermaid_svg(svg: str) -> str:
    cleaned = re.sub(r"<\?xml[^>]*>\s*", "", svg.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"<!DOCTYPE[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r'<style[^>]*>\s*@import\s+url\("[^"]+"\);\s*</style>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _replace_foreign_object_labels(cleaned)

    def replace_svg(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if "mermaid-rendered" not in attrs:
            if re.search(r'\bclass="', attrs):
                attrs = re.sub(r'\bclass="([^"]*)"', r'class="\1 mermaid-rendered"', attrs, count=1)
            else:
                attrs += ' class="mermaid-rendered"'
        if "preserveAspectRatio" not in attrs:
            attrs += ' preserveAspectRatio="xMidYMid meet"'
        return f"<svg{attrs}>"

    return re.sub(r"<svg\b([^>]*)>", replace_svg, cleaned, count=1, flags=re.IGNORECASE)


def _replace_foreign_object_labels(svg: str) -> str:
    pattern = re.compile(
        r'(<g class="label"[^>]*>)\s*(?:<rect\s*/>\s*)?'
        r'<foreignObject\s+width="(?P<width>[^"]+)"\s+height="(?P<height>[^"]+)"[^>]*>'
        r'(?P<body>.*?)</foreignObject>\s*</g>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        width = _float_or_default(match.group("width"), 0.0)
        height = _float_or_default(match.group("height"), 0.0)
        body = match.group("body")
        text = _strip_tags(body).strip()
        if not text:
            return match.group(0)
        return (
            f'{match.group(1)}<text x="{width / 2:.3f}" y="{height / 2:.3f}" '
            'text-anchor="middle" dominant-baseline="central" '
            'font-family="trebuchet ms, verdana, arial, sans-serif" '
            'font-size="16" fill="#333">'
            f"{escape(text)}"
            "</text></g>"
        )

    return pattern.sub(replace, svg)


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    return unescape(re.sub(r"\s+", " ", text))


def _float_or_default(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _render_mermaid_with_cli(source: str, backend: MermaidBackend, *, timeout: int) -> str:
    with tempfile.TemporaryDirectory(prefix="mdtopdf-mermaid-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / "diagram.mmd"
        output_path = tmp_path / "diagram.svg"
        input_path.write_text(source, encoding="utf-8")

        command = [
            *backend.command,
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-b",
            "transparent",
            "--quiet",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise MermaidRenderError(f"Mermaid rendering failed with {backend.kind}: {detail}")
        if not output_path.exists():
            raise MermaidRenderError("Mermaid renderer completed but did not produce an SVG file.")
        return output_path.read_text(encoding="utf-8")


def _diagram_label(source: str) -> str:
    for line in source.splitlines():
        text = line.strip()
        if text:
            return escape(f"Mermaid diagram: {text[:80]}", quote=True)
    return "Mermaid diagram"
