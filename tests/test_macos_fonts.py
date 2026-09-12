import pytest

from mdtopdf.core import fonts
from mdtopdf.core.markdown import load_theme_css


@pytest.mark.parametrize("monospace", ["Menlo", "Monaco"])
def test_default_theme_accepts_macos_system_monospace(monkeypatch, monospace):
    monkeypatch.setattr(fonts, "available_font_names", lambda: {
        "Arial", "PingFang SC", "Times New Roman", "Apple Color Emoji", monospace,
    })
    result = fonts.inspect_css_font_usage(load_theme_css(), document_text="Example code")
    assert not result["warnings"]
    group = fonts.inspect_recommended_font_groups("Darwin")["groups"]["monospace"]
    assert group["ok"]
    assert group["found"] == [monospace]
    assert group["preferred"] == ["Cascadia Mono", "Cascadia Code"]
