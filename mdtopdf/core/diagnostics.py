"""Per-conversion diagnostics shared by Markdown rendering and PDF output."""

from contextlib import contextmanager
from contextvars import ContextVar


_active_warnings: ContextVar[list[dict] | None] = ContextVar("mdtopdf_warnings", default=None)


def warn(kind: str, message: str, **details) -> None:
    warnings = _active_warnings.get()
    if warnings is not None:
        warning = {"type": kind, "message": message, **details}
        if warning not in warnings:
            warnings.append(warning)



@contextmanager
def collect_warnings():
    warnings: list[dict] = []
    token = _active_warnings.set(warnings)
    try:
        yield warnings
    finally:
        _active_warnings.reset(token)


class RenderWarningError(RuntimeError):
    def __init__(self, warnings):
        self.warnings = list(warnings)
        super().__init__(
            f"Strict rendering stopped because of {len(warnings)} warning(s); output was not replaced."
        )


def check_warnings(warnings, *, strict=False):
    if strict and warnings:
        raise RenderWarningError(warnings)
