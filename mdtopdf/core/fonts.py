from __future__ import annotations

import shutil
import subprocess
import re
from typing import Any, Iterable


GENERIC_FONT_FAMILIES = {
    "caption",
    "cursive",
    "emoji",
    "fangsong",
    "fantasy",
    "inherit",
    "initial",
    "math",
    "menu",
    "message-box",
    "monospace",
    "revert",
    "revert-layer",
    "sans-serif",
    "serif",
    "small-caption",
    "status-bar",
    "system-ui",
    "ui-monospace",
    "ui-rounded",
    "ui-sans-serif",
    "ui-serif",
    "unset",
}

RECOMMENDED_FONT_GROUPS = {
    "cjk_sans": {
        "description": "CJK body text",
        "families": (
            "Microsoft YaHei",
            "PingFang SC",
            "Hiragino Sans GB",
            "Noto Sans SC",
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "Source Han Sans CN",
        ),
    },
    "monospace": {
        "description": "Code blocks",
        "families": (
            "Cascadia Mono",
            "Cascadia Code",
            "Consolas",
            "Noto Sans Mono CJK SC",
            "Liberation Mono",
            "DejaVu Sans Mono",
        ),
    },
    "math": {
        "description": "Math fallback",
        "families": (
            "Cambria Math",
            "STIX Two Math",
            "STIXGeneral",
            "Latin Modern Math",
        ),
    },
    "emoji": {
        "description": "Emoji glyphs",
        "families": (
            "Segoe UI Emoji",
            "Apple Color Emoji",
            "Noto Emoji",
            "Noto Color Emoji",
            "Twemoji Mozilla",
            "EmojiOne Color",
        ),
    },
}
CJK_CAPABLE_FONT_FAMILIES = (
    "Noto Sans SC",
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Noto Sans CJK KR",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "Source Han Sans JP",
    "Source Han Sans KR",
    "Microsoft YaHei",
    "PingFang SC",
    "SimHei",
    "SimSun",
    "WenQuanYi Micro Hei",
    "WenQuanYi Zen Hei",
    "Sarasa Gothic SC",
    "Hiragino Sans",
    "Yu Gothic",
    "Meiryo",
    "Malgun Gothic",
    "Apple SD Gothic Neo",
)
EMOJI_FONT_FAMILIES = tuple(RECOMMENDED_FONT_GROUPS["emoji"]["families"])

_FONT_FACE_BLOCK_RE = re.compile(r"@font-face\s*\{[^{}]*\}", re.IGNORECASE | re.DOTALL)
_FONT_FAMILY_RE = re.compile(r"\bfont-family\s*:\s*([^;{}]+)", re.IGNORECASE)


def available_font_names() -> set[str]:
    from matplotlib import font_manager

    return {font.name for font in font_manager.fontManager.ttflist}


def match_font_name(family: str, available: set[str]) -> str | None:
    target = family.lower()
    for name in sorted(available):
        current = name.lower()
        if current == target or current.startswith(target + " "):
            return name
    return None


def inspect_recommended_font_groups() -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "backend": "matplotlib.font_manager",
        "groups": {},
        "error": None,
    }

    try:
        available = available_font_names()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    fontconfig_emoji = _fontconfig_emoji_match()
    for group_name, group in RECOMMENDED_FONT_GROUPS.items():
        recommended = list(group["families"])
        found = []
        for family in recommended:
            match = match_font_name(family, available)
            if match and match not in found:
                found.append(match)
        if group_name == "emoji" and fontconfig_emoji.get("ok"):
            for family in fontconfig_emoji.get("families", []):
                if family not in found:
                    found.append(family)
        result["groups"][group_name] = {
            "ok": bool(found),
            "description": group["description"],
            "recommended": recommended,
            "found": found,
            "missing": [family for family in recommended if not match_font_name(family, available)],
        }
        if group_name == "emoji":
            result["groups"][group_name]["fontconfig"] = fontconfig_emoji

    result["ok"] = all(info["ok"] for info in result["groups"].values())
    return result


