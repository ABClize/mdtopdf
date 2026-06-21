from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable
from urllib.parse import unquote, urlparse

from mdit_py_plugins.anchors.index import slugify

from mdtopdf.core.inline import (
    FENCE_RE,
    find_inline_protected_end,
    find_unescaped_text,
    html_emphasis_tags,
    is_escaped_marker,
    map_lines_outside_fences,
)


@dataclass(frozen=True)
class ObsidianPreprocessResult:
    markdown: str
    placeholders: dict[str, str]


_EMBED_FILE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


def protect_obsidian_code_span_emphasis(markdown_text: str) -> ObsidianPreprocessResult:
    placeholders: dict[str, str] = {}
    counter = 0

    def stash(html: str) -> str:
        nonlocal counter
        token = f"\ufffcMDTOPDFOB{counter}\ufffc"
        placeholders[token] = html
        counter += 1
        return token

    return ObsidianPreprocessResult(
        map_lines_outside_fences(
            markdown_text,
            lambda line: _protect_code_span_emphasis_line(line, stash),
        ),
        placeholders,
    )


def preprocess_obsidian_markdown(
    markdown_text: str,
    *,
    embed_resolver: Callable[[str], str] | None = None,
) -> str:
    markdown_text = _strip_yaml_frontmatter(markdown_text)
    markdown_text = _strip_html_comments(markdown_text)
    markdown_text = _strip_obsidian_comments(markdown_text)
    markdown_text = _normalize_tab_indented_lists(markdown_text)
    markdown_text = _normalize_blockquote_continuation(markdown_text)
    markdown_text = _convert_wikilinks(markdown_text, embed_resolver=embed_resolver)
    markdown_text = _normalize_loose_emphasis(markdown_text)
    return _convert_underscore_emphasis(markdown_text)


def restore_obsidian_placeholders(html: str, result: ObsidianPreprocessResult) -> str:
    for token, replacement in result.placeholders.items():
        html = html.replace(token, replacement)
    return html


def _strip_yaml_frontmatter(markdown_text: str) -> str:
    has_bom = markdown_text.startswith("\ufeff")
    body = markdown_text[1:] if has_bom else markdown_text
    lines = body.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return body

    for index, line in enumerate(lines[1:100], start=1):
        if line.strip() not in {"---", "..."}:
            continue
        frontmatter_lines = lines[1:index]
        if any(_YAML_FRONTMATTER_KEY_RE.match(item) for item in frontmatter_lines):
            return "".join(lines[index + 1 :])
        return body

    return body


def _strip_html_comments(markdown_text: str) -> str:
    return _strip_delimited_comments(markdown_text, "<!--", "-->")


def _strip_obsidian_comments(markdown_text: str) -> str:
    return _strip_delimited_comments(markdown_text, "%%", "%%")


def _strip_delimited_comments(markdown_text: str, start_marker: str, end_marker: str) -> str:
    converted_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    fence_length = 0
    in_comment = False

    for line in markdown_text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]

        if not in_comment:
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

        if in_fence:
            converted_lines.append(line)
            continue

        content, in_comment = _strip_delimited_comments_line(
            content,
            in_comment,
            start_marker,
            end_marker,
        )
        converted_lines.append(content + newline)

    return "".join(converted_lines)


def _strip_delimited_comments_line(
    line: str,
    in_comment: bool,
    start_marker: str,
    end_marker: str,
) -> tuple[str, bool]:
    output: list[str] = []
    pos = 0
    while pos < len(line):
        if in_comment:
            end = find_unescaped_text(line, end_marker, pos)
            if end is None:
                return "".join(output), True
            pos = end + len(end_marker)
            in_comment = False
            continue

        comment_start = find_unescaped_text(line, start_marker, pos)
        if comment_start is None:
            output.append(line[pos:])
            break

        code_start = line.find("`", pos)
        if code_start != -1 and code_start < comment_start:
            code_end = find_inline_protected_end(line, code_start)
            if code_end == -1:
                output.append(line[pos:])
                break
            output.append(line[pos:code_end])
            pos = code_end
            continue

        output.append(line[pos:comment_start])
        pos = comment_start + len(start_marker)
        in_comment = True

    return "".join(output), in_comment


