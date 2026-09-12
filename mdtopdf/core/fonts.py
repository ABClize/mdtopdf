from __future__ import annotations

import shutil
import subprocess
import base64
import os
import platform
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import url2pathname
from typing import Any

import tinycss2
from fontTools.ttLib import TTFont, TTCollection


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
    "latin_sans": {
        "description": "Latin body text and digits",
        "preferred": ("Segoe UI", "Arial", "Liberation Sans", "DejaVu Sans"),
        "families": (
            "Segoe UI",
            "Arial",
            "Liberation Sans",
            "DejaVu Sans",
        ),
    },
    "cjk_sans": {
        "description": "CJK body text",
        "preferred": ("Microsoft YaHei",),
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
        "preferred": ("Cascadia Mono", "Cascadia Code"),
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
        "preferred": ("Cambria Math",),
        "families": (
            "Cambria Math",
            "STIX Two Math",
            "STIXGeneral",
            "Latin Modern Math",
        ),
    },
    "emoji": {
        "description": "Emoji glyphs",
        "preferred": ("Segoe UI Emoji",),
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
PLATFORM_PREFERRED_FONT_GROUPS = {
    "Linux": {
        "latin_sans": ("Liberation Sans", "DejaVu Sans"),
        "cjk_sans": ("Noto Sans CJK SC", "Noto Sans SC"),
        "math": ("STIXGeneral", "STIX Two Math"),
        "emoji": ("Noto Emoji",),
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


def available_font_names() -> set[str]:
    executable = shutil.which("fc-list")
    if executable:
        try:
            proc = subprocess.run(
                [executable, "-f", "%{family}\n"], check=True, capture_output=True,
                text=True, encoding="utf-8", timeout=5,
            )
            names = {
                name.strip() for line in proc.stdout.splitlines()
                for name in line.split(",") if name.strip()
            }
            if names:
                return _FontNames(names, backend="fontconfig")
        except (OSError, subprocess.SubprocessError, UnicodeError):
            pass
    names = set()
    for path in _system_font_files():
        try:
            info = path.stat()
            names.update(_file_font_names(str(path), info.st_mtime_ns, info.st_size))
        except Exception:
            # A malformed individual font must not hide the rest of the inventory.
            continue
    return _FontNames(names, backend="fonttools")


def _system_font_files():
    system = platform.system()
    if system == "Windows":
        directories = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
                       Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft/Windows/Fonts"]
    elif system == "Darwin":
        directories = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), Path.home() / "Library/Fonts"]
    else:
        directories = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
                       Path.home() / ".local/share/fonts", Path.home() / ".fonts"]
    files = set()
    for directory in directories:
        if directory.is_dir():
            files.update(p for p in directory.rglob("*") if p.suffix.lower() in {".ttf", ".otf", ".ttc", ".otc"})
    if system == "Windows":
        import winreg
        for hive, directory in ((winreg.HKEY_LOCAL_MACHINE, directories[0]), (winreg.HKEY_CURRENT_USER, directories[1])):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                    for index in range(winreg.QueryInfoKey(key)[1]):
                        value = winreg.EnumValue(key, index)[1]
                        if isinstance(value, str):
                            path = Path(value)
                            files.add(path if path.is_absolute() else directory / path)
            except OSError:
                pass
    return files


@lru_cache(maxsize=2048)
def _file_font_names(path, mtime_ns, size):
    collection = TTCollection(path, lazy=True) if Path(path).suffix.lower() in {".ttc", ".otc"} else None
    fonts = collection.fonts if collection else [TTFont(path, lazy=True)]
    try:
        return frozenset(name.toUnicode() for font in fonts for name in font["name"].names if name.nameID in {1, 16})
    finally:
        for font in fonts:
            font.close()
        if collection:
            collection.close()


class _FontNames(set):
    def __init__(self, names, *, backend):
        super().__init__(names)
        self.backend = backend


