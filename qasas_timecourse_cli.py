from __future__ import annotations

import argparse
import csv
from pathlib import Path

from qasas.modes import MatchingMode, mode_specification
from qasas.timecourse import TimepointSpec, analyse_timecourse, format_day, parse_day
from qasas.timecourse_export import export_timecourse_xlsx


def load_manifest(path: str | Path) -> tuple[TimepointSpec, ...]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("マニフェストにヘッダーがありません。")
        normalized = {str(name).strip().lower(): name for name in reader.fieldnames}
        required = {"day", "sample"}
        missing = required.difference(normalized)
        if missing:
            raise ValueError(f"マニフェストに必要な列がありません: {', '.join(sorted(missing))}")
        specs: list[TimepointSpec] = []
        for row_number, row in enumerate(reader, start=2):
            sample_text = str(row.get(normalized["sample"], "")).strip()
            day_text = str(row.get(normalized["day"], "")).strip()
            if not sample_text and not day_text:
                continue
            if not sample_text:
                raise ValueError(f"マニフェスト{row_number}行目のSampleが空です。")
            sample_path = Path(sample_text)
            if not sample_path.is_absolute():
                sample_path = source.parent / sample_path
            label_column = normalized.get("label")
            format_column = normalized.get("format")
            label = str(row.get(label_column, "")).strip() if label_column else ""
            input_format = str(row.get(format_column, "AUTO")).strip() if format_column else "AUTO"
            specs.append(
                TimepointSpec(
                    day=parse_day(day_text),
                    label=label or sample_path.stem,
                    sample_path=sample_path,
                    input_format=input_format or "AUTO",
                )
            )
    return tuple(specs)


def main() -> int:
    parser = argparse.ArgumentParser(description="QASAS Kobe Ver 2.0 longitudinal analysis")
    parser.add_argument("--manifest", required=True, help="CSV with Day, Sample, Label, Format columns")
    parser.add_argument("--database", required=True, help="Common antigen-specific antibody database CSV")
    parser.add_argument(
        "--mode",
        default=MatchingMode.KOBE.value,
        choices=tuple(mode.value for mode in MatchingMode),
        help="Matching strategy: legacy, kobe, or cdr3-only",
    )
    parser.add_argument("--series-name", default="QASAS time course")
    parser.add_argument("--output", required=True, help="Result XLSX path")
    args = parser.parse_args()

    specs = load_manifest(args.manifest)
    result = analyse_timecourse(
        specs,
        args.database,
        matching_mode=args.mode,
        series_name=args.series_name,
        status_callback=print,
        progress_callback=lambda point, point_total, done, total: print(
            f"時点 {point}/{point_total}: {done:,}/{total:,} clones"
        ),
    )
    output = export_timecourse_xlsx(result, args.output)
    print(f"Matching mode: {mode_specification(result.matching_mode).label} [{result.matching_mode.value}]")
    for point in result.timepoints:
        cumulative = point.analysis.cumulative_summaries[-1]
        print(
            f"Day {format_day(point.spec.day)} | {point.spec.label} | "
            f"≤LV2 clones={cumulative.unique_clones:,}, reads={cumulative.total_reads:,}, "
            f"frequency={cumulative.frequency_percent:.9f}%"
        )
    print(f"Saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
