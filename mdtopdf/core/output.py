"""Write PDF output once, with shared diagnostics for file and string APIs."""

import os
from pathlib import Path
import stat
import tempfile

from mdtopdf.core.diagnostics import check_warnings, collect_warnings


def write_pdf(rendered, output: Path, *, base_url=None, warnings=(), strict=False):
    from mdtopdf.core.doctor import add_weasyprint_dll_directories

    combined = [*rendered.warnings, *warnings]
    check_warnings(combined, strict=strict)
    try:
        add_weasyprint_dll_directories()
        from weasyprint import HTML
    except Exception as exc:
        raise RuntimeError(
            "WeasyPrint could not be imported or initialized. Run "
            "`mdtopdf doctor` for native library diagnostics."
        ) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    # Render beside the destination, then replace only after all checks pass.
    # In particular, strict failures must leave an existing output intact.
    previous_mode = stat.S_IMODE(output.stat().st_mode) if os.name == "posix" and output.exists() else None
    # Let the renderer create a regular file respecting umask, not a mkstemp
    # file fixed at 0600. The private directory protects the unfinished output.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".mdtopdf-") as directory:
        temporary = Path(directory) / "output.pdf"
        with collect_warnings(render_logs=True) as render_warnings:
            HTML(string=rendered.html, base_url=base_url).write_pdf(str(temporary))
        combined.extend(render_warnings)
        check_warnings(combined, strict=strict)
        if previous_mode is not None:
            temporary.chmod(previous_mode)
        os.replace(temporary, output)
    return combined
