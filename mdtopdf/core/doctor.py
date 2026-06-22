from __future__ import annotations

import ctypes
import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from mdtopdf.core.fonts import inspect_recommended_font_groups
from mdtopdf.core.mermaid import inspect_mermaid_backend


WINDOWS_DLL_ENV = "WEASYPRINT_DLL_DIRECTORIES"
REQUIRED_WINDOWS_DLLS = (
    "libgobject-2.0-0.dll",
    "libpango-1.0-0.dll",
    "libcairo-2.dll",
)
COMMON_WINDOWS_DLL_DIRS = (
    r"C:\msys64\mingw64\bin",
    r"D:\Environment\msys64\mingw64\bin",
)
def add_weasyprint_dll_directories() -> list[str]:
    """Register Windows DLL search directories from ``WEASYPRINT_DLL_DIRECTORIES``."""

    if os.name != "nt":
        return []

    added: list[str] = []
    for raw_path in _env_dll_directories():
        path = Path(raw_path)
        if path.exists() and path.is_dir():
            os.add_dll_directory(str(path))
            added.append(str(path))
    return added


def run_doctor() -> dict[str, Any]:
    """Inspect Python packages, optional Mermaid support, and native libraries.

    Returns:
        A JSON-serializable dictionary with platform details, Python package
        import status, Mermaid backend status, Windows native library probes,
        and repair recommendations. The top-level ``ok`` value is true when all
        required Python packages are available; Mermaid is optional and only
        renders when local ``mmdc`` is installed.
    """

    add_weasyprint_dll_directories()

    result: dict[str, Any] = {
        "ok": False,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "environment": {
            WINDOWS_DLL_ENV: os.environ.get(WINDOWS_DLL_ENV),
        },
        "packages": {},
        "tools": {},
        "native_libraries": _inspect_native_libraries(),
        "fonts": _inspect_fonts(),
        "recommendations": [],
    }

    result["packages"]["weasyprint"] = _check_python_package("weasyprint")
    result["packages"]["mini-racer"] = _check_python_package("py_mini_racer")
    result["packages"]["latex2mathml"] = _check_python_package("latex2mathml")
    result["packages"]["matplotlib"] = _check_python_package("matplotlib")
    result["tools"]["mermaid"] = inspect_mermaid_backend()
    if result["platform"]["system"] == "Linux":
        result["tools"]["fontconfig"] = _inspect_fontconfig()
    result["ok"] = all(info["ok"] for info in result["packages"].values())
    result["recommendations"] = _recommendations(result)
    return result


def format_doctor_text(result: dict[str, Any]) -> str:
    status = "OK" if result.get("ok") else "NEEDS ATTENTION"
    lines = [
        f"mdtopdf doctor: {status}",
        f"Python: {result['python']['version']} ({result['python']['executable']})",
        f"Platform: {result['platform']['system']} {result['platform']['release']} {result['platform']['machine']}",
        f"{WINDOWS_DLL_ENV}: {result['environment'].get(WINDOWS_DLL_ENV) or '(not set)'}",
        "",
        "Python packages:",
    ]

    for name, info in result.get("packages", {}).items():
        version = f" {info.get('version')}" if info.get("version") else ""
        error = f" - {info.get('error')}" if info.get("error") else ""
        lines.append(f"  - {name}: {'OK' if info.get('ok') else 'FAIL'}{version}{error}")

    if result.get("tools"):
        lines.extend(["", "External tools:"])
        for name, info in result["tools"].items():
            backend = f" via {info.get('backend')}" if info.get("backend") else ""
            executable = f" ({info.get('executable')})" if info.get("executable") else ""
            error = f" - {info.get('error')}" if info.get("error") else ""
            lines.append(f"  - {name}: {'OK' if info.get('ok') else 'MISSING'}{backend}{executable}{error}")

    if result.get("native_libraries"):
        lines.extend(["", "Native library probes:"])
        for probe in result["native_libraries"]:
            lines.append(
                f"  - {probe['directory']}: "
                f"{'OK' if probe['all_found'] else 'MISSING'} "
                f"found={', '.join(probe['found']) or '(none)'} "
                f"missing={', '.join(probe['missing']) or '(none)'}"
            )

    if result.get("fonts"):
        lines.extend(["", "Fonts:"])
        font_error = result["fonts"].get("error")
        if font_error:
            lines.append(f"  - font inspection: FAIL - {font_error}")
        for name, info in result["fonts"].get("groups", {}).items():
            found = ", ".join(info.get("found", [])) or "(none)"
            recommended = ", ".join(info.get("recommended", []))
            lines.append(
                f"  - {name}: {'OK' if info.get('ok') else 'MISSING'} "
                f"found={found} recommended={recommended}"
            )

    if result.get("recommendations"):
        lines.extend(["", "Recommendations:"])
        for item in result["recommendations"]:
            lines.append(f"  - {item}")

    return "\n".join(lines)


