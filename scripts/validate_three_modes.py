from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from qasas.engine import analyse  # noqa: E402
from qasas.export import export_result_xlsx  # noqa: E402
from qasas.loaders import load_database, load_sample  # noqa: E402
from qasas.modes import ALGORITHM_VERSION, MatchingMode, mode_specification  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one repertoire/database pair with all three fixed QASAS modes."
    )
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--format", default="AUTO", choices=("AUTO", "CPM", "RG"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="If set, save three workbooks and a machine-readable JSON report.",
    )
    args = parser.parse_args()

    sample_path = args.sample.resolve()
    database_path = args.database.resolve()
    rows: list[dict[str, object]] = []
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    for mode in MatchingMode:
        started = perf_counter()
        sample = load_sample(sample_path, args.format, matching_mode=mode)
        database = load_database(database_path, matching_mode=mode)
        result = analyse(sample, database, matching_mode=mode)
        elapsed_seconds = perf_counter() - started
        exact = {item.label: item for item in result.exact_summaries}
        cumulative = {item.label: item for item in result.cumulative_summaries}
        row: dict[str, object] = {
            "algorithm_version": ALGORITHM_VERSION,
            "mode": mode.value,
            "mode_label": mode_specification(mode).label,
            "sample_id": sample.sample_id,
            "input_format": sample.input_format,
            "sample_unique_clones": len(sample.clones),
            "sample_listed_reads": sample.listed_reads,
            "frequency_denominator": sample.total_reads,
            "database_unique_keys": len(database.entries),
            "elapsed_seconds": round(elapsed_seconds, 3),
        }
        for distance in range(3):
            item = exact[f"LV{distance}"]
            row[f"lv{distance}_clones"] = item.unique_clones
            row[f"lv{distance}_reads"] = item.total_reads
            row[f"lv{distance}_frequency_percent"] = round(item.frequency_percent, 12)
            cumulative_item = cumulative[f"≤LV{distance}"]
            row[f"le_lv{distance}_clones"] = cumulative_item.unique_clones
            row[f"le_lv{distance}_reads"] = cumulative_item.total_reads
            row[f"le_lv{distance}_frequency_percent"] = round(
                cumulative_item.frequency_percent, 12
            )
        rows.append(row)

        if args.output_dir:
            output_path = args.output_dir / f"{sample.sample_id}_{mode.value}.xlsx"
            export_result_xlsx(result, output_path)

        print(
            "\t".join(
                (
                    mode.value,
                    f"clones={len(sample.clones)}",
                    f"db_keys={len(database.entries)}",
                    f"LV0={exact['LV0'].unique_clones}/{exact['LV0'].total_reads}",
                    f"LV1={exact['LV1'].unique_clones}/{exact['LV1'].total_reads}",
                    f"LV2={exact['LV2'].unique_clones}/{exact['LV2'].total_reads}",
                    f"seconds={elapsed_seconds:.3f}",
                )
            )
        )

    if args.output_dir:
        report = {
            "algorithm_version": ALGORITHM_VERSION,
            "sample": str(sample_path),
            "sample_sha256": _sha256(sample_path),
            "database": str(database_path),
            "database_sha256": _sha256(database_path),
            "results": rows,
        }
        report_path = args.output_dir / "validation_summary.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
