"""medrack.benchmarks — single reusable benchmark engine for MedRack.

Public API:
    medrack.benchmarks.engine      — pure data layer (run_benchmark, BenchmarkRun, BenchmarkRecord)
    medrack.benchmarks.report      — JSON + Markdown writers (write_json_report, write_markdown_report)
    medrack.benchmarks.run         — CLI entry point (python -m medrack.benchmarks.run)
    medrack benchmark              — argparse subcommand (medrack.cli.cmd_benchmark)

The current canonical suite is ``medrack.tests.regression_datasets.v1.json``
(20 questions, 12 PSM + 8 FMT). Future suites (v2.json, v3.json) extend
but v1 never changes (per the directive v1.0).
"""
from medrack.benchmarks.engine import (
    BenchmarkRecord,
    BenchmarkRun,
    run_benchmark,
)
from medrack.benchmarks.report import (
    write_json_report,
    write_markdown_report,
)


__all__ = [
    "BenchmarkRecord",
    "BenchmarkRun",
    "run_benchmark",
    "write_json_report",
    "write_markdown_report",
]
