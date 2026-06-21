from __future__ import annotations

import re
from typing import Callable


FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})")


def map_lines_outside_fences(markdown_text: str, convert_line: Callable[[str], str]) -> str:
    converted_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    fence_length = 0

    for line in markdown_text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        fence_match = FENCE_RE.match(content)
        if fence_match:
            marker = fence_match.group("fence")
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_marker and len(marker) >= fence_length:
                in_fence = False
            converted_lines.append(line)
            continue

        converted_lines.append(line if in_fence else convert_line(content) + newline)

    return "".join(converted_lines)


def find_inline_protected_end(line: str, start: int) -> int:
    marker_char = line[start]
    if marker_char == "`":
        end = start
        while end < len(line) and line[end] == "`":
            end += 1
        marker = line[start:end]
        closing = line.find(marker, end)
        return -1 if closing == -1 else closing + len(marker)

    if marker_char == "$":
        marker = "$$" if line.startswith("$$", start) else "$"
        pos = start + len(marker)
        while pos < len(line):
            closing = line.find(marker, pos)
            if closing == -1:
                return -1
            if closing == 0 or line[closing - 1] != "\\":
                return closing + len(marker)
            pos = closing + len(marker)

    return -1


def find_unescaped_text(text: str, needle: str, start: int = 0) -> int | None:
    pos = start
    while True:
        index = text.find(needle, pos)
        if index == -1:
            return None
        if not is_escaped_marker(text, index):
            return index
        pos = index + len(needle)


def is_escaped_marker(text: str, index: int) -> bool:
    backslashes = 0
    pos = index - 1
    while pos >= 0 and text[pos] == "\\":
        backslashes += 1
        pos -= 1
    return bool(backslashes % 2)


def html_emphasis_tags(marker_length: int) -> tuple[str, str]:
    if marker_length == 1:
        return "<em>", "</em>"
    if marker_length == 2:
        return "<strong>", "</strong>"
    return "<em><strong>", "</strong></em>"
