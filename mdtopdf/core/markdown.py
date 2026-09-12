"""Markdown rendering helpers for the mdtopdf conversion pipeline."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from html import escape, unescape
from importlib import resources
import re
from typing import Callable, Iterable

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors.index import slugify
from mdit_py_plugins.amsmath import amsmath_plugin
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from mdtopdf.core.inline import (
    FENCE_RE,
    find_inline_protected_end,
    find_unescaped_text,
    html_emphasis_tags,
    is_escaped_marker,
    map_lines_outside_fences,
    protect_code_blocks,
    restore_code_blocks,
)
from mdtopdf.core.diagnostics import collect_warnings
from mdtopdf.core.katex import load_katex_css
from mdtopdf.core.obsidian import (
    format_resource_href,
    preprocess_obsidian_markdown,
    protect_obsidian_code_span_emphasis,
    restore_obsidian_placeholders,
)


DEFAULT_THEME = "default"
SUPPORTED_THEMES = (DEFAULT_THEME,)
PAGE_MARGIN_FONT_FAMILY = (
    '"Segoe UI", Arial, "Liberation Sans", "DejaVu Sans", '
    '"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", '
    '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif'
)


@dataclass(frozen=True)
class RenderedHTML:
    """Complete HTML rendering result.

    Attributes:
        title: Resolved document title.
        body: Rendered HTML body fragment.
        css: Combined CSS used by the full document.
        html: Complete static HTML document.
    """

    title: str
    body: str
    css: str
    html: str
    warnings: list[dict] = field(default_factory=list)


def available_themes() -> list[str]:
    """Return the built-in theme names bundled with the package."""

    return list(SUPPORTED_THEMES)


def load_theme_css(theme: str = DEFAULT_THEME) -> str:
    """Load CSS for a bundled theme.

    Args:
        theme: Built-in theme name.

    Returns:
        The theme CSS text.

    Raises:
        ValueError: If the theme name is not bundled with the package.
    """

    if theme not in SUPPORTED_THEMES:
        supported = ", ".join(SUPPORTED_THEMES)
        raise ValueError(f"Unknown theme '{theme}'. Supported themes: {supported}")

    themes_dir = resources.files("mdtopdf").joinpath("themes")
    return themes_dir.joinpath(f"{DEFAULT_THEME}.css").read_text(encoding="utf-8")


def load_custom_css(path: str) -> str:
    """Read a caller-provided CSS file as UTF-8 text."""

    from pathlib import Path

    css_path = Path(path).expanduser()
    if not css_path.exists():
        raise FileNotFoundError(f"Custom CSS file not found: {css_path}")
    return css_path.read_text(encoding="utf-8")


def compose_css(
    theme_css: str,
    custom_css: str | None = None,
    *,
    page_header: str | None = None,
    page_footer: str | None = None,
    page_numbers: bool = False,
    lang: str = "zh-Hans",
) -> str:
    """Combine theme, math, code highlight, page margin, and custom CSS.

    Custom CSS is appended last so callers can override the default theme.
    """

    parts = [
        theme_css,
        load_katex_css(),
        _pygments_css(),
        _page_margin_css(page_header, page_footer, page_numbers, lang=lang),
    ]
    if custom_css:
        parts.append(custom_css)
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def render_markdown_to_html(
    markdown_text: str,
    *,
    title: str | None = None,
    theme: str = DEFAULT_THEME,
    custom_css: str | None = None,
    unsafe_html: bool = False,
    page_header: str | None = None,
    page_footer: str | None = None,
    include_page_header: bool = True,
    include_page_footer: bool = True,
    page_numbers: bool = True,
    obsidian_embed_resolver: Callable[[str], str] | None = None,
    _defer_browser: bool = False,
    _browser_base_url: str | Path | None = None,
) -> RenderedHTML:
    """Render Markdown text to a full Obsidian-compatible HTML document.

    The renderer keeps raw HTML disabled by default, then applies a constrained
    safe HTML allowlist plus Obsidian-oriented preprocessing for frontmatter,
    comments, wikilinks, callouts, soft breaks, nested emphasis, KaTeX math, and
    Mermaid diagrams.

    Args:
        markdown_text: Source Markdown text.
        title: Optional document title. If omitted, the first level-one heading
            is used before falling back to "Markdown Document".
        theme: Built-in theme name.
        custom_css: Optional raw CSS appended after built-in styles.
        unsafe_html: Allow arbitrary raw HTML in the Markdown source.
        page_header: Header text for paged output. Defaults to the title.
        page_footer: Optional footer text for paged output.
        include_page_header: Whether to include page header CSS.
        include_page_footer: Whether to include page footer CSS.
        page_numbers: Whether the footer includes the current page number.
        obsidian_embed_resolver: Optional resolver for Obsidian ``![[...]]``
            embed targets and generated image ``src`` attributes.

    Returns:
        A ``RenderedHTML`` object with the body fragment, combined CSS, and full
        HTML document.
    """

    resolved_title = title or infer_title(markdown_text) or "Markdown Document"
    resolved_header = page_header if page_header is not None else resolved_title
    resolved_footer = page_footer or None
    protected_source, code_blocks = protect_code_blocks(markdown_text)
    obsidian_result = protect_obsidian_code_span_emphasis(protected_source)
    if unsafe_html:
        protected_markdown = obsidian_result.markdown
        safe_html_placeholders: dict[str, str] = {}
    else:
        protected_markdown, safe_html_placeholders = _protect_safe_html(obsidian_result.markdown)
        protected_markdown = _protect_safe_html_emphasis(protected_markdown, safe_html_placeholders)
    protected_markdown = preprocess_obsidian_markdown(
        protected_markdown,
        embed_resolver=obsidian_embed_resolver,
    )
    md = _build_markdown_renderer(unsafe_html=unsafe_html)
    protected_markdown = restore_code_blocks(protected_markdown, code_blocks)
    with collect_warnings() as warnings:
        body = md.render(protected_markdown)
    body = _restore_placeholders(body, safe_html_placeholders)
    body = restore_obsidian_placeholders(body, obsidian_result)
    body = _unwrap_safe_block_tags(body)
    body = _replace_obsidian_callouts(body)
    body = _replace_task_checkboxes(body)
    if obsidian_embed_resolver is not None:
        body = _resolve_image_sources(body, obsidian_embed_resolver)
    body = _wrap_emoji_text(body)
    css = compose_css(
        load_theme_css(theme),
        custom_css,
        page_header=resolved_header if include_page_header else None,
        page_footer=resolved_footer if include_page_footer else None,
        page_numbers=page_numbers if include_page_footer else False,
        lang=infer_document_lang(markdown_text),
    )
    html = _build_document(resolved_title, body, css, lang=infer_document_lang(markdown_text))
    if not _defer_browser and ('data-mdtopdf-math=' in body or 'data-mdtopdf-mermaid=' in body):
        from mdtopdf.core.browser import render_document
        result = render_document(html, base_url=_browser_base_url)
        body = result.body
        warnings.extend(result.warnings)
        html = _build_document(resolved_title, body, css, lang=infer_document_lang(markdown_text))
    return RenderedHTML(title=resolved_title, body=body, css=css, html=html, warnings=warnings)


def _resolve_image_sources(html: str, resource_resolver: Callable[[str], str]) -> str:
    def replace(match: re.Match[str]) -> str:
        prefix, src, suffix = match.groups()
        original = unescape(src)
        resolved = resource_resolver(original)
        if resolved == original:
            return match.group(0)
        return f'{prefix}{escape(format_resource_href(resolved), quote=True)}{suffix}'

    return _IMG_SRC_RE.sub(replace, html)


def infer_title(markdown_text: str) -> str | None:
    for line in markdown_text.splitlines():
        line = line.removeprefix("\ufeff")
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return re.sub(r"\s+#*$", "", match.group(1)).strip() or None
    return None


def infer_document_lang(markdown_text: str) -> str:
    cjk_count = sum(1 for char in markdown_text if _is_cjk_char(char))
    latin_count = sum(1 for char in markdown_text if ("A" <= char <= "Z") or ("a" <= char <= "z"))
    if cjk_count and cjk_count >= max(4, latin_count // 4):
        return "zh-Hans"
    return "en"


def _is_cjk_char(char: str) -> bool:
    return (
        "\u3400" <= char <= "\u4dbf"
        or "\u4e00" <= char <= "\u9fff"
        or "\uf900" <= char <= "\ufaff"
    )


def _build_markdown_renderer(*, unsafe_html: bool = False) -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": unsafe_html, "breaks": True})
    md.enable(["table", "strikethrough"])
    md.use(_mark_plugin)
    md.use(tasklists_plugin, enabled=True)
    md.use(footnote_plugin)
    md.use(dollarmath_plugin, renderer=_render_math)
    md.use(amsmath_plugin, renderer=_render_amsmath)
    md.use(anchors_plugin, max_level=6, slug_func=_slugify_heading, permalink=False)
    md.renderer.rules["fence"] = _render_fence
    return md


def _render_fence(
    tokens: list[Token],
    idx: int,
    options,
    env,
) -> str:
    token = tokens[idx]
    lang = token.info.strip().split(maxsplit=1)[0] if token.info else ""
    if lang.lower() in {"mermaid", "mmd"}:
        encoded = base64.b64encode(token.content.encode("utf-8")).decode("ascii")
        return f'<figure class="mermaid-diagram" data-mdtopdf-mermaid="{encoded}"></figure>\n'
    return highlight_code(token.content, lang)


def highlight_code(code: str, lang: str | None = None) -> str:
    language = (lang or "text").strip()
    try:
        lexer = get_lexer_by_name(language) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
        language = "text"

    formatter = HtmlFormatter(nowrap=True)
    highlighted = highlight(code, lexer, formatter).rstrip("\n")
    safe_language = escape(language, quote=True)
    return f'<pre class="highlight"><code class="language-{safe_language}">{highlighted}</code></pre>\n'


def _render_math(content: str, options: dict) -> str:
    display = "block" if options.get("display_mode") else "inline"
    return latex_to_html_math(content, display=display)


def _render_amsmath(content: str) -> str:
    return latex_to_html_math(content, display="block")


def latex_to_html_math(content: str, *, display: str = "inline") -> str:
    latex = _strip_latex_comments(content).strip()
    if not latex:
        return ""
    encoded = base64.b64encode(latex.encode("utf-8")).decode("ascii")
    return f'<span data-mdtopdf-math="{encoded}" data-display="{display}"></span>'


def _strip_latex_comments(content: str) -> str:
    lines = []
    for line in content.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("%"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _slugify_heading(title: str) -> str:
    return slugify(title)


def _mark_plugin(md: MarkdownIt) -> None:
    def tokenize(state, silent: bool) -> bool:
        start = state.pos
        if state.src[start : start + 2] != "==":
            return False
        content_start = start + 2
        end = state.src.find("==", content_start)
        if end <= content_start:
            return False
        if state.src[content_start].isspace() or state.src[end - 1].isspace():
            return False

        if not silent:
            token = state.push("mark_open", "mark", 1)
            token.markup = "=="
            old_pos = state.pos
            old_max = state.posMax
            state.pos = content_start
            state.posMax = end
            state.md.inline.tokenize(state)
            token = state.push("mark_close", "mark", -1)
            token.markup = "=="
            state.pos = old_pos
            state.posMax = old_max

        state.pos = end + 2
        return True

    md.inline.ruler.before("strikethrough", "mark", tokenize)


_SAFE_TAG_RE = re.compile(
    r"<(?P<closing>/)?(?P<tag>kbd|big|small|sup|sub|mark|strong|em|b|i|u|s|del|ins|span|ruby|rt|rp|abbr|font)(?P<attrs>\s+[^<>]*)?>",
    re.IGNORECASE,
)
_KBD_SPAN_RE = re.compile(r"<kbd(?:\s+[^<>]*)?>.*?</kbd>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_VOID_SAFE_TAG_RE = re.compile(r"<(?P<tag>hr|wbr)\s*/?>", re.IGNORECASE)
_COLOR_ATTR_RE = re.compile(
    r"""\bcolor\s*=\s*(?:"(?P<double>[^"]+)"|'(?P<single>[^']+)'|(?P<bare>[^\s"'>]+))""",
    re.IGNORECASE,
)
_STYLE_ATTR_RE = re.compile(
    r"""\bstyle\s*=\s*(?:"(?P<double>[^"]+)"|'(?P<single>[^']+)'|(?P<bare>[^\s"'>]+))""",
    re.IGNORECASE,
)
_TITLE_ATTR_RE = re.compile(
    r"""\btitle\s*=\s*(?:"(?P<double>[^"]+)"|'(?P<single>[^']+)'|(?P<bare>[^\s"'>]+))""",
    re.IGNORECASE,
)
_STYLE_COLOR_RE = re.compile(r"\bcolor\s*:\s*(?P<color>[^;]+)", re.IGNORECASE)
_COLOR_STYLE_TAGS = {"span", "strong", "em", "b", "i", "u", "s", "del", "ins", "mark"}
_SAFE_HTML_PLACEHOLDER_RE = re.compile(r"\ufffcMDTOPDF\d+\ufffc")


