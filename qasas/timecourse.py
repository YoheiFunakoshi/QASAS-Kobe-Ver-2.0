from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import math
from pathlib import Path

from .engine import analyse
from .loaders import load_database, load_sample
from .models import AnalysisResult, DatabaseData
from .modes import MatchingMode, parse_matching_mode


StatusCallback = Callable[[str], None] | None
TimeCourseProgressCallback = Callable[[int, int, int, int], None] | None


@dataclass(frozen=True, slots=True)
class TimepointSpec:
    """One repertoire file and its user-supplied numeric observation day."""

    day: float
    label: str
    sample_path: Path
    input_format: str = "AUTO"


@dataclass(frozen=True, slots=True)
class TimepointResult:
    spec: TimepointSpec
    analysis: AnalysisResult


@dataclass(frozen=True, slots=True)
class TimeCourseResult:
    series_name: str
    matching_mode: MatchingMode
    database: DatabaseData
    timepoints: tuple[TimepointResult, ...]


def parse_day(value: object) -> float:
    """Parse a signed finite numeric Day value.

    Negative values, zero, positive values, and decimal values are valid.
    Non-numeric, NaN, and infinite values are rejected because they cannot be
    plotted or sorted reproducibly.
    """

    text = str(value).strip()
    if not text:
        raise ValueError("Dayを入力してください。負数・0・正数・小数を使用できます。")
    try:
        day = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Dayは数値で入力してください: {value}") from exc
    if not math.isfinite(day):
        raise ValueError("DayにNaNや無限大は使用できません。")
    return 0.0 if day == 0 else day


def format_day(day: float) -> str:
    """Return an unambiguous compact Day label without changing its value."""

    return f"{day:g}"


def validate_timepoints(specs: Iterable[TimepointSpec]) -> tuple[TimepointSpec, ...]:
    """Validate and numerically sort time points.

    Duplicate days are deliberately rejected.  Ver 2.0 does not silently
    average technical/biological replicates because doing so would change the
    scientific unit of analysis without an explicit aggregation rule.
    """

    validated: list[TimepointSpec] = []
    seen_days: dict[float, TimepointSpec] = {}
    for raw in specs:
        day = parse_day(raw.day)
        path = Path(raw.sample_path)
        if not path.is_file():
            raise ValueError(f"検体ファイルが見つかりません: {path}")
        if day in seen_days:
            previous = seen_days[day]
            raise ValueError(
                f"Day {format_day(day)} が重複しています: "
                f"{previous.sample_path.name} / {path.name}。"
                "Ver 2.0では同一Dayを自動平均しません。"
            )
        label = str(raw.label).strip() or path.stem
        input_format = str(raw.input_format).strip() or "AUTO"
        spec = TimepointSpec(day, label, path, input_format)
        seen_days[day] = spec
        validated.append(spec)
    if len(validated) < 2:
        raise ValueError("経時解析にはDayを設定した検体を2件以上追加してください。")
    return tuple(sorted(validated, key=lambda item: item.day))


def analyse_timecourse(
    specs: Iterable[TimepointSpec],
    database_path: str | Path,
    matching_mode: MatchingMode | str = MatchingMode.KOBE,
    *,
    series_name: str = "",
    status_callback: StatusCallback = None,
    progress_callback: TimeCourseProgressCallback = None,
) -> TimeCourseResult:
    """Analyse every time point independently against one common database."""

    ordered_specs = validate_timepoints(specs)
    mode = parse_matching_mode(matching_mode)
    database_source = Path(database_path)
    if not database_source.is_file():
        raise ValueError(f"抗原結合性データベースが見つかりません: {database_source}")
    if status_callback:
        status_callback("共通の抗原結合性データベースを読み込んでいます…")
    database = load_database(database_source, status_callback, matching_mode=mode)

    timepoints: list[TimepointResult] = []
    total_timepoints = len(ordered_specs)
    for index, spec in enumerate(ordered_specs, start=1):
        if status_callback:
            status_callback(
                f"時点 {index}/{total_timepoints}: Day {format_day(spec.day)} "
                f"({spec.label}) を読み込んでいます…"
            )
        sample = load_sample(
            spec.sample_path,
            spec.input_format,
            status_callback,
            matching_mode=mode,
        )
        if status_callback:
            status_callback(
                f"時点 {index}/{total_timepoints}: Day {format_day(spec.day)} "
                "のCDR3距離を照合しています…"
            )
        result = analyse(
            sample,
            database,
            max_distance=2,
            progress_callback=(
                (lambda done, total, i=index: progress_callback(i, total_timepoints, done, total))
                if progress_callback
                else None
            ),
            matching_mode=mode,
        )
        timepoints.append(TimepointResult(spec, result))

    return TimeCourseResult(
        series_name=str(series_name).strip() or "QASAS time course",
        matching_mode=mode,
        database=database,
        timepoints=tuple(timepoints),
    )
