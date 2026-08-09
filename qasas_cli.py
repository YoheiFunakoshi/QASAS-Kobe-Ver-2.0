from __future__ import annotations

import argparse
from pathlib import Path

from qasas.engine import analyse
from qasas.export import export_result_xlsx
from qasas.loaders import load_database, load_sample
from qasas.modes import MatchingMode, mode_specification


def main() -> int:
    parser = argparse.ArgumentParser(description="QASAS Kobe Ver 2.0 single-sample command-line tool")
    parser.add_argument("--sample", required=True, help="CPM CSV or RG XLSX repertoire file")
    parser.add_argument("--database", required=True, help="Antigen-specific antibody database CSV")
    parser.add_argument("--format", default="AUTO", choices=("AUTO", "CPM", "RG"))
    parser.add_argument(
        "--mode",
        default=MatchingMode.KOBE.value,
        choices=tuple(mode.value for mode in MatchingMode),
        help="Matching strategy: legacy, kobe, or cdr3-only",
    )
    parser.add_argument("--output", help="Optional result XLSX path")
    args = parser.parse_args()

    sample = load_sample(args.sample, args.format, print, matching_mode=args.mode)
    database = load_database(args.database, print, matching_mode=args.mode)
    result = analyse(
        sample,
        database,
        progress_callback=lambda done, total: print(f"照合中: {done:,}/{total:,}"),
        matching_mode=args.mode,
    )
    print(f"Matching mode: {mode_specification(result.matching_mode).label} [{result.matching_mode.value}]")
    print(f"Sample: {sample.sample_id} ({sample.input_format})")
    print(
        f"Unique clones: {len(sample.clones):,}; listed reads: {sample.listed_reads:,}; "
        f"frequency denominator: {sample.total_reads:,}"
    )
    print(f"Database unique keys: {len(database.entries):,}")
    for item in result.exact_summaries:
        print(
            f"{item.label}: clones={item.unique_clones:,}, reads={item.total_reads:,}, "
            f"frequency={item.frequency_percent:.9f}%"
        )
    if args.output:
        path = export_result_xlsx(result, Path(args.output))
        print(f"Saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
