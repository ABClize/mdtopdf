"""Write PDF output once, with shared diagnostics for file and string APIs."""

import os
from pathlib import Path
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
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".mdtopdf-", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        with collect_warnings(render_logs=True) as render_warnings:
            HTML(string=rendered.html, base_url=base_url).write_pdf(str(temporary))
        combined.extend(render_warnings)
        check_warnings(combined, strict=strict)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return combined