def _normalize_tab_indented_lists(markdown_text: str) -> str:
    converted_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    fence_length = 0
    in_list_context = False
    last_list_indent_width: int | None = None
    tab_indent_map: dict[int, int] = {}

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
            in_list_context = False
            last_list_indent_width = None
            tab_indent_map.clear()
            converted_lines.append(line)
            continue

        if in_fence:
            converted_lines.append(line)
            continue

        list_match = _LIST_MARKER_RE.match(content)
        if list_match:
            indent = list_match.group("indent")
            if in_list_context and indent.count("\t") >= 3:
                indent = _canonicalize_list_indent(indent, last_list_indent_width, tab_indent_map)
                content = indent + content[len(list_match.group("indent")) :]
            else:
                tab_indent_map.clear()
            in_list_context = True
            last_list_indent_width = _markdown_indent_width(indent)
            converted_lines.append(content + newline)
            continue

        if not content.strip():
            in_list_context = False
            last_list_indent_width = None
            tab_indent_map.clear()
        converted_lines.append(line)

    return "".join(converted_lines)


def _canonicalize_list_indent(
    indent: str,
    previous_indent_width: int | None,
    tab_indent_map: dict[int, int],
) -> str:
    tab_count = indent.count("\t")
    if tab_count not in tab_indent_map:
        lower_tab_counts = [count for count in tab_indent_map if count < tab_count]
        if lower_tab_counts:
            lower_tab_count = max(lower_tab_counts)
            width = tab_indent_map[lower_tab_count] + (tab_count - lower_tab_count) * 2
        else:
            width = (previous_indent_width or 0) + 2
        tab_indent_map[tab_count] = width
    return " " * tab_indent_map[tab_count]


def _markdown_indent_width(indent: str) -> int:
    width = 0
    for char in indent:
        if char == "\t":
            width += 4 - (width % 4)
        else:
            width += 1
    return width


def _normalize_blockquote_continuation(markdown_text: str) -> str:
    converted_lines: list[str] = []
    in_fence = False
    fence_marker = ""
    fence_length = 0
    pending_quote_prefix: str | None = None

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
            pending_quote_prefix = None
            converted_lines.append(line)
            continue

        if in_fence:
            converted_lines.append(line)
            continue

        marker_match = _BLOCKQUOTE_MARKER_ONLY_RE.match(content)
        if marker_match:
            depth = marker_match.group("markers").count(">")
            pending_quote_prefix = marker_match.group("indent") + (">" * depth) + " "
            converted_lines.append(line)
            continue

        if pending_quote_prefix and _should_continue_blockquote(content):
            converted_lines.append(pending_quote_prefix + content + newline)
        else:
            converted_lines.append(line)
        pending_quote_prefix = None

    return "".join(converted_lines)


def _should_continue_blockquote(line: str) -> bool:
    if not line.strip():
        return False
    stripped = line.lstrip()
    if stripped.startswith(">"):
        return False
    return not _BLOCKQUOTE_CONTINUATION_BLOCK_START_RE.match(stripped)


