"""Browser failures must remain actionable through doctor and CLI JSON."""
import asyncio
import json

import pytest
from click.testing import CliRunner

from mdtopdf.core import browser, doctor
from mdtopdf.mdtopdf_cli import cli


@pytest.mark.parametrize("message,code", [
    ("Executable doesn't exist at /missing/chrome", "browser_missing"),
    ("No usable sandbox!", "browser_sandbox_unavailable"),
    ("Running as root without --no-sandbox is not supported", "browser_sandbox_unavailable"),
    ("Timeout 30000ms exceeded", "browser_timeout"),
    ("Target page, context or browser has been closed", "browser_render_failed"),
])
def test_browser_failure_is_actionable(message, code):
    error = browser._failure(RuntimeError(message))
    assert error.error_code == code
    assert error.hint


def test_total_timeout_is_actionable():
    assert browser._failure(asyncio.TimeoutError()).error_code == "browser_timeout"


def test_render_check_preserves_repair_hint(monkeypatch):
    def fail(*args, **kwargs):
        raise browser.BrowserRenderError("Missing", error_code="browser_missing", hint="Install Chromium")
    monkeypatch.setattr(browser, "render_document", fail)
    checks = doctor._run_render_checks()
    assert checks["pdf"]["error_code"] == "browser_missing"
    assert checks["pdf"]["hint"] == "Install Chromium"


def test_cli_browser_error_json(monkeypatch, tmp_path):
    monkeypatch.setenv(browser.BROWSER_ENV, str(tmp_path / "missing"))
    source = tmp_path / "input.md"
    source.write_text("# Report", encoding="utf-8")
    result = CliRunner().invoke(cli, ["convert", str(source), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error_code"] == "browser_missing"
    assert payload["hint"]
    assert not source.with_suffix(".pdf").exists()