def _protect_safe_html(markdown_text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}
    counter = 0

    def stash(html: str) -> str:
        nonlocal counter
        token = f"\ufffcMDTOPDF{counter}\ufffc"
        placeholders[token] = html
        counter += 1
        return token

    protected_lines: list[str] = []
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
            protected_lines.append(line)
            continue

        if in_fence:
            protected_lines.append(line)
            continue

        protected_lines.append(_protect_safe_html_line(content, stash) + newline)

    return "".join(protected_lines), placeholders


def _protect_safe_html_emphasis(markdown_text: str, placeholders: dict[str, str]) -> str:
    if not placeholders:
        return markdown_text

    def stash(html: str) -> str:
        token = f"\ufffcMDTOPDF{len(placeholders)}\ufffc"
        placeholders[token] = html
        return token

    return map_lines_outside_fences(
        markdown_text,
        lambda line: _protect_safe_html_emphasis_line(line, stash),
    )


def _protect_safe_html_emphasis_line(line: str, stash: Callable[[str], str]) -> str:
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

        if line[pos] not in {"*", "_"} or is_escaped_marker(line, pos):
            output.append(line[pos])
            pos += 1
            continue

        run_end = pos
        while run_end < len(line) and line[run_end] == line[pos]:
            run_end += 1
        marker_length = run_end - pos
        if marker_length not in {1, 2, 3}:
            output.append(line[pos:run_end])
            pos = run_end
            continue
        if not _is_safe_html_emphasis_opener(line, pos, run_end):
            output.append(line[pos:run_end])
            pos = run_end
            continue

        marker = line[pos:run_end]
        closing = find_unescaped_text(line, marker, run_end)
        if closing is None:
            output.append(line[pos:run_end])
            pos = run_end
            continue

        content = line[run_end:closing]
        if _SAFE_HTML_PLACEHOLDER_RE.search(content):
            open_tags, close_tags = html_emphasis_tags(marker_length)
            output.append(stash(open_tags) + content + stash(close_tags))
            pos = closing + marker_length
            continue

        output.append(line[pos:run_end])
        pos = run_end

    return "".join(output)