def build_resource_resolver(
    base_url: str | Path | None,
    source: Path,
    resource_dir: str | Path | None = None,
) -> Callable[[str], str]:
    """Return a resolver for bare local image targets.

    ``base_url`` is still the renderer's base path. ``resource_dir`` is an
    explicit lookup directory for bare image names such as ``![[image.png]]`` or
    ``![](image.png)``. Targets that already include a directory component are
    left unchanged.
    """

    if resource_dir is None:
        return lambda target: target

    lookup_dir = resolve_resource_dir(resource_dir)
    href_base_path = _local_base_path(base_url) or source.resolve().parent
    cache: dict[str, str] = {}

    def resolve(target: str) -> str:
        normalized = target.strip().replace("\\", "/")
        if not normalized or normalized in cache:
            return cache.get(normalized, normalized)
        if (
            _has_url_scheme(normalized)
            or normalized.startswith("#")
            or not _looks_like_file_embed(normalized)
            or not _is_bare_resource_target(normalized)
        ):
            cache[normalized] = normalized
            return normalized

        candidate = lookup_dir / Path(unquote(normalized)).name
        if not candidate.exists():
            cache[normalized] = normalized
            return normalized

        cache[normalized] = _href_for_candidate(candidate.resolve(), href_base_path)
        return cache[normalized]

    return resolve


def resolve_resource_dir(resource_dir: str | Path | None) -> Path | None:
    """Normalize and validate an optional local resource lookup directory."""

    if resource_dir is None:
        return None

    path = Path(resource_dir).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Resource directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Resource path is not a directory: {path}")
    return path


def build_obsidian_embed_resolver(
    base_url: str | Path | None,
    source: Path,
    resource_dir: str | Path | None = None,
) -> Callable[[str], str]:
    """Backward-compatible alias for the file resource resolver."""

    return build_resource_resolver(base_url, source, resource_dir)


def format_resource_href(target: str) -> str:
    """Format a local resource path for Markdown/HTML href attributes."""

    return target.replace(" ", "%20")


def _convert_wikilinks(
    markdown_text: str,
    *,
    embed_resolver: Callable[[str], str] | None = None,
) -> str:
    return map_lines_outside_fences(
        markdown_text,
        lambda line: _convert_wikilinks_line(line, embed_resolver=embed_resolver),
    )


def _convert_wikilinks_line(
    line: str,
    *,
    embed_resolver: Callable[[str], str] | None = None,
) -> str:
    parts: list[str] = []
    pos = 0
    while pos < len(line):
        if line[pos] != "`":
            next_tick = line.find("`", pos)
            end = len(line) if next_tick == -1 else next_tick
            parts.append(_convert_wikilinks_segment(line[pos:end], embed_resolver=embed_resolver))
            pos = end
            continue

        protected_end = find_inline_protected_end(line, pos)
        if protected_end == -1:
            parts.append(_convert_wikilinks_segment(line[pos:], embed_resolver=embed_resolver))
            break
        parts.append(line[pos:protected_end])
        pos = protected_end

    return "".join(parts)


def _convert_wikilinks_segment(
    segment: str,
    *,
    embed_resolver: Callable[[str], str] | None = None,
) -> str:
    output: list[str] = []
    pos = 0
    while pos < len(segment):
        start = segment.find("[[", pos)
        if start == -1:
            output.append(segment[pos:])
            break
        end = segment.find("]]", start + 2)
        if end == -1:
            output.append(segment[pos:])
            break
        output.append(segment[pos:start])
        is_embed = start > 0 and segment[start - 1] == "!"
        replacement = _format_wikilink(
            segment[start + 2 : end],
            href_resolver=embed_resolver if is_embed else None,
        )
        output.append(replacement or segment[start : end + 2])
        pos = end + 2
    return "".join(output)


def _format_wikilink(
    inner: str,
    *,
    href_resolver: Callable[[str], str] | None = None,
) -> str | None:
    target, label = _split_wikilink(inner)
    target = target.strip()
    label = (label or target).strip()
    if not target or not label:
        return None
    if href_resolver is not None:
        target = href_resolver(target)
    return f"[{_escape_markdown_link_label(label)}]({_wikilink_href(target)})"


def _split_wikilink(inner: str) -> tuple[str, str | None]:
    for index, char in enumerate(inner):
        if char != "|":
            continue
        if index > 0 and inner[index - 1] == "\\":
            return inner[: index - 1], inner[index + 1 :]
        return inner[:index], inner[index + 1 :]
    return inner, None


