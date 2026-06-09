"""分析レポート（集計入力 + スコア計算）の単体テスト."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.analysis.report_generator import calculate_scores, generate_report

_DUMMY_NARRATIVES = {
    "summary_closing": "総評テスト",
    "strength": "強みテスト",
    "challenge": "課題テスト",
}


def test_calculate_scores_full_shape():
    parts = {
        "listening": {
            "partA": {"correct": 30, "total": 30},
            "partB": {"correct": 8, "total": 8},
            "partC": {"correct": 12, "total": 12},
        },
        "structure": {
            "partA": {"correct": 15, "total": 15},
            "partB": {"correct": 25, "total": 25},
        },
        "reading": {
            "Reading_01": {"correct": 10, "total": 10},
            "Reading_02": {"correct": 10, "total": 10},
            "Reading_03": {"correct": 10, "total": 10},
            "Reading_04": {"correct": 10, "total": 10},
            "Reading_05": {"correct": 10, "total": 10},
        },
    }
    scores = calculate_scores(parts)
    assert scores["listening"] == 68
    assert scores["structure"] == 68
    assert scores["reading"] == 67
    assert scores["total"] == 677
    assert scores["max"] == 677  # 内部・DB 用. Rails POST では送らない


def test_calculate_scores_empty_section_returns_min():
    parts = {
        "listening": {"partA": {"correct": 0, "total": 4}},
        "structure": {"partA": {"correct": 0, "total": 4}},
        "reading": {"Reading_01": {"correct": 0, "total": 4}},
    }
    scores = calculate_scores(parts)
    assert scores["listening"] == 31
    assert scores["structure"] == 31
    assert scores["reading"] == 31
    assert scores["total"] == 310


@pytest.mark.asyncio
async def test_generate_report_requires_parts_accuracy():
    with pytest.raises(ValueError, match="parts_accuracy"):
        await generate_report({"tags": {}})


@pytest.mark.asyncio
async def test_generate_report_returns_scores_and_narratives():
    payload = {
        "goal": {"target_score": 500},
        "parts_accuracy": {
            "listening": {"partA": {"correct": 1, "total": 4}},
            "structure": {"partA": {"correct": 1, "total": 4}},
            "reading": {"Reading_01": {"correct": 1, "total": 4}},
        },
        "tags": {"shortConv": {"correct": 1, "total": 2}},
    }
    with patch(
        "app.services.analysis.report_generator._generate_narratives_with_gpt",
        new=AsyncMock(return_value=_DUMMY_NARRATIVES),
    ):
        out = await generate_report(payload)
    assert "scores" in out
    assert "narratives" in out
    assert "report_date" in out
    assert set(out["narratives"].keys()) == {"summary_closing", "strength", "challenge"}