def _is_safe_html_emphasis_opener(line: str, _start: int, end: int) -> bool:
    return end < len(line) and not line[end].isspace()


def _protect_safe_html_line(line: str, stash: Callable[[str], str]) -> str:
    parts: list[str] = []
    pos = 0
    while pos < len(line):
        if line[pos] != "`":
            next_tick = line.find("`", pos)
            kbd_span = _find_kbd_span_containing(line, pos, next_tick)
            if kbd_span:
                if kbd_span.start() > pos:
                    parts.append(_protect_safe_html_segment(line[pos : kbd_span.start()], stash))
                parts.append(_protect_safe_html_segment(line[kbd_span.start() : kbd_span.end()], stash))
                pos = kbd_span.end()
                continue
            end = len(line) if next_tick == -1 else next_tick
            parts.append(_protect_safe_html_segment(line[pos:end], stash))
            pos = end
            continue

        tick_end = pos
        while tick_end < len(line) and line[tick_end] == "`":
            tick_end += 1
        marker = line[pos:tick_end]
        closing = line.find(marker, tick_end)
        if closing == -1:
            parts.append(_protect_safe_html_segment(line[pos:], stash))
            break
        parts.append(line[pos : closing + len(marker)])
        pos = closing + len(marker)

    return "".join(parts)