def _escape_markdown_link_label(label: str) -> str:
    label = label.replace(r"\|", "|")
    return label.replace("\\", "\\\\").replace("[", r"\[").replace("]", r"\]").replace("|", r"\|")


def _wikilink_href(target: str) -> str:
    if target.startswith("#"):
        return "#" + slugify(target[1:])
    return format_resource_href(target)


def _local_base_path(base_url: str | Path | None) -> Path | None:
    if base_url is None:
        return None
    value = str(base_url)
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return None
    if parsed.scheme == "file":
        from urllib.request import url2pathname

        return Path(url2pathname(parsed.path)).expanduser().resolve()
    return Path(value).expanduser().resolve()


def _has_url_scheme(target: str) -> bool:
    return bool(urlparse(target).scheme)


def _looks_like_file_embed(target: str) -> bool:
    return Path(unquote(target).replace("/", "\\")).suffix.lower() in _EMBED_FILE_EXTENSIONS


def _is_bare_resource_target(target: str) -> bool:
    target_path = Path(unquote(target).replace("/", "\\"))
    return target_path.parent == Path(".")


def _href_for_candidate(candidate: Path, base_path: Path) -> str:
    try:
        return candidate.relative_to(base_path).as_posix()
    except ValueError:
        return candidate.as_uri()


def _normalize_loose_emphasis(markdown_text: str) -> str:
    return map_lines_outside_fences(markdown_text, _normalize_loose_emphasis_line)


def _normalize_loose_emphasis_line(line: str) -> str:
    parts: list[str] = []
    pos = 0
    while pos < len(line):
        next_special = _find_next_inline_protected_start(line, pos)
        if next_special == -1:
            parts.append(_normalize_loose_emphasis_segment(line[pos:]))
            break
        parts.append(_normalize_loose_emphasis_segment(line[pos:next_special]))
        protected_end = find_inline_protected_end(line, next_special)
        if protected_end == -1:
            parts.append(line[next_special:])
            break
        parts.append(line[next_special:protected_end])
        pos = protected_end

    return "".join(parts)


def _normalize_loose_emphasis_segment(segment: str) -> str:
    output: list[str] = []
    pos = 0
    while pos < len(segment):
        marker_char = segment[pos]
        if marker_char not in {"*", "_"} or is_escaped_marker(segment, pos):
            output.append(marker_char)
            pos += 1
            continue

        run_end = pos
        while run_end < len(segment) and segment[run_end] == marker_char:
            run_end += 1
        marker_length = run_end - pos
        if marker_length not in {1, 2, 3}:
            output.append(segment[pos:run_end])
            pos = run_end
            continue

        marker = marker_char * marker_length
        closing = segment.find(marker, run_end)
        if closing == -1:
            output.append(segment[pos:run_end])
            pos = run_end
            continue

        content = segment[run_end:closing]
        end = closing + marker_length
        if _should_normalize_loose_emphasis(content):
            stripped = content.rstrip()
            trailing = content[len(stripped) :]
            converted_content = _normalize_loose_emphasis_segment(stripped)
            output.append(marker + converted_content + marker + trailing)
            pos = end
            continue

        output.append(segment[pos:end])
        pos = end

    return "".join(output)


def _should_normalize_loose_emphasis(content: str) -> bool:
    stripped = content.rstrip()
    return bool(stripped) and not content[0].isspace() and len(stripped) < len(content)


