"""FM01～FM06 の 6 個の dict を full_parts にまとめる."""

from typing import Any, Dict

# merge.py の SECTION_ORDER に合わせたキー
FULL_MOCK_KEYS = [
    "listening_part_a",
    "listening_part_b",
    "listening_part_c",
    "grammar_part_a",
    "grammar_part_b",
    "reading",
]


def merge_full_mock_parts(
    fm01: Dict[str, Any],
    fm02: Dict[str, Any],
    fm03: Dict[str, Any],
    fm04: Dict[str, Any],
    fm05: Dict[str, Any],
    fm06_reading: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    6 個のセクション dict をキー listening_part_a, listening_part_b, ... reading の full_parts 辞書で返す.
    fm06_reading は fm06_merger.merge_fm06 の出力 ({"passages": [...]}).
    """
    parts = [fm01, fm02, fm03, fm04, fm05, fm06_reading]
    if len(FULL_MOCK_KEYS) != len(parts):
        raise ValueError("FM01～FM06 の 6 件が必要です")
    return dict(zip(FULL_MOCK_KEYS, parts))
