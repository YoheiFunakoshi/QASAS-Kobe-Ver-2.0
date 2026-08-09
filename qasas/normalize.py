from __future__ import annotations

import re
from collections.abc import Iterable


_EMPTY_VALUES = {
    "",
    "-",
    "--",
    "N/A",
    "NA",
    "NAN",
    "NONE",
    "NULL",
    "ND",
    "UNKNOWN",
    "UNASSIGNED",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() in _EMPTY_VALUES else text


def normalize_gene_options(value: object, locus: str) -> tuple[str, ...]:
    """Normalize an IGHV/IGHJ call into unique allele-free alternatives."""

    text = clean_text(value)
    if not text:
        return ()

    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\b(?:OR|AND)\b", "//", text, flags=re.IGNORECASE)
    pieces = re.split(r"\s*(?://|[,;|/])\s*", text)
    expected_prefix = locus.upper()
    output: list[str] = []
    seen: set[str] = set()

    for piece in pieces:
        gene = piece.strip().upper().replace(" ", "")
        if expected_prefix == "IGHJ" and gene.startswith("IHGJ"):
            gene = "IGHJ" + gene[4:]
        gene = re.sub(r"\*[^,;/|\s]+$", "", gene)
        gene = gene.rstrip(".:")
        if not gene or gene in _EMPTY_VALUES:
            continue
        match = re.search(rf"({re.escape(expected_prefix)}[A-Z0-9.-]+)", gene)
        if match:
            gene = match.group(1)
        if not gene.startswith(expected_prefix):
            continue
        if gene not in seen:
            seen.add(gene)
            output.append(gene)
    return tuple(output)


def normalize_cdr3(value: object, trim_anchors: bool = True) -> str:
    """Normalize an amino-acid CDR3 and harmonize CPM/RG C...W anchors."""

    text = clean_text(value).upper()
    text = re.sub(r"[^A-Z*]", "", text)
    if trim_anchors and len(text) > 2 and text.startswith("C") and text.endswith("W"):
        text = text[1:-1]
    return text


def parse_positive_int(value: object, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default
    if number < 0:
        return default
    return int(round(number))


def parse_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    text = str(value).replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def join_unique(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return tuple(output)
