"""Actionable diagram failures, separate from browser environment failures."""

from __future__ import annotations


class DiagramRenderError(RuntimeError):
    """A diagram could not be parsed or rendered by the bundled renderer."""

    error_code = "diagram_render_failed"

    def __init__(self, details: dict):
        self.error_details = dict(details)
        index = details.get("diagram_index", 1)
        location = f"Diagram {index}"
        if details.get("source_line"):
            location += f" at Markdown line {details['source_line']}"
        elif details.get("diagram_line"):
            location += f" at diagram line {details['diagram_line']}"
        elif details.get("source_start_line"):
            location += f" starting at Markdown line {details['source_start_line']}"
        message = details.get("message") or "Pele could not render this diagram."
        super().__init__(f"{location}: {message}")
        action = {
            "limit": "Simplify the diagram or split it into smaller code blocks.",
            "unsupported-diagram": "Use a diagram type and header supported by Pele.",
            "syntax": "Correct the reported diagram syntax.",
            "semantic": "Correct the conflicting or unresolved diagram declarations.",
        }.get(details.get("code"), "Check the diagram's syntax and Pele compatibility.")
        self.hint = (
            f"Check the Mermaid/mmd code block for diagram {index}. {action} "
            "See error_details for its location and source excerpt."
        )


def raise_diagram_error(details: dict) -> None:
    """Raise a browser-serialized diagram failure without losing its metadata."""
    raise DiagramRenderError(details)
