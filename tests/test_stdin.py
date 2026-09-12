import json
import io
from pathlib import Path

from click.testing import CliRunner
import pytest

from mdtopdf.mdtopdf_cli import cli
import mdtopdf.mdtopdf_cli as commands


@pytest.mark.parametrize("args", [
    ["convert", "-", "--json"],
    ["convert", "-", "-o", "-", "--json"],
])
def test_stdin_requires_real_output(args):
    result = CliRunner().invoke(cli, args, input="# Report")
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert not data["ok"]
    assert "output" in data["error"].lower()


@pytest.mark.parametrize("data", [b"", b" \r\n\t", b"\xff"])
def test_invalid_stdin_does_not_create_pdf(tmp_path, data):
    output = tmp_path / "report.pdf"
    result = CliRunner().invoke(cli, ["convert", "-", "-o", str(output), "--json"], input=data)
    assert result.exit_code == 1
    assert not json.loads(result.stdout)["ok"]
    assert not output.exists()


def test_utf8_stdin_passes_all_render_options(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    css = tmp_path / "theme.css"
    css.write_text("body {color: teal}", encoding="utf-8")
    captured = {}

    def render(text, output_path, **options):
        captured.update(text=text, output_path=output_path, **options)
        return {"ok": True, "input": None, "source": "markdown_text", "warnings": []}

    monkeypatch.setattr(commands, "markdown_to_pdf", render)
    result = CliRunner().invoke(cli, [
        "convert", "-", "-o", "out.pdf", "--json", "--title", "Report",
        "--header", "Header", "--footer", "Footer", "--css", str(css),
        "--resource-dir", str(tmp_path), "--strict", "--overwrite", "--unsafe-html",
        "--no-page-numbers",
    ], input="\ufeff# 中文报告\n\n$x^2$".encode("utf-8"))
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["input"] == "-"
    assert json.loads(result.stdout)["source"] == "stdin"
    assert captured["text"] == "# 中文报告\n\n$x^2$"
    assert Path(captured["base_url"]) == tmp_path
    assert captured["custom_css"] == css.read_text(encoding="utf-8")
    assert captured["strict"] and captured["overwrite"] and captured["unsafe_html"]
    assert captured["page_header"] == "Header"
    assert captured["page_footer"] == "Footer"
    assert captured["title"] == "Report"
    assert not captured["page_numbers"]


def test_stdin_existing_output_stays_unchanged(tmp_path):
    target = tmp_path / "report.pdf"
    target.write_bytes(b"original")
    result = CliRunner().invoke(cli, ["convert", "-", "-o", str(target), "--json"], input="# Test")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error_type"] == "FileExistsError"
    assert target.read_bytes() == b"original"


def test_stdin_real_pdf_and_relative_resources(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "image.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>',
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, ["convert", "-", "-o", "report.pdf", "--json"],
                                input="# Report\n\n![image](image.svg)\n\n$x^2$\n\n~~~mermaid\ngraph TD; A-->B\n~~~")
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF-")
    data = json.loads(result.stdout)
    assert not data["warnings"]
    assert data["title"] == "stdin"
    assert data["input"] == "-"
    assert data["method"] == "markdown-it-py+chromium"


def test_stdin_strict_failure_preserves_output(tmp_path):
    target = tmp_path / "keep.pdf"
    target.write_bytes(b"original")
    result = CliRunner().invoke(cli, [
        "convert", "-", "-o", str(target), "--overwrite", "--strict", "--json",
    ], input=r"$\unknownCommand{x}$")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["warnings"]
    assert target.read_bytes() == b"original"


def test_file_named_dash_can_be_explicitly_addressed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    Path("-").write_text("# File, not stdin", encoding="utf-8")
    result = CliRunner().invoke(cli, ["convert", "./-", "-o", "literal.pdf", "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["input"] == str((tmp_path / "-").resolve())


def test_interactive_stdin_fails_without_waiting(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

        def read(self, *args):
            pytest.fail("Interactive stdin must not block waiting for EOF")

    monkeypatch.setattr(commands.sys, "stdin", Terminal())
    with pytest.raises(ValueError, match="Pipe UTF-8"):
        commands._read_stdin_markdown()


def test_text_only_stdin_stream(monkeypatch):
    monkeypatch.setattr(commands.sys, "stdin", io.StringIO("\ufeff# Report"))
    assert commands._read_stdin_markdown() == "# Report"