def _find_kbd_span_containing(line: str, start: int, index: int) -> re.Match[str] | None:
    if index == -1:
        return None
    for match in _KBD_SPAN_RE.finditer(line, start):
        if match.start() <= index < match.end():
            return match
        if match.start() > index:
            break
    return None


def _protect_safe_html_segment(segment: str, stash: Callable[[str], str]) -> str:
    segment = _BR_RE.sub(lambda _match: stash("<br>"), segment)
    segment = _VOID_SAFE_TAG_RE.sub(lambda match: stash(f"<{match.group('tag').lower()}>"), segment)
    segment = _protect_balanced_safe_tags(segment, stash)
    return segment


def _protect_balanced_safe_tags(segment: str, stash: Callable[[str], str]) -> str:
    matches = list(_SAFE_TAG_RE.finditer(segment))
    if not matches:
        return segment

    protected: set[int] = set()
    stack: list[tuple[str, int]] = []
    for index, match in enumerate(matches):
        tag = match.group("tag").lower()
        is_closing = match.group(0).startswith("</")
        if not is_closing:
            if _sanitize_safe_html_tag(match):
                stack.append((tag, index))
            continue
        if stack and stack[-1][0] == tag:
            _open_tag, open_index = stack.pop()
            protected.add(open_index)
            protected.add(index)

    parts: list[str] = []
    pos = 0
    kbd_depth = 0
    for index, match in enumerate(matches):
        text = segment[pos : match.start()]
        if kbd_depth:
            text = _protect_kbd_text(text, stash)
        parts.append(text)
        safe_tag = _sanitize_safe_html_tag(match)
        is_protected = index in protected and safe_tag
        parts.append(stash(safe_tag) if is_protected else match.group(0))
        if is_protected and match.group("tag").lower() == "kbd":
            if match.group("closing"):
                kbd_depth = max(0, kbd_depth - 1)
            else:
                kbd_depth += 1
        pos = match.end()
    tail = segment[pos:]
    if kbd_depth:
        tail = _protect_kbd_text(tail, stash)
    parts.append(tail)
    return "".join(parts)


