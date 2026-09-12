from html import unescape
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from importlib import resources

import pytest
from click.testing import CliRunner

from mdtopdf import markdown_to_pdf
from mdtopdf.core import fonts, markdown, obsidian
from mdtopdf.core import doctor as doctor_module
from mdtopdf.core.diagnostics import collect_warnings, warn
from mdtopdf.core.html import convert_markdown_file_to_html
from mdtopdf.core.pdf import convert_markdown_file
from mdtopdf.mdtopdf_cli import cli
import mdtopdf.mdtopdf_cli as commands


LITERAL = '<kbd>key</kbd> [[target]] %%literal%% <!-- comment --> **bold**'


@pytest.mark.parametrize('source', [
    f'    {LITERAL}\n',
    f'```text\n{LITERAL}\n```\n',
    f'> ```text\n> {LITERAL}\n> ```\n',
    f'- Example:\n\n    ```text\n    {LITERAL}\n    ```\n',
    f'- ```text\n  {LITERAL}\n  ```\n',
    f'>     {LITERAL}\n',
    f'- Example:\n\n        {LITERAL}\n',
])
def test_code_blocks_preserve_literal_markdown(source):
    body = markdown.render_markdown_to_html(source).body
    code = re.search(r'<pre[^>]*>(.*?)</pre>', body, re.S).group(1)
    assert LITERAL in unescape(re.sub(r'<[^>]+>', '', code))
    assert '<kbd>' not in code
    assert '<a ' not in code


def test_nested_code_does_not_disable_surrounding_obsidian():
    rendered = markdown.render_markdown_to_html(
        f'[[before]]\n\n> ```\n> {LITERAL}\n> ```\n\n[[after]] %%hidden%%\n'
    )
    assert 'href="before"' in rendered.body
    assert 'href="after"' in rendered.body
    assert 'hidden' not in rendered.body


@pytest.mark.parametrize(('source', 'expected'), [
    ('```\ncode\n```\n>\ncontinued\n', '```\ncode\n```\n>\n> continued\n'),
    ('>\n```\ncode\n```\nplain\n', '>\n```\ncode\n```\nplain\n'),
    ('```\ncode\n```\n- item\n\t\t\t- child\n', '```\ncode\n```\n- item\n  - child\n'),
])
def test_code_protection_preserves_neighboring_block_boundaries(source, expected):
    assert obsidian.preprocess_obsidian_markdown(source) == expected


@pytest.mark.parametrize('source', [
    '```\ncode\n```', '```\r\ncode\r\n```\r\n',
    '> ```\n> code\n> ```\n\n- ```\n  next\n  ```\n',
])
def test_code_protection_round_trip(source):
    from mdtopdf.core.inline import protect_code_blocks, restore_code_blocks

    protected, replacements = protect_code_blocks(source)
    assert restore_code_blocks(protected, replacements) == source


@pytest.mark.parametrize('target', ['charts/logo.png', r'charts\logo.png', 'charts%2Flogo.png'])
def test_resource_subdirectory_is_not_bare_on_posix(monkeypatch, target):
    monkeypatch.setattr(obsidian, 'Path', PurePosixPath)
    assert not obsidian._is_bare_resource_target(target)


def test_resource_directory_does_not_shadow_explicit_path(tmp_path):
    (tmp_path / 'logo.png').write_bytes(b'not used')
    resolver = obsidian.build_resource_resolver(str(tmp_path), tmp_path / 'report.md', tmp_path)
    assert resolver('charts/logo.png') == 'charts/logo.png'


@pytest.mark.parametrize('args', [
    ['--json', 'convert'], ['convert', '--json'],
    ['convert', '--json', '--unknown'], ['--json', 'missing-command'],
    ['html', '--json', '--theme'], ['doctor', '--json', '--unknown'],
])
def test_usage_errors_are_json(args):
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    assert json.loads(result.stdout)['ok'] is False
    assert not result.stderr


def test_doctor_failure_exits_nonzero(monkeypatch):
    monkeypatch.setattr(commands, 'run_doctor', lambda **kwargs: {'ok': False})
    result = CliRunner().invoke(cli, ['doctor', '--json'])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {'ok': False}


