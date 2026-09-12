"""Run with the wheel's Python, from outside the source checkout."""

from importlib import metadata, resources
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import mdtopdf


def run(*args, input=None):
    proc = subprocess.run(
        [sys.executable, "-m", "mdtopdf", *args],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=90, input=input,
    )
    return proc.stdout


def main():
    package_path = Path(mdtopdf.__file__).resolve()
    assert Path(sys.prefix).resolve() in package_path.parents, package_path
    version = metadata.version("agent-markdown-pdf")
    assert version in run("--version")
    assert "--strict" in run("convert", "--help")
    assert json.loads(run("doctor", "--json"))["ok"]
    package = resources.files("mdtopdf")
    assert package.joinpath("skills/SKILL.md").is_file()
    assert package.joinpath("themes/default.css").is_file()
    assert package.joinpath("vendor/katex/dist/fonts/KaTeX_Main-Regular.woff2").is_file()
    assert package.joinpath("vendor/mermaid/mermaid.min.js").is_file()
    assert package.joinpath("vendor/browser-render.js").is_file()
    with tempfile.TemporaryDirectory(prefix="mdtopdf-wheel-") as directory:
        source = Path(directory) / "report.md"
        source.write_text("# Wheel check\n\n0123456789\n\n$x^2 + 1$\n\n~~~mermaid\ngraph TD; A-->B\n~~~\n", encoding="utf-8")
        result = json.loads(run("convert", str(source), "--strict", "--json"))
        assert result["ok"] and result["warnings"] == []
        assert Path(result["output"]).read_bytes().startswith(b"%PDF-")
        preview = json.loads(run("html", str(source), "--json"))
        html = Path(preview["output"]).read_text(encoding="utf-8")
        assert "katex-html" in html and "<svg" in html
        assert "data-mdtopdf-mermaid=" not in html
        piped = json.loads(run("convert", "-", "-o", str(Path(directory) / "stdin.pdf"),
                               "--json", input="# UTF-8 stdin\n\n中文 0123456789\n"))
        assert piped["ok"] and piped["source"] == "stdin" and piped["input"] == "-"
        assert Path(piped["output"]).read_bytes().startswith(b"%PDF-")
    print(f"Installed wheel {version} passed: {package_path}")


if __name__ == "__main__":
    main()