def _protect_kbd_text(text: str, stash: Callable[[str], str]) -> str:
    return text.replace("$", stash("$")).replace("`", stash("`"))


def _sanitize_safe_html_tag(match: re.Match[str]) -> str | None:
    tag = match.group("tag").lower()
    attrs = match.group("attrs") or ""
    if match.group("closing"):
        return "</span>" if tag == "font" else f"</{tag}>"
    if tag == "font":
        color = _extract_color_attribute(attrs)
        if not color:
            return None
        return f'<span style="color: {color};">'
    if tag == "abbr":
        if not attrs:
            return "<abbr>"
        title = _extract_title_attribute(attrs)
        if not title:
            return None
        return f'<abbr title="{title}">'
    if attrs:
        color = _extract_style_color(attrs)
        if not color or tag not in _COLOR_STYLE_TAGS:
            return None
        return f'<{tag} style="color: {color};">'
    return f"<{tag}>"


def _extract_color_attribute(attrs: str) -> str | None:
    match = _COLOR_ATTR_RE.search(attrs)
    if not match:
        return None
    value = match.group("double") or match.group("single") or match.group("bare") or ""
    return _sanitize_color_value(value)


def _extract_style_color(attrs: str) -> str | None:
    match = _STYLE_ATTR_RE.search(attrs)
    if not match:
        return None
    style = match.group("double") or match.group("single") or match.group("bare") or ""
    color_match = _STYLE_COLOR_RE.search(style)
    if not color_match:
        return None
    return _sanitize_color_value(color_match.group("color"))


def _extract_title_attribute(attrs: str) -> str | None:
    match = _TITLE_ATTR_RE.search(attrs)
    if not match:
        return None
    value = match.group("double") or match.group("single") or match.group("bare") or ""
    return escape(value, quote=True)


def _sanitize_color_value(value: str) -> str | None:
    color = value.strip()
    if re.fullmatch(r"[A-Za-z]+", color):
        return color.lower()
    if re.fullmatch(r"#[0-9A-Fa-f]{3,8}", color):
        return color
    if re.fullmatch(r"(?:rgb|rgba|hsl|hsla)\([0-9.,%\s+-]+\)", color, re.IGNORECASE):
        return color
    return None