def match_font_name(family: str, available: set[str]) -> str | None:
    target = family.lower()
    for name in sorted(available):
        current = name.lower()
        if "emoji" not in target and " emoji" in current:
            continue
        if current == target or current.startswith(target + " "):
            return name
    return None


def inspect_recommended_font_groups(platform_system: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "backend": "fonttools",
        "groups": {},
        "error": None,
    }

    try:
        available = available_font_names()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["backend"] = getattr(available, "backend", result["backend"])
    fontconfig_emoji = _fontconfig_emoji_match()
    for group_name, group in RECOMMENDED_FONT_GROUPS.items():
        recommended = list(group["families"])
        preferred = list(_preferred_families(group_name, group, platform_system))
        found = []
        for family in recommended:
            match = match_font_name(family, available)
            if match and match not in found:
                found.append(match)
        if group_name == "emoji" and fontconfig_emoji.get("ok"):
            for family in fontconfig_emoji.get("families", []):
                if family not in found:
                    found.append(family)
        missing = [family for family in recommended if not match_font_name(family, set(found))]
        result["groups"][group_name] = {
            "ok": bool(found),
            "description": group["description"],
            "preferred": preferred,
            "preferred_found": any(family not in missing for family in preferred),
            "recommended": recommended,
            "found": found,
            "missing": missing,
        }
        if group_name == "emoji":
            result["groups"][group_name]["fontconfig"] = fontconfig_emoji

    result["ok"] = all(info["ok"] for info in result["groups"].values())
    return result


def _preferred_families(
    group_name: str,
    group: dict[str, Any],
    platform_system: str | None,
) -> tuple[str, ...]:
    platform_preferred = PLATFORM_PREFERRED_FONT_GROUPS.get(platform_system or "", {})
    if isinstance(platform_preferred, dict) and group_name in platform_preferred:
        return platform_preferred[group_name]
    return group.get("preferred", group["families"][:1])