def _protect_code_span_emphasis_line(line: str, stash: Callable[[str], str]) -> str:
    output: list[str] = []
    pos = 0
    while pos < len(line):
        if line[pos] == "`":
            protected_end = find_inline_protected_end(line, pos)
            if protected_end == -1:
                output.append(line[pos:])
                break
            output.append(line[pos:protected_end])
            pos = protected_end
            continue

        if line[pos] not in {"*", "_"}:
            output.append(line[pos])
            pos += 1
            continue

        marker_char = line[pos]
        run_end = pos
        while run_end < len(line) and line[run_end] == marker_char:
            run_end += 1
        if is_escaped_marker(line, pos):
            output.append(line[pos:run_end])
            pos = run_end
            continue

        marker_length = run_end - pos
        if marker_length not in {1, 2, 3}:
            output.append(line[pos:run_end])
            pos = run_end
            continue

        marker = marker_char * marker_length
        code_end = (
            find_inline_protected_end(line, run_end)
            if run_end < len(line) and line[run_end] == "`"
            else -1
        )
        if code_end != -1 and line.startswith(marker, code_end):
            open_tags, close_tags = html_emphasis_tags(marker_length)
            output.append(stash(open_tags) + line[run_end:code_end] + stash(close_tags))
            pos = code_end + marker_length
            continue

        output.append(line[pos:run_end])
        pos = run_end

    return "".join(output)


def _convert_underscore_emphasis(markdown_text: str) -> str:
    return map_lines_outside_fences(markdown_text, _convert_underscore_emphasis_line)


def _convert_underscore_emphasis_line(line: str) -> str:
    parts: list[str] = []
    pos = 0
    while pos < len(line):
        next_special = _find_next_inline_protected_start(line, pos)
        if next_special == -1:
            parts.append(_convert_underscore_emphasis_segment(line[pos:]))
            break
        parts.append(_convert_underscore_emphasis_segment(line[pos:next_special]))
        protected_end = find_inline_protected_end(line, next_special)
        if protected_end == -1:
            parts.append(line[next_special:])
            break
        parts.append(line[next_special:protected_end])
        pos = protected_end

    return "".join(parts)


def _convert_underscore_emphasis_segment(segment: str) -> str:
    output: list[str] = []
    pos = 0
    while pos < len(segment):
        if segment[pos] != "_" or is_escaped_marker(segment, pos):
            output.append(segment[pos])
            pos += 1
            continue

        run_end = pos
        while run_end < len(segment) and segment[run_end] == "_":
            run_end += 1
        marker_length = run_end - pos
        if marker_length not in {1, 2, 3}:
            output.append(segment[pos:run_end])
            pos = run_end
            continue

        marker = "_" * marker_length
        closing = segment.find(marker, run_end)
        if closing == -1:
            output.append(segment[pos:run_end])
            pos = run_end
            continue

        content = segment[run_end:closing]
        end = closing + marker_length
        if _should_convert_underscore_emphasis(segment, pos, end, content):
            replacement = "*" * marker_length
            converted_content = _convert_underscore_emphasis_segment(content)
            output.append(replacement + converted_content + replacement)
            pos = end
            continue

        output.append(segment[pos:run_end])
        pos = run_end

    return "".join(output)


def _find_next_inline_protected_start(line: str, start: int) -> int:
    candidates = [index for index in (line.find("`", start), line.find("$", start)) if index != -1]
    return min(candidates) if candidates else -1


def _should_convert_underscore_emphasis(source: str, start: int, end: int, content: str) -> bool:
    if not content or content[0].isspace() or content[-1].isspace():
        return False
    previous_char = source[start - 1] if start > 0 else ""
    next_char = source[end] if end < len(source) else ""
    return any(ord(char) > 127 for char in previous_char + content + next_char)


_LIST_MARKER_RE = re.compile(r"^(?P<indent>[ \t]*)(?:[-+*]|\d+[.)])\s+")
_YAML_FRONTMATTER_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+:\s*")
_BLOCKQUOTE_MARKER_ONLY_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<markers>(?:>\s*)+)$")
_BLOCKQUOTE_CONTINUATION_BLOCK_START_RE = re.compile(
    r"^(?:#{1,6}\s|[-+*]\s|\d+[.)]\s|`{3,}|~{3,}|\|)"
)
