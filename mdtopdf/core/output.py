"""Write PDF output once, with shared diagnostics for file and string APIs."""

import os
from pathlib import Path
import stat
import tempfile

from mdtopdf.core.diagnostics import check_warnings
from mdtopdf.core.browser import render_document


def write_pdf(rendered, output: Path, *, base_url=None, warnings=(), strict=False):
    combined = [*rendered.warnings, *warnings]
    check_warnings(combined, strict=strict)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Render beside the destination, then replace only after all checks pass.
    # In particular, strict failures must leave an existing output intact.
    previous_mode = stat.S_IMODE(output.stat().st_mode) if os.name == "posix" and output.exists() else None
    # Let the renderer create a regular file respecting umask, not a mkstemp
    # file fixed at 0600. The private directory protects the unfinished output.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".mdtopdf-") as directory:
        temporary = Path(directory) / "output.pdf"
        result = render_document(rendered.html, base_url=base_url, output_path=temporary)
        combined.extend(result.warnings)
        check_warnings(combined, strict=strict)
        if previous_mode is not None:
            temporary.chmod(previous_mode)
        os.replace(temporary, output)
    return combined