def _check_python_package(name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(name)
    except Exception as exc:
        return {
            "ok": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "ok": True,
        "version": getattr(module, "__version__", None),
        "error": None,
    }


def _inspect_native_libraries() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []

    probes: list[dict[str, Any]] = []
    for directory in _candidate_windows_dll_dirs():
        path = Path(directory)
        found = [dll for dll in REQUIRED_WINDOWS_DLLS if (path / dll).exists()]
        missing = [dll for dll in REQUIRED_WINDOWS_DLLS if dll not in found]
        loadable = _loadable_dlls(path, found)
        probes.append(
            {
                "directory": str(path),
                "exists": path.exists(),
                "found": found,
                "missing": missing,
                "loadable": loadable,
                "all_found": bool(found) and not missing,
            }
        )
    return probes


def _loadable_dlls(directory: Path, dll_names: list[str]) -> dict[str, bool]:
    if os.name != "nt" or not directory.exists():
        return {dll: False for dll in dll_names}

    status: dict[str, bool] = {}
    for dll in dll_names:
        try:
            ctypes.CDLL(str(directory / dll))
        except Exception:
            status[dll] = False
        else:
            status[dll] = True
    return status


def _candidate_windows_dll_dirs() -> list[str]:
    seen: set[str] = set()
    dirs: list[str] = []
    for item in [*_env_dll_directories(), *COMMON_WINDOWS_DLL_DIRS]:
        normalized = str(Path(item))
        if normalized not in seen:
            seen.add(normalized)
            dirs.append(normalized)
    return dirs


def _env_dll_directories() -> list[str]:
    raw = os.environ.get(WINDOWS_DLL_ENV, "")
    return [part.strip() for part in raw.split(os.pathsep) if part.strip()]


def _inspect_fonts() -> dict[str, Any]:
    return inspect_recommended_font_groups()


def _inspect_fontconfig() -> dict[str, Any]:
    executable = shutil.which("fc-match")
    result: dict[str, Any] = {
        "ok": False,
        "executable": executable,
        "sample": None,
        "error": None,
    }
    if not executable:
        result["error"] = "fc-match was not found on PATH."
        return result

    try:
        proc = subprocess.run(
            [executable, "-f", "%{family}\n", "sans-serif"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["sample"] = proc.stdout.strip() or None
    result["ok"] = True
    return result


def _recommendations(result: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    is_linux = result.get("platform", {}).get("system") == "Linux"
    package_info = result.get("packages", {}).get("weasyprint", {})
    if not package_info.get("ok"):
        recommendations.append("Install Python dependencies with: python -m pip install agent-markdown-pdf")
    mini_racer_info = result.get("packages", {}).get("mini-racer", {})
    if not mini_racer_info.get("ok"):
        recommendations.append("Install KaTeX rendering support with: python -m pip install mini-racer")
    math_info = result.get("packages", {}).get("latex2mathml", {})
    if not math_info.get("ok"):
        recommendations.append("Install LaTeX math support with: python -m pip install latex2mathml")
    matplotlib_info = result.get("packages", {}).get("matplotlib", {})
    if not matplotlib_info.get("ok"):
        recommendations.append("Install SVG math rendering support with: python -m pip install matplotlib")

    mermaid_info = result.get("tools", {}).get("mermaid", {})
    if not mermaid_info.get("ok"):
        recommendations.append(
            "Optional: install Mermaid rendering support with Node.js plus: "
            "npm install -g @mermaid-js/mermaid-cli"
        )
    fontconfig_info = result.get("tools", {}).get("fontconfig")
    if is_linux and fontconfig_info and not fontconfig_info.get("ok"):
        recommendations.append(
            "Install fontconfig so WeasyPrint/Pango can resolve system fonts, for example: "
            "sudo apt-get install fontconfig"
        )

    font_info = result.get("fonts", {})
    font_groups = font_info.get("groups", {})
    if font_info.get("error"):
        recommendations.append("Font inspection failed; run conversion once and verify CJK text visually.")
    if font_groups.get("latin_sans") and not font_groups["latin_sans"].get("ok"):
        recommendations.append(
            "Install a Latin sans font so digits, dates, versions, and page counters avoid CJK font subsets. "
            "On Debian or Ubuntu, use: sudo apt-get install fonts-liberation fonts-dejavu-core"
        )
    if font_groups.get("cjk_sans") and not font_groups["cjk_sans"].get("ok"):
        recommendations.append(
            "Provide Microsoft YaHei in the runtime to match the default theme's Windows-like Chinese typography. "
            "On Debian or Ubuntu, Noto CJK is a supported fallback: sudo apt-get install fonts-noto-cjk"
        )
    elif is_linux and font_groups.get("cjk_sans") and "Microsoft YaHei" in font_groups["cjk_sans"].get("missing", []):
        recommendations.append(
            "Optional: provide Microsoft YaHei in the Linux runtime to match the default theme's Windows-like "
            "Chinese typography. Without it, output falls back to installed CJK fonts such as Noto CJK."
        )
    if font_groups.get("monospace") and not font_groups["monospace"].get("ok"):
        recommendations.append(
            "Install a monospace font for code blocks. On Debian or Ubuntu, use: "
            "sudo apt-get install fonts-cascadia-code if that package is available; "
            "otherwise provide Cascadia Code in the runtime."
        )
    elif (
        is_linux
        and font_groups.get("monospace")
        and "Cascadia Mono" in font_groups["monospace"].get("missing", [])
        and "Cascadia Code" in font_groups["monospace"].get("missing", [])
    ):
        recommendations.append(
            "Optional: install Cascadia Code on Linux for default-theme code blocks: "
            "sudo apt-get install fonts-cascadia-code if that package is available, "
            "or provide Cascadia Code in the runtime."
        )
    if font_groups.get("math") and not font_groups["math"].get("ok"):
        recommendations.append(
            "Optional: install STIX fonts for math fallback, for example: sudo apt-get install fonts-stix"
        )
    if font_groups.get("emoji") and not font_groups["emoji"].get("ok"):
        recommendations.append(
            "Provide Segoe UI Emoji in the runtime if you want the default theme's first-choice "
            "emoji glyphs. If that is not available, install another emoji font and run fc-cache -f."
        )
    elif font_groups.get("emoji") and "Segoe UI Emoji" in font_groups["emoji"].get("missing", []):
        recommendations.append(
            "Optional: provide Segoe UI Emoji if you want the default theme's preferred emoji glyphs. "
            "Existing emoji fallback fonts will still be used."
        )

    if os.name == "nt":
        env_value = result.get("environment", {}).get(WINDOWS_DLL_ENV)
        probes = result.get("native_libraries", [])
        has_complete_probe = any(probe.get("all_found") for probe in probes)
        if not env_value:
            recommendations.append(
                f"Set {WINDOWS_DLL_ENV} to the directory containing Pango/GLib/Cairo DLLs, "
                f"for example: setx {WINDOWS_DLL_ENV} \"D:\\Environment\\msys64\\mingw64\\bin\""
            )
        if not has_complete_probe:
            recommendations.append(
                "Install native WeasyPrint libraries on Windows, for example in MSYS2: "
                "pacman -S mingw-w64-x86_64-pango"
            )

    if not recommendations and result.get("ok"):
        recommendations.append("No action needed.")
    return recommendations
