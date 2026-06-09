"""reading_content: sanitize / validate / prepare."""

import copy

import pytest

from app.services.generation.reading_content import (
    prepare_reading_for_mock,
    sanitize_reading,
    validate_reading,
)


def _q(correct: str = "B") -> dict:
    return {
        "question_text": "Q?",
        "choice_a": "a",
        "choice_b": "b",
        "choice_c": "c",
        "choice_d": "d",
        "correct_choice": correct,
        "tag": "fact",
    }


def _passage(body: str = "Body.", n_questions: int = 10) -> dict:
    return {
        "passage": body,
        "questions": [_q("B") for _ in range(n_questions)],
    }


def test_sanitize_uppercases_correct_choice_and_strips() -> None:
    reading = {
        "passages": [
            {
                "passage": "P1",
                "questions": [
                    {
                        "question_text": "  hi  ",
                        "choice_a": " x ",
                        "choice_b": "y",
                        "choice_c": "z",
                        "choice_d": "w",
                        "correct_choice": " c ",
                    }
                ],
            }
        ]
    }
    out = sanitize_reading(reading)
    assert out is not reading
    q = out["passages"][0]["questions"][0]
    assert q["question_text"] == "hi"
    assert q["choice_a"] == "x"
    assert q["correct_choice"] == "C"


def test_validate_passage_count_mismatch() -> None:
    reading = {"passages": [_passage(), _passage()]}
    with pytest.raises(ValueError, match="exactly 5"):
        validate_reading(reading, expected_passages=5)


def test_validate_question_count_mismatch() -> None:
    reading = {"passages": [_passage(n_questions=9)]}
    with pytest.raises(ValueError, match="exactly 10"):
        validate_reading(reading, expected_passages=1)


def test_validate_missing_key() -> None:
    bad = copy.deepcopy(_passage())
    del bad["questions"][0]["choice_c"]
    reading = {"passages": [bad]}
    with pytest.raises(ValueError, match="missing required key"):
        validate_reading(reading, expected_passages=1)


def test_validate_invalid_correct_choice() -> None:
    bad = _passage()
    bad["questions"][0]["correct_choice"] = "X"
    reading = {"passages": [bad]}
    with pytest.raises(ValueError, match="one of A/B/C/D"):
        validate_reading(reading, expected_passages=1)


def test_validate_rejects_question_text_with_in_line() -> None:
    bad = _passage()
    bad["questions"][0][
        "question_text"
    ] = 'The word \"x\" in line 4 is closest in meaning to'
    reading = {"passages": [bad]}
    with pytest.raises(ValueError, match=r"must not contain the substring"):
        validate_reading(reading, expected_passages=1)


def test_validate_passes_when_question_markers_match_passage() -> None:
    body = "Preface. [V1]instantaneously[/V1] mid."
    p = _passage(body=body, n_questions=10)
    p["questions"][0]["question_text"] = (
        'The word [V1]"instantaneously"[/V1] in paragraph 1, sentence 2 is closest'
    )
    validate_reading({"passages": [p]}, expected_passages=1)


def test_validate_rejects_when_question_marker_missing_in_passage() -> None:
    body = "No markers here, just plain instantly."
    p = _passage(body=body, n_questions=10)
    p["questions"][0]["question_text"] = (
        'The word [V1]"instantaneously"[/V1] in paragraph 1 is closest'
    )
    reading = {"passages": [p]}
    with pytest.raises(ValueError, match="passage must contain"):
        validate_reading(reading, expected_passages=1)


def test_prepare_reading_for_mock_mutates_full_parts() -> None:
    fp = {
        "reading": {
            "passages": [
                _passage("A"),
                _passage("B"),
            ]
        }
    }
    prepare_reading_for_mock(fp, expected_passages=2)
    assert fp["reading"]["passages"][0]["questions"][0]["correct_choice"] == "B"


def test_prepare_rejects_non_dict_reading() -> None:
    with pytest.raises(ValueError, match="reading.*must be a dict"):
        prepare_reading_for_mock({"reading": None}, expected_passages=2)
