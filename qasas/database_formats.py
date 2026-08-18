from __future__ import annotations

from dataclasses import dataclass


COV_ABDAB_DATABASE_FORMAT = "CoV-AbDab"
GENERIC_DATABASE_FORMAT = "汎用データベース"


@dataclass(frozen=True, slots=True)
class DatabaseFormatChoice:
    value: str
    label: str
    enabled: bool


DATABASE_FORMAT_CHOICES = (
    DatabaseFormatChoice(COV_ABDAB_DATABASE_FORMAT, "CoV-AbDab（CSV）", True),
    DatabaseFormatChoice(GENERIC_DATABASE_FORMAT, "汎用データベース（今後対応）", False),
)

_ACTIVE_VALUES = {choice.value for choice in DATABASE_FORMAT_CHOICES if choice.enabled}
_LABELS = {choice.value: choice.label for choice in DATABASE_FORMAT_CHOICES}


def database_format_label(value: str) -> str:
    return _LABELS.get(value, value)


def resolve_database_format(selected: str) -> str:
    requested = selected.strip()
    if requested in _ACTIVE_VALUES:
        return requested
    if requested == GENERIC_DATABASE_FORMAT:
        raise ValueError(
            "汎用データベースは今後対応予定です。現在はCoV-AbDabを選択してください。"
        )
    raise ValueError(f"未対応のデータベース形式です: {selected}")