def inspect_css_font_usage(
    css: str, *, document_text: str | None = None,
    base_url: str | None = None, custom_css: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "backend": "fonttools",
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
                    "Font inspection failed; "
                    "font fallback should be checked visually."
                ),
                "error": result["error"],
            }
        )
        return result

    result["backend"] = getattr(available, "backend", result["backend"])
    face_rules, declarations = _font_declarations(css)
    defined_faces = {}
    cjk_characters = {ord(char) for char in document_text or "" if _contains_cjk(char)}
    for family, sources in face_rules:
        face = _inspect_font_sources(sources, available, base_url, cjk_characters)
        defined_faces.setdefault(family.lower(), []).append(face)
    result["font_faces"] = sorted(defined_faces)
    result["font_face_checks"] = defined_faces
    custom_declarations = set(_font_declarations(custom_css or "")[1])

    seen_stacks: set[tuple[str, ...]] = set()
    for declaration in declarations:
        families = _parse_font_family_list(declaration)
        checkable = [family for family in families if _is_checkable_font_family(family)]
        if not checkable:
            continue
        if not _contains_emoji(document_text or "") and all(
            family in EMOJI_FONT_FAMILIES for family in checkable
        ) and declaration not in custom_declarations:
            continue

        normalized = tuple(family.lower() for family in checkable)
        if normalized in seen_stacks:
            continue
        seen_stacks.add(normalized)

        resolved = []
        missing = []
        for family in checkable:
            if family.lower() in defined_faces:
                valid = [face for face in defined_faces[family.lower()] if face["ok"]]
                if valid:
                    resolved.append({
                        "family": family, "source": "font-face", "matched": family,
                        "cjk_capable": any(face["cjk_capable"] for face in valid),
                    })
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
        for family in checkable:
            for face in defined_faces.get(family.lower(), []):
                if not face["ok"]:
                    result["ok"] = False
                    warning = {
                        "type": "font_face_unavailable",
                        "message": f"Could not verify @font-face '{family}'; font fallback may be used.",
                        "families": [family], "error": face["error"],
                    }
                    if warning not in result["warnings"]:
                        result["warnings"].append(warning)
        if declaration in custom_declarations and checkable[0] in missing and resolved:
            result["ok"] = False
            result["warnings"].append({
                "type": "missing_preferred_font",
                "message": "The first font in a custom CSS stack is unavailable; a fallback will be used.",
                "families": [checkable[0]], "declaration": stack["declaration"],
            })
        if not stack["ok"]:
            result["ok"] = False
            result["warnings"].append(
                {
                    "type": "missing_font_stack",
                    "message": (
                        "No installed or @font-face font matched this CSS font-family stack; "
                        "Chromium will choose a fallback."
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
                    "glyph coverage and pagination should be checked."
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
                    "emoji rendering can be missing or tiny on Linux."
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


def _font_declarations(css):
    faces, families = [], []

    def visit(rules):
        for rule in rules:
            if rule.type not in {"at-rule", "qualified-rule"} or rule.content is None:
                continue
            items = tinycss2.parse_blocks_contents(rule.content, skip_comments=True, skip_whitespace=True)
            declarations = {
                item.lower_name: tinycss2.serialize(item.value).strip()
                for item in items if item.type == "declaration"
            }
            if rule.type == "at-rule" and rule.lower_at_keyword == "font-face":
                for family in _parse_font_family_list(declarations.get("font-family", "")):
                    faces.append((family, declarations.get("src", "")))
            else:
                if "font-family" in declarations:
                    families.append(declarations["font-family"])
                visit(items)

    visit(tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True))
    return faces, families


@lru_cache(maxsize=256)
def _file_font_codepoints(path, mtime_ns, size):
    # Metadata in the cache key invalidates fonts replaced during a long-lived
    # Python process without re-reading every bundled KaTeX font per export.
    with TTFont(path, lazy=True, fontNumber=0) as font:
        return frozenset(font.getBestCmap() or {})


def _inspect_font_sources(sources, available, base_url, cjk_characters):
    errors = []
    for token in tinycss2.parse_component_value_list(sources, skip_comments=True):
        url = None
        if token.type == "function" and token.lower_name == "local":
            name = tinycss2.serialize(token.arguments).strip().strip("'\"")
            matched = match_font_name(name, available)
            if matched:
                return {"ok": True, "cjk_capable": matched in CJK_CAPABLE_FONT_FAMILIES, "error": None}
            errors.append(f"Local font not found: {name}")
        elif token.type == "url":
            url = token.value
        elif token.type == "function" and token.lower_name == "url":
            args = [arg for arg in token.arguments if arg.type not in {"whitespace", "comment"}]
            if len(args) == 1 and args[0].type == "string":
                url = args[0].value
        if url is None:
            continue
        try:
            if url.startswith("data:"):
                header, data = url.split(",", 1)
                raw = base64.b64decode(data) if ";base64" in header else unquote(data).encode("latin-1")
                with TTFont(BytesIO(raw), lazy=True, fontNumber=0) as font:
                    points = frozenset(font.getBestCmap() or {})
            else:
                parsed = urlparse(url)
                if not parsed.scheme:
                    base = base_url or str(Path.cwd())
                    if urlparse(base).scheme in {"file", "http", "https"}:
                        url = urljoin(base.rstrip("/") + "/", url)
                    else:
                        url = (Path(base) / unquote(url)).resolve().as_uri()
                    parsed = urlparse(url)
                if parsed.scheme != "file":
                    errors.append(f"Remote font is not verified by static inspection: {url}")
                    continue
                path = Path(url2pathname(parsed.path))
                if parsed.netloc and parsed.netloc != "localhost":
                    path = Path(f"//{parsed.netloc}{url2pathname(parsed.path)}")
                stat = path.stat()
                points = _file_font_codepoints(str(path), stat.st_mtime_ns, stat.st_size)
            return {"ok": True, "cjk_capable": bool(cjk_characters) and cjk_characters <= points, "error": None}
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    return {"ok": False, "cjk_capable": False, "error": "; ".join(errors) or "No usable font source"}


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
        and resolved.get("cjk_capable", False)
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
