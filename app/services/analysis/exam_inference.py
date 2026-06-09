"""分析ジョブ投入ペイロードから模試種別（full / short）を推定する."""
from typing import Literal, Tuple

from app.schemas.analysis import PartsAccuracy

ExamType = Literal["full", "short"]

# 本番想定の問題数シグネチャ（Rails 側の固定フォーマットと一致させる）
_FULL_LISTENING_TOTALS: Tuple[int, int, int] = (30, 8, 12)
_FULL_STRUCTURE_TOTALS: Tuple[int, int] = (15, 25)
_FULL_READING_EACH = 10

_SHORT_LISTENING_TOTALS: Tuple[int, int, int] = (8, 8, 8)
_SHORT_STRUCTURE_TOTALS: Tuple[int, int] = (8, 8)
# Short は Reading 2 パッセージ × 10 問. Reading_03〜05 は省略可（スキーマ既定で total 0）.
_SHORT_READING_TOTALS: Tuple[int, int, int, int, int] = (10, 10, 0, 0, 0)

# 実力診断 (diagnostics) シグネチャ: Part B/C 各 2 問, Structure は partA なし (0/0).
_DIAG_LISTENING_TOTALS: Tuple[int, int, int] = (8, 2, 2)
_DIAG_STRUCTURE_TOTALS: Tuple[int, int] = (0, 8)
_DIAG_READING_TOTALS: Tuple[int, int, int, int, int] = (10, 10, 0, 0, 0)


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
    if lt == _DIAG_LISTENING_TOTALS and st == _DIAG_STRUCTURE_TOTALS:
        if rt == _DIAG_READING_TOTALS:
            return "short"

    raise ValueError(
        "parts_accuracy の問題数から full / short を特定できません. "
        "full: Listening 30/8/12, Structure 15/25, Reading 各10問. "
        "short: Listening 8/8/8, Structure 8/8, Reading は 10/10 のみでも可. "
        "diagnostic: Listening 8/2/2, Structure partA なし/8, Reading 10/10."
    )