def _unwrap_safe_block_tags(html: str) -> str:
    return re.sub(r"<p>\s*(<hr>)\s*</p>", r"\1", html)


def _replace_obsidian_callouts(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        inner = match.group("inner")
        if not inner.startswith("<p>"):
            return match.group(0)

        paragraph_end = inner.find("</p>")
        if paragraph_end == -1:
            return match.group(0)

        first_paragraph = inner[3:paragraph_end].lstrip()
        marker_match = _CALLOUT_MARKER_RE.match(first_paragraph)
        if not marker_match:
            return match.group(0)

        callout_type = marker_match.group("type").lower()
        fold = marker_match.group("fold")
        after_marker = marker_match.group("after").strip()
        parts = _CALLOUT_BREAK_RE.split(after_marker, maxsplit=1)
        title_html = parts[0].strip() or _default_callout_title(callout_type)
        first_body = parts[1].strip() if len(parts) == 2 else ""
        remaining = inner[paragraph_end + len("</p>") :].lstrip("\n")

        classes = ["callout", f"callout-{callout_type}"]
        if fold == "+":
            classes.append("callout-expanded")
        elif fold == "-":
            classes.append("callout-collapsed")

        content = [f'<p class="callout-title">{title_html}</p>']
        if first_body:
            content.append(f"<p>{first_body}</p>")
        if remaining:
            content.append(remaining)

        safe_type = escape(callout_type, quote=True)
        safe_classes = " ".join(classes)
        return (
            f'<blockquote class="{safe_classes}" data-callout="{safe_type}">\n'
            + "\n".join(content)
            + "\n</blockquote>"
        )

    return _CALLOUT_BLOCKQUOTE_RE.sub(replace, html)


def _default_callout_title(callout_type: str) -> str:
    return _CALLOUT_TITLES.get(callout_type, callout_type.replace("-", " ").title())


def _restore_placeholders(html: str, placeholders: dict[str, str]) -> str:
    for token, replacement in placeholders.items():
        html = html.replace(token, replacement)
    return html


def _replace_task_checkboxes(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        checked = "checked" in attrs
        css_class = "task-checkbox checked" if checked else "task-checkbox"
        return f'<span class="{css_class}"></span> '

    return re.sub(
        r'<input class="task-list-item-checkbox"(?P<attrs>[^>]*)>\s*',
        replace,
        html,
    )


def _wrap_emoji_text(html: str) -> str:
    parts: list[str] = []
    skip_stack: list[str] = []

    for part in _HTML_TAG_TOKEN_RE.split(html):
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            _update_emoji_skip_stack(part, skip_stack)
            parts.append(part)
            continue
        if skip_stack:
            parts.append(part)
            continue
        parts.append(_EMOJI_TEXT_RE.sub(_emoji_span, part))

    return "".join(parts)


def _update_emoji_skip_stack(tag_html: str, skip_stack: list[str]) -> None:
    match = _HTML_TAG_NAME_RE.match(tag_html)
    if not match:
        return

    tag = match.group("tag").lower()
    if tag not in _EMOJI_SKIP_TAGS:
        return

    is_closing = tag_html.startswith("</")
    if is_closing:
        for index in range(len(skip_stack) - 1, -1, -1):
            if skip_stack[index] == tag:
                del skip_stack[index]
                break
        return

    if tag_html.rstrip().endswith("/>") or tag in _VOID_HTML_TAGS:
        return
    skip_stack.append(tag)


def _emoji_span(match: re.Match[str]) -> str:
    return f'<span class="mdtopdf-emoji">{match.group(0)}</span>'


def _pygments_css() -> str:
    formatter = HtmlFormatter()
    return formatter.get_style_defs(".highlight")


def _page_margin_css(page_header: str | None, page_footer: str | None, page_numbers: bool, *, lang: str = "zh-Hans") -> str:
    if not page_header and not page_footer and not page_numbers:
        return ""

    rules = ["@page {"]
    if page_header:
        rules.extend(
            [
                "  @top-center {",
                f"    content: {_css_string(page_header)};",
                '    color: #6b7280;',
                f"    font-family: {PAGE_MARGIN_FONT_FAMILY};",
                '    font-size: 8.5pt;',
                '    vertical-align: middle;',
                "  }",
            ]
        )

    footer_content = _page_footer_content(page_footer, page_numbers, lang=lang)
    if footer_content:
        rules.extend(
            [
                "  @bottom-center {",
                f"    content: {footer_content};",
                '    color: #6b7280;',
                f"    font-family: {PAGE_MARGIN_FONT_FAMILY};",
                '    font-size: 8.5pt;',
                '    vertical-align: middle;',
                "  }",
            ]
        )

    rules.append("}")
    return "\n".join(rules)


def _page_footer_content(page_footer: str | None, page_numbers: bool, *, lang: str = "zh-Hans") -> str | None:
    if page_numbers and not lang.startswith("zh"):
        prefix = (page_footer + " · ") if page_footer else ""
        return f'{_css_string(prefix + "Page ")} counter(page) " of " counter(pages)'
    if page_footer and page_numbers:
        return f'{_css_string(page_footer + " · 第 ")} counter(page) " 页 / 共 " counter(pages) " 页"'
    if page_footer:
        return _css_string(page_footer)
    if page_numbers:
        return '"第 " counter(page) " 页 / 共 " counter(pages) " 页"'
    return None


def _css_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\A ")
        .replace("\n", "\\A ")
        .replace("\f", "\\A ")
    )
    return f'"{escaped}"'


def _build_document(title: str, body: str, css: str, *, lang: str = "en") -> str:
    safe_title = escape(title)
    safe_lang = escape(lang, quote=True)
    return (
        "<!doctype html>\n"
        f'<html lang="{safe_lang}">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{safe_title}</title>\n"
        "  <style>\n"
        f"{css}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="document">\n'
        f"{body}\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def merge_css_files(paths: Iterable[str]) -> str:
    return "\n\n".join(load_custom_css(path).strip() for path in paths if path)


_CALLOUT_BLOCKQUOTE_RE = re.compile(r"<blockquote>\n(?P<inner>.*?)</blockquote>", re.DOTALL)
_IMG_SRC_RE = re.compile(r'(<img\b(?=[^>]*\bsrc=")[^>]*?\bsrc=")([^"]*)(")', re.IGNORECASE)
_HTML_TAG_TOKEN_RE = re.compile(r"(<[^>]+>)")
_HTML_TAG_NAME_RE = re.compile(r"</?\s*(?P<tag>[A-Za-z][A-Za-z0-9:-]*)")
_EMOJI_BASE_PATTERN = (
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "]"
)
_EMOJI_TEXT_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF]{2}|"
    r"[0-9#*]\ufe0f?\u20e3|"
    rf"{_EMOJI_BASE_PATTERN}[\ufe0e\ufe0f]?(?:[\U0001F3FB-\U0001F3FF])?"
    rf"(?:\u200d{_EMOJI_BASE_PATTERN}[\ufe0e\ufe0f]?(?:[\U0001F3FB-\U0001F3FF])?)*"
)
_EMOJI_SKIP_TAGS = {"code", "kbd", "pre", "script", "style", "textarea"}
_VOID_HTML_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_CALLOUT_MARKER_RE = re.compile(
    r"^\[!(?P<type>[A-Za-z][A-Za-z0-9_-]*)(?P<fold>[+-])?\](?P<after>.*)$",
    re.DOTALL,
)
_CALLOUT_BREAK_RE = re.compile(r"<br\s*/?>\s*", re.IGNORECASE)
_CALLOUT_TITLES = {
    "abstract": "Abstract",
    "attention": "Attention",
    "bug": "Bug",
    "caution": "Caution",
    "check": "Check",
    "danger": "Danger",
    "done": "Done",
    "error": "Error",
    "example": "Example",
    "fail": "Failure",
    "failure": "Failure",
    "faq": "Question",
    "help": "Question",
    "hint": "Hint",
    "important": "Important",
    "info": "Info",
    "missing": "Missing",
    "note": "Note",
    "question": "Question",
    "quote": "Quote",
    "success": "Success",
    "summary": "Summary",
    "tip": "Tip",
    "todo": "Todo",
    "tldr": "Summary",
    "warning": "Warning",
}