def test_missing_font_face_is_not_a_resolved_font(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, 'available_font_names', lambda: set())
    css = '@font-face {font-family: Report; src: url(missing.ttf)} body {font-family: Report}'
    result = fonts.inspect_css_font_usage(css, document_text='中文测试', base_url=str(tmp_path))
    assert result['ok'] is False
    assert not result['stacks'][0]['resolved']
    assert any(w['type'] == 'missing_cjk_font' for w in result['warnings'])


def test_custom_preferred_font_warns_even_with_fallback(monkeypatch):
    monkeypatch.setattr(fonts, 'available_font_names', lambda: {'Arial'})
    css = 'body {font-family: MissingReportFont, Arial, sans-serif}'
    result = fonts.inspect_css_font_usage(css, custom_css=css)
    assert any(w['type'] == 'missing_preferred_font' for w in result['warnings'])


def test_fontconfig_emoji_not_also_reported_missing(monkeypatch):
    monkeypatch.setattr(fonts, 'available_font_names', lambda: set())
    monkeypatch.setattr(fonts, '_fontconfig_emoji_match', lambda: {'ok': True, 'families': ['Noto Emoji']})
    group = fonts.inspect_recommended_font_groups('Linux')['groups']['emoji']
    assert group['preferred_found']
    assert 'Noto Emoji' not in group['missing']


def test_missing_mermaid_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(markdown, 'find_mermaid_backend', lambda: None)
    source = tmp_path / 'report.md'
    source.write_text('```mermaid\ngraph TD; A-->B\n```', encoding='utf-8')
    result = convert_markdown_file_to_html(source)
    assert any(w['type'] == 'mermaid_unavailable' for w in result['warnings'])


