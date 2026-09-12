from __future__ import annotations

import json as json_module
import sys
from pathlib import Path
from typing import Any

import click

from mdtopdf import __version__
from mdtopdf.api import markdown_to_pdf
from mdtopdf.core.doctor import format_doctor_text, run_doctor
from mdtopdf.core.html import convert_markdown_file_to_html
from mdtopdf.core.markdown import DEFAULT_THEME, available_themes, load_custom_css
from mdtopdf.core.pdf import convert_markdown_file


def _emit_json(data: dict[str, Any]) -> None:
    click.echo(json_module.dumps(data, ensure_ascii=False, indent=2))


def _error_result(exc: Exception) -> dict[str, Any]:
    result = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
    if hasattr(exc, "warnings"):
        result["warnings"] = exc.warnings
    for field in ("error_code", "hint"):
        if getattr(exc, field, None):
            result[field] = getattr(exc, field)
    return result


class JsonGroup(click.Group):
    def main(self, args=None, prog_name=None, complete_var=None, standalone_mode=True, **extra):
        args = list(sys.argv[1:] if args is None else args)
        try:
            result = super().main(
                args, prog_name=prog_name, complete_var=complete_var, standalone_mode=False, **extra,
            )
        except click.ClickException as exc:
            if not standalone_mode:
                raise
            if self._requests_json(args):
                _emit_json(_error_result(exc))
            else:
                exc.show()
            raise SystemExit(exc.exit_code) from exc
        except click.Abort as exc:
            if not standalone_mode:
                raise
            if self._requests_json(args):
                _emit_json(_error_result(exc))
            else:
                click.echo("Aborted!", err=True)
            raise SystemExit(1) from exc
        if standalone_mode:
            raise SystemExit(result if isinstance(result, int) else 0)
        return result

    def _requests_json(self, args):
        value_options = set()

        def visit(command):
            for param in command.params:
                if isinstance(param, click.Option) and not param.is_flag:
                    value_options.update(param.opts)
            if isinstance(command, click.Group):
                for child in command.commands.values():
                    visit(child)

        visit(self)
        skip_value = False
        for arg in args:
            if skip_value:
                skip_value = False
                continue
            if arg == "--":
                break
            if arg == "--json":
                return True
            skip_value = arg in value_options
        return False


def _json_enabled(ctx: click.Context, local_json: bool = False) -> bool:
    obj = ctx.find_root().obj or {}
    return bool(obj.get("json") or local_json)


def _emit_warnings(data: dict[str, Any]) -> None:
    for warning in data.get("warnings", []):
        message = warning.get("message", "Warning")
        detail = warning.get("declaration") or ", ".join(warning.get("families", []))
        suffix = f" ({detail})" if detail else ""
        click.secho(f"Warning: {message}{suffix}", fg="yellow", err=True)


def _read_stdin_markdown() -> str:
    stream = sys.stdin
    if stream.isatty():
        raise ValueError("Pipe UTF-8 Markdown to stdin or provide an input file.")
    try:
        data = getattr(stream, "buffer", stream).read()
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data.removeprefix("\ufeff")
    except UnicodeDecodeError as exc:
        raise ValueError("Standard input must contain UTF-8 Markdown.") from exc
    if not text.strip():
        raise ValueError("Standard input contains no Markdown.")
    return text


@click.group(cls=JsonGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="mdtopdf")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> None:
    """Convert Markdown files to themed PDFs with markdown-it-py and Chromium."""

    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


@cli.command()
@click.argument("input_md", type=click.Path(dir_okay=False))
@click.option("-o", "--output", "output_pdf", type=click.Path(dir_okay=False, path_type=Path), help="Output PDF path.")
@click.option("--theme", default=DEFAULT_THEME, show_default=True, help="Built-in theme name.")
@click.option("--css", "custom_css", type=click.Path(dir_okay=False, path_type=Path), help="Append custom CSS after the theme.")
@click.option("--title", help="Document title. Defaults to the input file stem.")
@click.option("--header", "page_header", help="Page header text. Defaults to the input file stem.")
@click.option("--footer", "page_footer", help="Page footer text before page numbers.")
@click.option("--no-header", is_flag=True, help="Disable the page header.")
@click.option("--no-footer", is_flag=True, help="Disable the page footer.")
@click.option("--no-page-numbers", is_flag=True, help="Disable page numbers in the footer.")
@click.option("--base-url", help="Base path or URL for relative images and links.")
@click.option(
    "--resource-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for bare image names such as ![[image.png]] or ![](image.png).",
)
@click.option("--overwrite", is_flag=True, help="Replace an existing output PDF.")
@click.option("--strict", is_flag=True, help="Fail on rendering warnings without replacing the output.")
@click.option("--unsafe-html", is_flag=True, help="Allow raw HTML in trusted Markdown input.")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def convert(
    ctx: click.Context,
    input_md: str,
    output_pdf: Path | None,
    theme: str,
    custom_css: Path | None,
    title: str | None,
    page_header: str | None,
    page_footer: str | None,
    no_header: bool,
    no_footer: bool,
    no_page_numbers: bool,
    base_url: str | None,
    resource_dir: Path | None,
    overwrite: bool,
    strict: bool,
    unsafe_html: bool,
    json_output: bool,
) -> None:
    """Convert INPUT.md to PDF. Use - to read UTF-8 Markdown from stdin."""

    if input_md == "-" and (output_pdf is None or output_pdf == Path("-")):
        raise click.UsageError("Standard input requires an output file: -o OUTPUT.pdf (not '-').")
    try:
        options = dict(
            theme=theme,
            title=title,
            base_url=base_url,
            resource_dir=resource_dir,
            overwrite=overwrite,
            strict=strict,
            unsafe_html=unsafe_html,
            page_header=page_header,
            page_footer=page_footer,
            include_page_header=not no_header,
            include_page_footer=not no_footer,
            page_numbers=not no_page_numbers,
        )
        if input_md == "-":
            output = output_pdf.expanduser()
            if output.exists() and not overwrite:
                raise FileExistsError(f"Output PDF already exists: {output}. Use --overwrite to replace it.")
            options["base_url"] = base_url if base_url is not None else str(Path.cwd())
            options["title"] = title or "stdin"
            result = markdown_to_pdf(
                _read_stdin_markdown(), output,
                custom_css=load_custom_css(str(custom_css)) if custom_css else None,
                **options,
            )
            result.update(input="-", source="stdin")
        else:
            result = convert_markdown_file(
                input_md, output_path=output_pdf, custom_css_path=custom_css, **options,
            )
    except Exception as exc:
        if _json_enabled(ctx, json_output):
            _emit_json(_error_result(exc))
            raise click.exceptions.Exit(1) from exc
        raise click.ClickException(str(exc)) from exc

    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(f"Converted PDF: {result['output']} ({result['file_size']} bytes)")
        _emit_warnings(result)


