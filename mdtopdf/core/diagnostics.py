"""Per-conversion diagnostics shared by Markdown rendering and PDF output."""

from contextlib import contextmanager
from contextvars import ContextVar
import logging


_active_warnings: ContextVar[list[dict] | None] = ContextVar("mdtopdf_warnings", default=None)


def warn(kind: str, message: str, **details) -> None:
    warnings = _active_warnings.get()
    if warnings is not None:
        warning = {"type": kind, "message": message, **details}
        if warning not in warnings:
            warnings.append(warning)


class _RenderLogHandler(logging.Handler):
    def __init__(self, warnings):
        super().__init__(logging.WARNING)
        self.warnings = warnings

    def emit(self, record):
        if _active_warnings.get() is not self.warnings:
            return
        message = record.getMessage()
        lower = message.lower()
        if "failed to load" in lower or "relative uri reference without a base" in lower:
            warn("resource_load_failed", message)
        elif "font-face" in lower and ("cannot" in lower or "failed" in lower):
            warn("font_load_failed", message)
        elif record.levelno >= logging.ERROR:
            warn("render_error", message)
        # Browser-only CSS properties in the shared theme are intentionally
        # ignored here; they are not evidence of missing document content.


@contextmanager
def collect_warnings(*, render_logs=False):
    warnings: list[dict] = []
    token = _active_warnings.set(warnings)
    logger = logging.getLogger("weasyprint")
    handler = _RenderLogHandler(warnings) if render_logs else None
    if handler is not None:
        logger.addHandler(handler)
    try:
        yield warnings
    finally:
        if handler is not None:
            logger.removeHandler(handler)
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