def test_math_fallback_is_reported(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError('KaTeX unavailable')
    monkeypatch.setattr(markdown, 'render_katex_to_html', fail)
    rendered = markdown.render_markdown_to_html('$x^2$')
    assert any(w['type'] == 'math_fallback' for w in rendered.warnings)


def test_missing_image_is_reported_and_strict_preserves_existing_output(tmp_path):
    source = tmp_path / 'report.md'
    source.write_text('![missing](missing.png)', encoding='utf-8')
    output = tmp_path / 'report.pdf'
    result = convert_markdown_file(source, output_path=output)
    assert any(w['type'] == 'resource_load_failed' for w in result['warnings'])
    original = output.read_bytes()
    with pytest.raises(RuntimeError) as exc:
        convert_markdown_file(source, output_path=output, overwrite=True, strict=True)
    assert exc.value.warnings
    assert output.read_bytes() == original


def test_text_pdf_api_reports_missing_resources(tmp_path):
    result = markdown_to_pdf('![missing](missing.png)', tmp_path / 'api.pdf', base_url=tmp_path)
    assert any(w['type'] == 'resource_load_failed' for w in result['warnings'])


def test_same_path_overwrite_still_supported(tmp_path):
    source = tmp_path / 'report.md'
    source.write_text('# Original', encoding='utf-8')
    with pytest.raises(FileExistsError):
        convert_markdown_file(source, output_path=source)
    result = convert_markdown_file(source, output_path=source, overwrite=True)
    assert result['ok']
    assert source.read_bytes().startswith(b'%PDF-')


@pytest.mark.skipif(os.name != 'posix', reason='POSIX file mode contract')
@pytest.mark.parametrize('existing', [False, True])
def test_atomic_pdf_output_preserves_file_mode(tmp_path, existing):
    output = tmp_path / 'report.pdf'
    reference = tmp_path / 'reference'
    reference.write_bytes(b'normal file permissions')
    expected = stat.S_IMODE(reference.stat().st_mode)
    if existing:
        output.write_bytes(b'old')
        output.chmod(0o640)
        expected = 0o640

    markdown_to_pdf('# Report', output, overwrite=existing)

    assert stat.S_IMODE(output.stat().st_mode) == expected
    assert not list(tmp_path.glob('.mdtopdf-*'))


def test_failed_pdf_write_preserves_output_and_cleans_temporary_files(monkeypatch, tmp_path):
    from weasyprint import HTML

    def fail(self, target, **kwargs):
        Path(target).write_bytes(b'incomplete')
        raise RuntimeError('Render failed')

    monkeypatch.setattr(HTML, 'write_pdf', fail)
    output = tmp_path / 'report.pdf'
    output.write_bytes(b'previous valid output')
    with pytest.raises(RuntimeError, match='Render failed'):
        markdown_to_pdf('# Report', output, overwrite=True)
    assert output.read_bytes() == b'previous valid output'
    assert not list(tmp_path.glob('.mdtopdf-*'))


def test_footer_uses_document_language():
    en = markdown.render_markdown_to_html('# English report\n\nA short report.')
    zh = markdown.render_markdown_to_html('# 中文报告\n\n这是一份中文报告。')
    assert '"Page " counter(page) " of " counter(pages)' in en.css
    assert '"第 " counter(page)' in zh.css


@pytest.mark.parametrize('emoji', ['\U0001f1e8\U0001f1f3', '1\ufe0f\u20e3', '\U0001f469\U0001f3fd\u200d\U0001f4bb'])
def test_emoji_sequences_stay_in_one_span(emoji):
    body = markdown.render_markdown_to_html(emoji).body
    assert body.count('class="mdtopdf-emoji"') == 1
    assert f'>{emoji}</span>' in body


def test_invalid_font_file_does_not_pass_inspection(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, 'available_font_names', lambda: set())
    (tmp_path / 'broken.ttf').write_bytes(b'not a font')
    css = '@font-face {font-family: Broken; src: url(broken.ttf)} body {font-family: Broken}'
    result = fonts.inspect_css_font_usage(css, base_url=str(tmp_path))
    assert not result['ok']
    assert result['warnings'][0]['type'] == 'font_face_unavailable'


def test_real_latin_font_face_does_not_claim_cjk_coverage(monkeypatch, tmp_path):
    monkeypatch.setattr(fonts, 'available_font_names', lambda: set())
    font = resources.files('mdtopdf').joinpath('vendor/katex/dist/fonts/KaTeX_Main-Regular.woff2')
    (tmp_path / 'latin.woff2').write_bytes(font.read_bytes())
    css = '@font-face {font-family: Latin; src: url(latin.woff2)} body {font-family: Latin}'
    result = fonts.inspect_css_font_usage(css, base_url=str(tmp_path), document_text='中文报告')
    assert result['stacks'][0]['resolved'][0]['source'] == 'font-face'
    assert any(w['type'] == 'missing_cjk_font' for w in result['warnings'])


def test_doctor_render_check_failure_changes_ok(monkeypatch):
    monkeypatch.setattr(doctor_module, '_check_python_package', lambda name: {'ok': True})
    monkeypatch.setattr(doctor_module, '_run_render_checks', lambda mermaid: {'pdf': {'ok': False}})
    result = doctor_module.run_doctor(render_check=True)
    assert not result['ok']
    assert result['render_checks']['pdf']['ok'] is False


def test_doctor_fast_mode_does_not_render(monkeypatch):
    def unexpected(*args):
        pytest.fail('Fast doctor must not start rendering.')
    monkeypatch.setattr(doctor_module, '_run_render_checks', unexpected)
    assert 'render_checks' not in doctor_module.run_doctor()


def test_strict_html_does_not_replace_source_on_warning(monkeypatch, tmp_path):
    monkeypatch.setattr(markdown, 'find_mermaid_backend', lambda: None)
    source = tmp_path / 'same.md'
    content = '```mermaid\ngraph TD; A-->B\n```'
    source.write_text(content, encoding='utf-8')
    result = CliRunner().invoke(cli, ['html', str(source), '-o', str(source), '--overwrite', '--strict', '--json'])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data['error_type'] == 'RenderWarningError'
    assert data['warnings']
    assert source.read_text(encoding='utf-8') == content


@pytest.mark.parametrize('args', [
    ['convert', '--', '--json'],
    ['convert', '--title', '--json'],
])
def test_json_as_data_does_not_select_json_output(args):
    result = CliRunner().invoke(cli, args)
    assert not result.stdout.lstrip().startswith('{')
    assert result.exit_code != 0


def test_diagnostic_collection_does_not_leak_between_renders():
    with collect_warnings() as outer:
        warn('outer', 'Outer')
        with collect_warnings() as inner:
            warn('inner', 'Inner')
        warn('outer', 'Outer')
    assert [item['type'] for item in outer] == ['outer']
    assert [item['type'] for item in inner] == ['inner']
    assert markdown.render_markdown_to_html('# Clean').warnings == []