def inspect_css_font_usage(css: str, *, document_text: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "backend": "matplotlib.font_manager",
        "font_faces": [],
        "stacks": [],
        "warnings": [],
        "error": None,
    }

    try:
        available = available_font_names()
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["warnings"].append(
            {
                "type": "font_inspection_failed",
                "message": (
                    "Font inspection failed; output was still written, "
                    "but font fallback should be checked visually."
                ),
                "error": result["error"],
            }
        )
        return result

    css_without_font_faces, defined_faces = _extract_font_faces(css)
    result["font_faces"] = sorted(defined_faces)

    seen_stacks: set[tuple[str, ...]] = set()
    for declaration in _FONT_FAMILY_RE.findall(_strip_css_comments(css_without_font_faces)):
        families = _parse_font_family_list(declaration)
        checkable = [family for family in families if _is_checkable_font_family(family)]
        if not checkable:
            continue

        normalized = tuple(family.lower() for family in checkable)
        if normalized in seen_stacks:
            continue
        seen_stacks.add(normalized)

        resolved = []
        missing = []
        for family in checkable:
            if family.lower() in defined_faces:
                resolved.append({"family": family, "source": "font-face", "matched": family})
                continue
            match = match_font_name(family, available)
            if match:
                resolved.append({"family": family, "source": "system", "matched": match})
            else:
                missing.append(family)

        stack = {
            "ok": bool(resolved),
            "families": checkable,
            "resolved": resolved,
            "missing": missing,
            "declaration": ", ".join(families),
        }
        result["stacks"].append(stack)
        if not stack["ok"]:
            result["ok"] = False
            result["warnings"].append(
                {
                    "type": "missing_font_stack",
                    "message": (
                        "No installed or @font-face font matched this CSS font-family stack; "
                        "output was still written and WeasyPrint will choose a fallback."
                    ),
                    "families": checkable,
                    "declaration": stack["declaration"],
                }
            )

    if document_text and _contains_cjk(document_text) and not _has_cjk_font_available(available, result):
        result["ok"] = False
        result["warnings"].append(
            {
                "type": "missing_cjk_font",
                "message": (
                    "Document contains CJK text, but no common CJK-capable font was found; "
                    "output was still written, but glyph coverage and pagination should be checked."
                ),
                "recommended": list(CJK_CAPABLE_FONT_FAMILIES),
            }
        )

    if document_text and _contains_emoji(document_text) and not _has_emoji_font_available(available):
        result["ok"] = False
        result["warnings"].append(
            {
                "type": "missing_emoji_font",
                "message": (
                    "Document contains emoji, but no common emoji font was found; "
                    "output was still written, but emoji rendering can be missing or tiny on Linux."
                ),
                "recommended": list(EMOJI_FONT_FAMILIES),
            }
        )

    return result


def font_warning_messages(font_usage: dict[str, Any]) -> list[str]:
    return [warning["message"] for warning in font_usage.get("warnings", [])]


def summarize_font_usage(font_usage: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(font_usage.get("ok")),
        "backend": font_usage.get("backend"),
        "checked_stacks": len(font_usage.get("stacks", [])),
        "font_face_count": len(font_usage.get("font_faces", [])),
        "error": font_usage.get("error"),
    }


def _extract_font_faces(css: str) -> tuple[str, set[str]]:
    defined: set[str] = set()

    def remove(match: re.Match[str]) -> str:
        block = match.group(0)
        for declaration in _FONT_FAMILY_RE.findall(block):
            for family in _parse_font_family_list(declaration):
                if _is_checkable_font_family(family):
                    defined.add(family.lower())
        return ""

    return _FONT_FACE_BLOCK_RE.sub(remove, css), defined


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _parse_font_family_list(value: str) -> list[str]:
    families: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    paren_depth = 0

    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            current.append(char)
            quote = char
            continue
        if char == "(":
            paren_depth += 1
            current.append(char)
            continue
        if char == ")" and paren_depth:
            paren_depth -= 1
            current.append(char)
            continue
        if char == "," and paren_depth == 0:
            _append_font_family(families, "".join(current))
            current = []
            continue
        current.append(char)

    _append_font_family(families, "".join(current))
    return families


def _append_font_family(families: list[str], raw: str) -> None:
    family = raw.strip()
    if not family:
        return
    if len(family) >= 2 and family[0] == family[-1] and family[0] in {"'", '"'}:
        family = family[1:-1].strip()
    if family:
        families.append(family)


def _is_checkable_font_family(family: str) -> bool:
    normalized = family.strip().lower()
    if not normalized or normalized in GENERIC_FONT_FAMILIES:
        return False
    if normalized.startswith(("var(", "env(")):
        return False
    return True


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
        or "\u3040" <= char <= "\u30ff"
        or "\uac00" <= char <= "\ud7af"
        for char in text
    )


def _contains_emoji(text: str) -> bool:
    return any(
        "\u2600" <= char <= "\u27bf"
        or "\U0001f000" <= char <= "\U0001faff"
        for char in text
    )


def _has_cjk_font_available(available: set[str], font_usage: dict[str, Any]) -> bool:
    for family in CJK_CAPABLE_FONT_FAMILIES:
        if match_font_name(family, available):
            return True
    return any(
        resolved.get("source") == "font-face"
        and not str(resolved.get("family", "")).lower().startswith("katex_")
        for stack in font_usage.get("stacks", [])
        for resolved in stack.get("resolved", [])
    )


def _has_emoji_font_available(available: set[str]) -> bool:
    for family in EMOJI_FONT_FAMILIES:
        if match_font_name(family, available):
            return True
    return bool(_fontconfig_emoji_match().get("ok"))


def _fontconfig_emoji_match() -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "tool": "fc-match",
        "families": [],
        "file": None,
        "error": None,
    }
    executable = shutil.which("fc-match")
    if not executable:
        result["error"] = "fc-match not found"
        return result

    try:
        family_proc = subprocess.run(
            [executable, "-f", "%{family}\n", "emoji"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        file_proc = subprocess.run(
            [executable, "-f", "%{file}\n", "emoji"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    families = [item.strip() for item in family_proc.stdout.replace(",", "\n").splitlines() if item.strip()]
    result["families"] = families
    result["file"] = file_proc.stdout.strip() or None
    result["ok"] = any("emoji" in family.lower() for family in families)
    return result
