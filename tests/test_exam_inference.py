"""parts_accuracy から full / short を推定するロジックのテスト."""
import json
from pathlib import Path

import pytest

from app.schemas.analysis import (
    AnalysisRequest,
    ListeningPartsAccuracy,
    PartStat,
    PartsAccuracy,
    ReadingPartsAccuracy,
    ReadingPassageStat,
    StructurePartsAccuracy,
)
from app.services.analysis.exam_inference import infer_exam_type


def _passage(total: int, correct: int = 0) -> ReadingPassageStat:
    return ReadingPassageStat(correct=correct, total=total)


def _full_parts() -> PartsAccuracy:
    return PartsAccuracy(
        listening=ListeningPartsAccuracy(
            part_a=PartStat(correct=1, total=30),
            part_b=PartStat(correct=1, total=8),
            part_c=PartStat(correct=1, total=12),
        ),
        structure=StructurePartsAccuracy(
            part_a=PartStat(correct=1, total=15),
            part_b=PartStat(correct=1, total=25),
        ),
        reading=ReadingPartsAccuracy(
            reading_01=_passage(10),
            reading_02=_passage(10),
            reading_03=_passage(10),
            reading_04=_passage(10),
            reading_05=_passage(10),
        ),
    )


def _short_parts() -> PartsAccuracy:
    return PartsAccuracy(
        listening=ListeningPartsAccuracy(
            part_a=PartStat(correct=1, total=12),
            part_b=PartStat(correct=1, total=6),
            part_c=PartStat(correct=1, total=8),
        ),
        structure=StructurePartsAccuracy(
            part_a=PartStat(correct=1, total=10),
            part_b=PartStat(correct=1, total=18),
        ),
        reading=ReadingPartsAccuracy(
            reading_01=_passage(8),
            reading_02=_passage(8),
            reading_03=_passage(0),
            reading_04=_passage(0),
            reading_05=_passage(0),
        ),
    )


def test_infer_full_canonical() -> None:
    assert infer_exam_type(_full_parts()) == "full"


def test_infer_short_canonical() -> None:
    assert infer_exam_type(_short_parts()) == "short"


def test_sample_repo_json_fixtures_infer() -> None:
    """リポジトリ直下のサンプル JSON がスキーマと推定の両方に通る."""
    root = Path(__file__).resolve().parents[1]
    for fname, expected in (
        ("analysis_full_payload.json", "full"),
        ("analysis_short_payload.json", "short"),
    ):
        raw = json.loads((root / fname).read_text(encoding="utf-8"))
        req = AnalysisRequest.model_validate(raw)
        assert infer_exam_type(req.parts_accuracy) == expected


def test_infer_rejects_unknown_totals() -> None:
    parts = _full_parts()
    bad_listening = parts.listening.model_copy(
        update={"part_a": PartStat(correct=0, total=29)}
    )
    bad = parts.model_copy(update={"listening": bad_listening})
    with pytest.raises(ValueError, match="特定できません"):
        infer_exam_type(bad)
