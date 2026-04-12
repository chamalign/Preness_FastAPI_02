"""分析ジョブ投入ペイロードから模試種別（full / short）を推定する."""
from typing import Literal, Tuple

from app.schemas.analysis import PartsAccuracy

ExamType = Literal["full", "short"]

# 本番想定の問題数シグネチャ（Rails 側の固定フォーマットと一致させる）
_FULL_LISTENING_TOTALS: Tuple[int, int, int] = (30, 8, 12)
_FULL_STRUCTURE_TOTALS: Tuple[int, int] = (15, 25)
_FULL_READING_EACH = 10

_SHORT_LISTENING_TOTALS: Tuple[int, int, int] = (12, 6, 8)
_SHORT_STRUCTURE_TOTALS: Tuple[int, int] = (10, 18)
# Short は Reading 2 パッセージ × 8 問. 固定キー Reading_01〜05 のうち未使用は total 0.
_SHORT_READING_TOTALS: Tuple[int, int, int, int, int] = (8, 8, 0, 0, 0)


def infer_exam_type(parts: PartsAccuracy) -> ExamType:
    """
    parts_accuracy の各パート total から full / short を判定する.

    いずれの既知シグネチャにも一致しない場合は ValueError.
    """
    lt = (
        parts.listening.part_a.total,
        parts.listening.part_b.total,
        parts.listening.part_c.total,
    )
    st = (parts.structure.part_a.total, parts.structure.part_b.total)
    rt = (
        parts.reading.reading_01.total,
        parts.reading.reading_02.total,
        parts.reading.reading_03.total,
        parts.reading.reading_04.total,
        parts.reading.reading_05.total,
    )

    if lt == _FULL_LISTENING_TOTALS and st == _FULL_STRUCTURE_TOTALS:
        if all(t == _FULL_READING_EACH for t in rt):
            return "full"
    if lt == _SHORT_LISTENING_TOTALS and st == _SHORT_STRUCTURE_TOTALS:
        if rt == _SHORT_READING_TOTALS:
            return "short"

    raise ValueError(
        "parts_accuracy の問題数から full / short を特定できません. "
        "full: Listening 30/8/12, Structure 15/25, Reading 各10問. "
        "short: Listening 12/6/8, Structure 10/18, Reading 8/8/0/0/0 である必要があります."
    )
