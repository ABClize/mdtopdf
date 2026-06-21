from __future__ import annotations

import json as json_module
import sys
from pathlib import Path
from typing import Any

import click

from mdtopdf import __version__
from mdtopdf.core.doctor import format_doctor_text, run_doctor
from mdtopdf.core.html import convert_markdown_file_to_html
from mdtopdf.core.markdown import DEFAULT_THEME, available_themes
from mdtopdf.core.pdf import convert_markdown_file


def _emit_json(data: dict[str, Any]) -> None:
    click.echo(json_module.dumps(data, ensure_ascii=False, indent=2))


def _json_enabled(ctx: click.Context, local_json: bool = False) -> bool:
    obj = ctx.find_root().obj or {}
    return bool(obj.get("json") or local_json)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="mdtopdf")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def cli(ctx: click.Context, json_output: bool) -> None:
    """Convert Markdown files to themed PDFs with markdown-it-py and WeasyPrint."""

    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


@cli.command()
@click.argument("input_md", type=click.Path(dir_okay=False, path_type=Path))
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
@click.option("--unsafe-html", is_flag=True, help="Allow raw HTML in trusted Markdown input.")
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def convert(
    ctx: click.Context,
    input_md: Path,
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
    unsafe_html: bool,
    json_output: bool,
) -> None:
    """Convert INPUT.md to PDF."""

    try:
        result = convert_markdown_file(
            input_md,
            output_path=output_pdf,
            theme=theme,
            custom_css_path=custom_css,
            title=title,
            base_url=base_url,
            resource_dir=resource_dir,
            overwrite=overwrite,
            unsafe_html=unsafe_html,
            page_header=page_header,
            page_footer=page_footer,
            include_page_header=not no_header,
            include_page_footer=not no_footer,
            page_numbers=not no_page_numbers,
        )
    except Exception as exc:
        if _json_enabled(ctx, json_output):
            _emit_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
            raise click.exceptions.Exit(1) from exc
        raise click.ClickException(str(exc)) from exc

    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(f"Converted PDF: {result['output']} ({result['file_size']} bytes)")


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
            unsafe_html=unsafe_html,
            page_header=page_header,
            page_footer=page_footer,
            include_page_header=not no_header,
            include_page_footer=not no_footer,
            page_numbers=not no_page_numbers,
        )
    except Exception as exc:
        if _json_enabled(ctx, json_output):
            _emit_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
            raise click.exceptions.Exit(1) from exc
        raise click.ClickException(str(exc)) from exc

    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(f"Converted HTML: {result['output']} ({result['file_size']} bytes)")


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Emit machine-readable JSON output.")
@click.pass_context
def doctor(ctx: click.Context, json_output: bool) -> None:
    """Check Python and native WeasyPrint dependencies."""

    result = run_doctor()
    if _json_enabled(ctx, json_output):
        _emit_json(result)
    else:
        click.echo(format_doctor_text(result))


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
