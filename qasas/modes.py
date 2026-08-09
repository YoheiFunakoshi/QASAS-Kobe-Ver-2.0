from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


ALGORITHM_VERSION = "QASAS-Kobe-three-mode-1.0"


class MatchingMode(str, Enum):
    """Matching strategies exposed by the GUI and command line."""

    LEGACY = "legacy"
    KOBE = "kobe"
    CDR3_ONLY = "cdr3-only"


@dataclass(frozen=True, slots=True)
class ModeSpecification:
    mode: MatchingMode
    label: str
    short_label: str
    description: str
    sample_clone_key: str
    sample_gene_handling: str
    database_key: str
    candidate_rule: str
    cdr3_handling: str
    candidate_retention: str
    frequency_rule: str


MODE_SPECIFICATIONS: dict[MatchingMode, ModeSpecification] = {
    MatchingMode.LEGACY: ModeSpecification(
        mode=MatchingMode.LEGACY,
        label="旧QASAS方式（V/J文字列完全一致）",
        short_label="旧QASAS",
        description="V/J候補を分割・アレル除去せず、旧QASASの文字列完全一致を再現します。",
        sample_clone_key="入力に記載されたIGHV文字列 × IGHJ文字列 × CDR3文字列",
        sample_gene_handling="前後空白以外は変更せず、候補分割・大文字化・アレル除去を行わない",
        database_key="旧QASAS互換IGHV × IGHJ × CDR3（CoV-AbDabでは末尾の ' (Human)' のみ除去）",
        candidate_rule="検体IGHVとIGHJがDBキーに文字列完全一致した配列だけを比較",
        cdr3_handling="検体CDR3は原表記、DB CDR3には旧実装どおり先頭C・末尾Wを付加",
        candidate_retention="距離0～2のDB候補をすべて保持し、検体クローンの区分は最小距離",
        frequency_rule="RGでは旧QASASどおり、列挙されたin-frameクローンのRead合計を分母にする",
    ),
    MatchingMode.KOBE: ModeSpecification(
        mode=MatchingMode.KOBE,
        label="Kobe Ver 1.0方式（V/J候補一致）",
        short_label="Kobe Ver 1.0",
        description="V/Jの複数候補を分け、いずれかのV/J組合せが一致すれば比較します。",
        sample_clone_key="正規化V候補集合 × 正規化J候補集合 × 正規化CDR3",
        sample_gene_handling="候補分割、大文字化、(Human)除去、アレル番号除去を実施",
        database_key="正規化した各IGHV候補 × 各IGHJ候補 × 正規化CDR3",
        candidate_rule="検体候補とDB候補のV/J組合せが1つ以上一致した配列だけを比較",
        cdr3_handling="大文字化し、両端がC…Wの場合だけ保存端を除去して比較",
        candidate_retention="最小距離のDB候補だけを保持し、検体クローンを1回計上",
        frequency_rule="RGのIn-frame readsが利用できる場合はそれを分母にし、列挙Readと別表示",
    ),
    MatchingMode.CDR3_ONLY: ModeSpecification(
        mode=MatchingMode.CDR3_ONLY,
        label="CDR3のみ方式（V/J不使用）",
        short_label="CDR3のみ",
        description="IGHV・IGHJを候補制限に使わず、CDR3アミノ酸配列だけで探索します。",
        sample_clone_key="正規化CDR3のみ（同じCDR3のReadをV/Jに関係なく合算）",
        sample_gene_handling="照合条件には使わず、表示用に観察された正規化候補を統合",
        database_key="正規化CDR3のみ（同じCDR3の注釈を統合）",
        candidate_rule="V/Jは使用せず、削除シグネチャ索引でLV0～LV2候補を漏れなく抽出後、正確な距離を計算",
        cdr3_handling="大文字化し、両端がC…Wの場合だけ保存端を除去して比較",
        candidate_retention="最小距離のDB CDR3候補だけを保持し、CDR3クローンを1回計上",
        frequency_rule="RGのIn-frame readsが利用できる場合はそれを分母にし、列挙Readと別表示",
    ),
}


GUI_MODE_LABELS = tuple(spec.label for spec in MODE_SPECIFICATIONS.values())


def parse_matching_mode(value: MatchingMode | str | None) -> MatchingMode:
    if value is None:
        return MatchingMode.KOBE
    if isinstance(value, MatchingMode):
        return value
    text = str(value).strip()
    lowered = text.lower().replace("_", "-")
    aliases = {
        "legacy": MatchingMode.LEGACY,
        "old": MatchingMode.LEGACY,
        "旧qasas": MatchingMode.LEGACY,
        "kobe": MatchingMode.KOBE,
        "kobe-ver-1.0": MatchingMode.KOBE,
        "cdr3": MatchingMode.CDR3_ONLY,
        "cdr3-only": MatchingMode.CDR3_ONLY,
        "cdr3のみ": MatchingMode.CDR3_ONLY,
    }
    if lowered in aliases:
        return aliases[lowered]
    for mode, spec in MODE_SPECIFICATIONS.items():
        if text in {spec.label, spec.short_label}:
            return mode
    valid = ", ".join(mode.value for mode in MatchingMode)
    raise ValueError(f"未対応の照合方式です: {value}（選択肢: {valid}）")


def mode_specification(value: MatchingMode | str | None) -> ModeSpecification:
    return MODE_SPECIFICATIONS[parse_matching_mode(value)]
