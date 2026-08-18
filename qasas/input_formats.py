from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .loaders import detect_sample_format


AUTO_INPUT_FORMAT = "自動判定"
RG_INPUT_FORMAT = "RG様式"
CPM_INPUT_FORMAT = "CPM様式"
GENERIC_INPUT_FORMAT = "汎用形式"


@dataclass(frozen=True, slots=True)
class InputFormatChoice:
    value: str
    label: str
    enabled: bool


INPUT_FORMAT_CHOICES = (
    InputFormatChoice(RG_INPUT_FORMAT, "RG社形式（Excel）", True),
    InputFormatChoice(CPM_INPUT_FORMAT, "CPM社形式（CSV/TSV）", True),
    InputFormatChoice(GENERIC_INPUT_FORMAT, "汎用形式（今後対応）", False),
)

_ACTIVE_VALUES = {choice.value for choice in INPUT_FORMAT_CHOICES if choice.enabled}
_LABELS = {choice.value: choice.label for choice in INPUT_FORMAT_CHOICES}


def input_format_label(value: str) -> str:
    return _LABELS.get(value, value)


def detected_input_format(path: str | Path) -> str:
    detected = detect_sample_format(path)
    if detected == "RG":
        return RG_INPUT_FORMAT
    if detected == "CPM":
        return CPM_INPUT_FORMAT
    raise ValueError(f"未対応の入力形式です: {detected}")


def resolve_input_format(selected: str, path: str | Path) -> str:
    requested = selected.strip()
    if requested in _ACTIVE_VALUES:
        return requested
    if requested == GENERIC_INPUT_FORMAT:
        raise ValueError(
            "汎用形式は今後対応予定です。現在はRG社形式またはCPM社形式を選択してください。"
        )
    if requested in {"", AUTO_INPUT_FORMAT, "AUTO"}:
        return detected_input_format(path)
    raise ValueError(f"未対応の入力形式です: {selected}")