@cli.command("html")
@click.argument("input_md", type=click.Path(dir_okay=False, path_type=Path))
@click.option("-o", "--output", "output_html", type=click.Path(dir_okay=False, path_type=Path), help="Output HTML path.")
@click.option("--theme", default=DEFAULT_THEME, show_default=True, help="Built-in theme name.")
@click.option("--css", "custom_css", type=click.Path(dir_okay=False, path_type=Path), help="Append custom CSS after the theme.")
@click.option("--title", help="Document title. Defaults to the input file stem.")
@click.option("--header", "page_header", help="Page header text. Defaults to the input file stem.")
@click.option("--footer", "page_footer", help="Page footer text before page numbers.")
@click.option("--no-header", is_flag=True, help="Disable the page header.")
@click.option("--no-footer", is_flag=True, help="Disable the page footer.")
@click.option("--no-page-numbers", is_flag=True, help="Disable page numbers in the footer.")
@click.option("--base-url", help="Base path or URL for relative images and links.")
@click.option(
    "--resource-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for bare image names such as ![[image.png]] or ![](image.png).",
)
@click.option("--overwrite", is_flag=True, help="Replace an existing output HTML file.")
@click.option("--strict", is_flag=True, help="Fail on preview diagnostics without replacing the output.")
@click.option("--unsafe-html", is_flag=True, help="Allow raw HTML in trusted Markdown input.")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def html(
    ctx: click.Context,
    input_md: Path,
    output_html: Path | None,
    theme: str,
    custom_css: Path | None,
    title: str | None,
    page_header: str | None,
    page_footer: str | None,
    no_header: bool,
    no_footer: bool,
    no_page_numbers: bool,
    base_url: str | None,
    resource_dir: Path | None,
    overwrite: bool,
    strict: bool,
    unsafe_html: bool,
    json_output: bool,
) -> None:
    """Convert INPUT.md to standalone HTML for fast browser preview."""

    try:
        result = convert_markdown_file_to_html(
            input_md,
            output_path=output_html,
            theme=theme,
            custom_css_path=custom_css,
            title=title,
            base_url=base_url,
            resource_dir=resource_dir,
            overwrite=overwrite,
            strict=strict,
            unsafe_html=unsafe_html,
            page_header=page_header,
            page_footer=page_footer,
            include_page_header=not no_header,
            include_page_footer=not no_footer,
            page_numbers=not no_page_numbers,
        )
    except Exception as exc:
        if _json_enabled(ctx, json_output):
            _emit_json(_error_result(exc))
            raise click.exceptions.Exit(1) from exc
        raise click.ClickException(str(exc)) from exc

    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(f"Converted HTML: {result['output']} ({result['file_size']} bytes)")
        _emit_warnings(result)


@cli.command()
@click.option("--render-check", is_flag=True, help="Render a sample PDF and test Mermaid if installed.")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def doctor(ctx: click.Context, json_output: bool, render_check: bool) -> None:
    """Check Python, Chromium, bundled renderers, and fonts."""

    try:
        result = run_doctor(render_check=render_check)
    except Exception as exc:
        if _json_enabled(ctx, json_output):
            _emit_json(_error_result(exc))
            raise click.exceptions.Exit(1) from exc
        raise click.ClickException(str(exc)) from exc
    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(format_doctor_text(result))
    if not result.get("ok"):
        raise click.exceptions.Exit(1)


@cli.group()
def themes() -> None:
    """Inspect built-in themes."""


@themes.command("list")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def list_themes(ctx: click.Context, json_output: bool) -> None:
    """List available built-in themes."""

    themes_list = available_themes()
    result = {"ok": True, "action": "themes_list", "themes": themes_list}
    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        for theme in themes_list:
            click.echo(theme)


main = cli


if __name__ == "__main__":
    sys.exit(main())
