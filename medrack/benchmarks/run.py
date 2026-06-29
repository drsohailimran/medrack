"""medrack.benchmarks.run — CLI entry point for the benchmark suite.

Invoked via either:

  $ medrack benchmark [options]              # thin wrapper in medrack.cli
  $ python -m medrack.benchmarks.run [opts]  # this module

Both call the same underlying engine. The CLI is intentionally thin:
argument parsing, default loading, and report writing. The heavy
lifting (the actual benchmark) lives in medrack.benchmarks.engine.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from medrack import config
from medrack.answer.llm import LLMClient, MockLLMClient
from medrack.benchmarks.engine import run_benchmark
from medrack.benchmarks.report import write_json_report, write_markdown_report
from medrack.tests.regression_datasets import (
    load_regression_dataset, list_available_versions, ACTIVE_VERSION,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="medrack benchmark",
        description="Run the benchmark suite on the regression dataset.",
    )
    p.add_argument(
        "--suite", type=int, default=ACTIVE_VERSION,
        help=f"Dataset version to use (default: {ACTIVE_VERSION}; available: {list_available_versions()})",
    )
    p.add_argument(
        "--subject", choices=["psm", "fmt"], default=None,
        help="Run only questions for this subject",
    )
    p.add_argument(
        "--module", default=None,
        help="Run only questions for this module (e.g. psm-module-1, singhi-fmt)",
    )
    p.add_argument(
        "--qid", default=None,
        help="Run only this single qid",
    )
    p.add_argument(
        "--llm", choices=["mock", "real"], default="mock",
        help="LLM client: 'mock' (offline, no API) or 'real' (uses OPENCODE_ZEN_API_KEY)",
    )
    p.add_argument(
        "--no-warm-path", action="store_true",
        help="Skip the warm-path pass (cold path only)",
    )
    p.add_argument(
        "--output-dir", type=Path, default=None,
        help="Directory to write the JSON + Markdown reports "
             "(default: ~/.hermes/medrack/benchmarks/runs/<timestamp>/)",
    )
    p.add_argument(
        "--keep-pdfs", action="store_true",
        help="Keep the warm-path PDFs (otherwise they're written to a temp file and discarded)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Load the suite
    suite_data = load_regression_dataset(args.suite)
    suite = suite_data["questions"]
    module_sources = suite_data["_module_sources"]

    # Build the LLM client
    if args.llm == "mock":
        llm_client = MockLLMClient()
    else:
        llm_client = LLMClient()

    # Resolve medrack source root (where the modules/ directory lives).
    # The dataset's _module_sources paths are relative to the source root,
    # not to $MEDRACK_HOME (which is the runtime data dir).
    medrack_root = Path(__file__).resolve().parents[2]  # medrack/benchmarks/run.py -> medrack/

    # Output dir
    if args.output_dir is None:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = medrack_root / "benchmarks" / "runs" / ts
    else:
        output_dir = args.output_dir

    # Run
    print(f"Running benchmark suite v{args.suite} ({len(suite)} questions)...", file=sys.stderr)
    run = run_benchmark(
        suite=suite,
        module_sources=module_sources,
        llm_client=llm_client,
        medrack_root=medrack_root,
        subject_filter=args.subject,
        module_filter=args.module,
        qid_filter=args.qid,
        run_warm=not args.no_warm_path,
        pdf_dir=output_dir / "pdfs" if args.keep_pdfs else None,
        suite_name=f"v{args.suite}",
        suite_path=f"medrack.tests.regression_datasets.v{args.suite}.json",
    )

    # Write reports
    json_path = write_json_report(run, output_dir)
    md_path = write_markdown_report(run, output_dir)

    # Print summary to stdout
    print(f"\nBenchmark complete: {run.n_success}/{len(run.records)} records successful", file=sys.stderr)
    print(f"  cache_hit_rate:  {run.cache_hit_rate:.1%}", file=sys.stderr)
    print(f"  total_tokens:    {run.total_tokens} (cold path)", file=sys.stderr)
    print(f"  avg PDF time:    {run.avg_pdf_generation_seconds:.2f}s", file=sys.stderr)
    print(f"  avg total time:  {run.avg_total_latency_seconds:.2f}s per record", file=sys.stderr)
    print(f"  JSON report:     {json_path}", file=sys.stderr)
    print(f"  Markdown report: {md_path}", file=sys.stderr)

    # On success, also print the summary as JSON to stdout (for scripting)
    summary = {
        "n_questions": run.n_questions,
        "n_success": run.n_success,
        "n_failure": run.n_failure,
        "cache_hit_rate": run.cache_hit_rate,
        "total_tokens": run.total_tokens,
        "avg_total_tokens": run.avg_total_tokens,
        "avg_total_latency_seconds": run.avg_total_latency_seconds,
        "avg_pdf_generation_seconds": run.avg_pdf_generation_seconds,
        "json_report": str(json_path),
        "markdown_report": str(md_path),
    }
    print(json.dumps(summary, indent=2))
    return 0 if run.n_failure == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
