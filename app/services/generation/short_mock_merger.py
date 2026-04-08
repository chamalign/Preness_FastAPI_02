"""SM01～SM06 の 6 個の dict を full_parts にまとめる (MockCreate 用)."""

from typing import Any, Dict

from app.services.generation.full_mock_merger import FULL_MOCK_KEYS


def merge_short_mock_parts(
    sm01: Dict[str, Any],
    sm02: Dict[str, Any],
    sm03: Dict[str, Any],
    sm04: Dict[str, Any],
    sm05: Dict[str, Any],
    sm06_reading: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    6 個の SM セクション dict をキー listening_part_a ... reading の full_parts 辞書で返す.
    build_mock_payload にそのまま渡せる.
    """
    parts = [sm01, sm02, sm03, sm04, sm05, sm06_reading]
    if len(FULL_MOCK_KEYS) != len(parts):
        raise ValueError("SM01～SM06 の 6 件が必要です")
    return dict(zip(FULL_MOCK_KEYS, parts))
