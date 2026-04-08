"""Short 模試レポート (tag 必須) の単体テスト."""
import pytest

from app.services.analysis.report_generator_short import generate_short_report


def _item(qid: str, section: str, tag: str, correct: str = "A") -> dict:
    return {
        "item_id": qid,
        "question_id": qid,
        "section_id": section,
        "section_type": {"L": "listening", "S": "structure", "R": "reading"}[section],
        "part": "",
        "tag": tag,
        "correct_choice": correct,
    }


def test_short_report_tag_based():
    items = [
        _item("l1", "L", "shortConv"),
        _item("l2", "L", "longConv"),
        _item("s1", "S", "verbForm"),
        _item("r1", "R", "vocab"),
        _item("r2", "R", "vocab"),
    ]
    answers = [{"question_id": x["question_id"], "selected_choice": "A", "skipped": False} for x in items]
    passages = [{"theme": "P1", "question_ids": ["r1", "r2"]}]
    out = generate_short_report(
        {
            "attempt_id": "1",
            "answers": answers,
            "items": items,
            "passages": passages,
        }
    )
    assert "tag_accuracy" in out
    assert out["tag_accuracy"]["listening"]["shortConv"] == 100
    assert out["latest"]["verbForm"] == 100
    assert out["passages"][0]["score"] == 2
    assert out["passages"][0]["max"] == 2


def test_short_requires_tag():
    items = [
        {**_item("l1", "L", "shortConv"), "tag": ""},
    ]
    with pytest.raises(ValueError, match="tag"):
        generate_short_report(
            {"attempt_id": "1", "answers": [], "items": items, "passages": [{"theme": "x", "question_ids": ["r1"]}]},
        )


def test_short_requires_l_s_r():
    items = [_item("l1", "L", "shortConv")]
    with pytest.raises(ValueError, match="Listening/Structure/Reading"):
        generate_short_report(
            {
                "attempt_id": "1",
                "answers": [{"question_id": "l1", "selected_choice": "A", "skipped": False}],
                "items": items,
                "passages": [{"theme": "x", "question_ids": ["x"]}],
            }
        )
