from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .modes import MatchingMode, mode_specification


@dataclass(frozen=True, slots=True)
class SampleClone:
    """One unique, normalized repertoire clone."""

    v_genes: tuple[str, ...]
    j_genes: tuple[str, ...]
    cdr3_aa: str
    reads: int
    frequency_percent: float
    raw_v_gene: str = ""
    raw_j_gene: str = ""
    raw_cdr3_aa: str = ""
    source_rows: int = 1

    @property
    def display_v_gene(self) -> str:
        return " / ".join(self.v_genes)

    @property
    def display_j_gene(self) -> str:
        return " / ".join(self.j_genes)


@dataclass(frozen=True, slots=True)
class SampleData:
    source_path: Path
    input_format: str
    sample_id: str
    clones: tuple[SampleClone, ...]
    total_reads: int
    source_rows: int
    accepted_rows: int
    skipped_rows: int
    metadata: Mapping[str, str] = field(default_factory=dict)
    matching_mode: MatchingMode = MatchingMode.KOBE

    @property
    def listed_reads(self) -> int:
        """Reads represented by clone rows actually present in the input file."""

        return sum(clone.reads for clone in self.clones)


@dataclass(frozen=True, slots=True)
class DatabaseEntry:
    """One deduplicated antigen-database V/J/CDR3 key."""

    v_gene: str
    j_gene: str
    cdr3_aa: str
    annotations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_rows: int = 1

    def annotation_text(self, column: str) -> str:
        return " | ".join(self.annotations.get(column, ()))


@dataclass(frozen=True, slots=True)
class DatabaseData:
    source_path: Path
    entries: tuple[DatabaseEntry, ...]
    source_rows: int
    usable_rows: int
    skipped_rows: int
    annotation_columns: tuple[str, ...]
    v_column: str
    j_column: str
    cdr3_column: str
    matching_mode: MatchingMode = MatchingMode.KOBE
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MatchRecord:
    clone: SampleClone
    distance: int
    database_entries: tuple[DatabaseEntry, ...]
    entry_distances: tuple[int, ...] = ()

    def combined_annotation(self, column: str) -> str:
        values: list[str] = []
        seen: set[str] = set()
        for entry in self.database_entries:
            for value in entry.annotations.get(column, ()):
                if value not in seen:
                    seen.add(value)
                    values.append(value)
        return " | ".join(values)


@dataclass(frozen=True, slots=True)
class LevelSummary:
    label: str
    unique_clones: int
    total_reads: int
    frequency_percent: float


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    sample: SampleData
    database: DatabaseData
    matches: tuple[MatchRecord, ...]
    exact_summaries: tuple[LevelSummary, ...]
    cumulative_summaries: tuple[LevelSummary, ...]

    @property
    def matched_clone_count(self) -> int:
        return len(self.matches)

    @property
    def matching_mode(self) -> MatchingMode:
        return self.sample.matching_mode

    @property
    def matching_mode_label(self) -> str:
        return mode_specification(self.matching_mode).label
