import os
from pathlib import Path

import pytest

from mdtopdf.core import browser


@pytest.fixture(autouse=True)
def clean_browser_environment(monkeypatch):
    monkeypatch.delenv(browser.BROWSER_ENV, raising=False)
    monkeypatch.delenv("PUPPETEER_EXECUTABLE_PATH", raising=False)


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test executable")
    path.chmod(0o755)
    return str(path)


def test_explicit_path_has_priority(monkeypatch, tmp_path):
    configured = executable(tmp_path / "chosen")
    legacy = executable(tmp_path / "legacy")
    managed = executable(tmp_path / "managed")
    monkeypatch.setenv(browser.BROWSER_ENV, configured)
    monkeypatch.setenv("PUPPETEER_EXECUTABLE_PATH", legacy)
    assert browser._resolve_executable(managed) == (configured, browser.BROWSER_ENV)


def test_invalid_explicit_path_never_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv(browser.BROWSER_ENV, str(tmp_path / "missing"))
    managed = executable(tmp_path / "managed")
    with pytest.raises(browser.BrowserRenderError) as caught:
        browser._resolve_executable(managed)
    assert caught.value.error_code == "browser_missing"
    assert browser.BROWSER_ENV in caught.value.hint


def test_legacy_path_is_still_explicit(monkeypatch, tmp_path):
    legacy = executable(tmp_path / "legacy")
    monkeypatch.setenv("PUPPETEER_EXECUTABLE_PATH", legacy)
    assert browser._resolve_executable("missing") == (legacy, "PUPPETEER_EXECUTABLE_PATH")


def test_managed_browser_precedes_system(monkeypatch, tmp_path):
    managed = executable(tmp_path / "managed")
    monkeypatch.setattr(browser, "_system_browser_candidates",
                        lambda: pytest.fail("System lookup should not run"))
    assert browser._resolve_executable(managed) == (managed, "playwright")


def test_system_browser_used_when_managed_missing(monkeypatch, tmp_path):
    system = executable(tmp_path / "system")
    monkeypatch.setattr(browser, "_system_browser_candidates", lambda: iter([Path(system)]))
    assert browser._resolve_executable("missing") == (system, "system")


def test_no_browser_has_install_hint(monkeypatch):
    monkeypatch.setattr(browser, "_system_browser_candidates", lambda: iter([]))
    with pytest.raises(browser.BrowserRenderError) as caught:
        browser._resolve_executable("missing")
    assert caught.value.error_code == "browser_missing"
    assert "playwright install chromium" in caught.value.hint


@pytest.mark.parametrize(("system", "name"), [
    ("Windows", "msedge.exe"), ("Windows", "chrome.exe"),
    ("Linux", "chromium"), ("Linux", "google-chrome-stable"),
    ("Darwin", "chromium"),
])
def test_path_lookup(monkeypatch, tmp_path, system, name):
    expected = executable(tmp_path / name)
    monkeypatch.setattr(browser.platform, "system", lambda: system)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert browser._resolve_executable("missing") == (expected, "system")


@pytest.mark.parametrize("relative", [
    "Google/Chrome/Application/chrome.exe",
    "Microsoft/Edge/Application/msedge.exe",
    "Chromium/Application/chrome.exe",
])
def test_windows_common_install_locations(monkeypatch, tmp_path, relative):
    expected = executable(tmp_path / relative)
    monkeypatch.setattr(browser.platform, "system", lambda: "Windows")
    monkeypatch.setenv("PATH", "")
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        monkeypatch.setenv(key, str(tmp_path))
    assert browser._resolve_executable("missing") == (expected, "system")


@pytest.mark.parametrize("app", ["Google Chrome", "Microsoft Edge", "Chromium"])
def test_macos_user_applications(monkeypatch, tmp_path, app):
    expected = tmp_path / "Applications" / f"{app}.app" / "Contents" / "MacOS" / app
    executable(expected)
    monkeypatch.setattr(browser.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(browser.Path, "home", lambda: tmp_path)
    monkeypatch.setenv("PATH", "")
    assert expected in list(browser._system_browser_candidates())


def test_inspection_uses_same_resolver(monkeypatch, tmp_path):
    selected = executable(tmp_path / "selected")
    monkeypatch.setattr(browser, "_resolve_executable", lambda managed: (selected, "system"))
    result = browser.inspect_browser()
    assert result["ok"]
    assert result["executable"] == selected
    assert result["source"] == "system"


@pytest.mark.skipif(os.name != "posix", reason="POSIX launcher symlinks")
def test_launcher_symlink_is_not_replaced_by_its_target(monkeypatch, tmp_path):
    target = executable(tmp_path / "launcher")
    link = tmp_path / "chromium"
    link.symlink_to(target)
    monkeypatch.setattr(browser, "_system_browser_candidates", lambda: iter([link]))
    assert browser._resolve_executable("missing") == (str(link), "system")


def test_relative_path_entries_are_not_searched(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", ".")
    monkeypatch.setattr(browser.platform, "system", lambda: "Linux")
    assert Path("./chromium") not in list(browser._system_browser_candidates())
