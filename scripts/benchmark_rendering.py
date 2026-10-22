"""Measure local PDF conversion phases without changing the public renderer.

Run with the Python environment to measure. For an installed-wheel comparison,
run from outside the checkout, for example::

    cd /tmp
    /path/to/wheel-env/bin/python /project/mdtopdf/scripts/benchmark_rendering.py

Every conversion starts its own browser. Warmups prime filesystem/font caches;
they do not reuse a browser. Fixtures have no external resource references.
"""

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from importlib import metadata
import json
from pathlib import Path
import platform
from statistics import median
import sys
import tempfile
from time import perf_counter

import mdtopdf
from mdtopdf.core import browser
from playwright.async_api import BrowserType, Page


PHASES = (
    "browser_startup_ms",
    "document_load_ms",
    "asset_load_ms",
    "render_evaluate_ms",
    "pdf_print_ms",
)


def _nonnegative(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a nonnegative integer") from None
    if number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return number


def _positive(value):
    number = _nonnegative(value)
    if number == 0:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _diagram_counts(value):
    try:
        counts = [_nonnegative(item.strip()) for item in value.split(",")]
    except argparse.ArgumentTypeError:
        raise argparse.ArgumentTypeError("use comma-separated nonnegative integers, e.g. 0,1,20") from None
    return list(dict.fromkeys(counts))


@contextmanager
def _timed_phases(timings, browser_details):
    """Temporarily time disjoint await boundaries; restore methods on failure too."""
    active = ContextVar("mdtopdf_benchmark_phase", default=None)
    patched = []

    def wrap(owner, method, phase):
        original = getattr(owner, method)

        @wraps(original)
        async def measured(*args, **kwargs):
            if active.get() is not None:
                return await original(*args, **kwargs)
            token = active.set(phase)
            start = perf_counter()
            try:
                result = await original(*args, **kwargs)
                if phase == "browser_startup_ms":
                    browser_details.update(
                        version=result.version,
                        executable=kwargs.get("executable_path"),
                        channel=kwargs.get("channel"),
                    )
                return result
            finally:
                timings[phase] += (perf_counter() - start) * 1000
                active.reset(token)

        patched.append((owner, method, original))
        setattr(owner, method, measured)

    try:
        wrap(BrowserType, "launch", "browser_startup_ms")
        wrap(Page, "goto", "document_load_ms")
        wrap(browser, "_load_script", "asset_load_ms")
        wrap(Page, "evaluate", "render_evaluate_ms")
        wrap(Page, "pdf", "pdf_print_ms")
        yield
    finally:
        for owner, method, original in reversed(patched):
            setattr(owner, method, original)


def _document(count):
    parts = [
        "# Rendering benchmark 2026\n\n"
        "A local report with mixed labels: Markdown, 中文, 0123456789, IT-001.\n\n"
        "| Stage | Result |\n| --- | --- |\n| Input | 42 |\n| Output | PDF |\n"
    ]
    for index in range(count):
        parts.append(
            f"## Diagram {index + 1}\n\n"
            "```mermaid\nflowchart TD\n"
            " A[输入 2026] --> B[Review IT-001]\n"
            " B --> C[PDF ready]\n```\n"
        )
    return "\n".join(parts)


def _sample(source, output, browser_details):
    timings = dict.fromkeys(PHASES, 0.0)
    start = perf_counter()
    with _timed_phases(timings, browser_details):
        result = mdtopdf.markdown_to_pdf(source, output, overwrite=True)
    timings["total_ms"] = (perf_counter() - start) * 1000
    timings["other_ms"] = timings["total_ms"] - sum(timings[phase] for phase in PHASES)
    if not result["ok"] or not output.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("Benchmark conversion did not produce a valid PDF file")
    return {
        "timings_ms": {key: round(value, 3) for key, value in timings.items()},
        "pdf_bytes": result["file_size"],
        "warning_types": sorted({warning["type"] for warning in result["warnings"]}),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeat", type=_positive, default=3, help="measured conversions per scenario (default: 3)")
    parser.add_argument("--diagrams", type=_diagram_counts, default=[0, 1, 20],
                        help="comma-separated diagram counts (default: 0,1,20)")
    parser.add_argument("--warmup", type=_nonnegative, default=1,
                        help="discarded conversions per scenario (default: 1)")
    args = parser.parse_args(argv)
    browser_details = {}
    scenarios = []
    with tempfile.TemporaryDirectory(prefix="mdtopdf-benchmark-") as directory:
        output = Path(directory) / "report.pdf"
        for count in args.diagrams:
            source = _document(count)
            for _ in range(args.warmup):
                _sample(source, output, browser_details)
            samples = [_sample(source, output, browser_details) for _ in range(args.repeat)]
            scenarios.append({
                "diagrams": count,
                "median_ms": {
                    phase: round(median(sample["timings_ms"][phase] for sample in samples), 3)
                    for phase in (*PHASES, "other_ms", "total_ms")
                },
                "samples": samples,
            })
    print(json.dumps({
        "package_version": metadata.version("agent-markdown-pdf"),
        "package_path": str(Path(mdtopdf.__file__).resolve()),
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "browser": browser_details,
        "repeat": args.repeat,
        "warmup_per_scenario": args.warmup,
        "timing_notes": [
            "Disjoint wall-clock phases; medians across phases need not sum to the median total.",
            "Browser startup measures launch only; Playwright startup, teardown and Python work are in other_ms.",
            "Asset loading measures bundled script loading, including its internal evaluate calls.",
            "Render evaluation includes layout, diagrams, formulas and awaiting fonts/images, excluding asset loading.",
            "Each conversion launches a fresh browser; warmups prime filesystem/font caches only.",
        ],
        "scenarios": scenarios,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
