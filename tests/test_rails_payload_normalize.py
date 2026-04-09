"""rails_payload_normalize: Rails Question 制約との整合."""

import pytest

from app.services.rails_payload_normalize import (
    normalize_exercise_payload_for_rails,
    normalize_mock_payload_for_rails,
)


def test_normalize_mock_uppercases_correct_choice() -> None:
    payload = {
        "title": "T",
        "sections": [
            {
                "section_type": "listening",
                "display_order": 1,
                "parts": [
                    {
                        "part_type": "part_a",
                        "display_order": 1,
                        "question_sets": [
                            {
                                "display_order": 1,
                                "questions": [
                                    {
                                        "display_order": 1,
                                        "question_text": "Q",
                                        "choice_a": "a",
                                        "choice_b": "b",
                                        "choice_c": "c",
                                        "choice_d": "d",
                                        "correct_choice": "b",
                                        "tag": "fact",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    out = normalize_mock_payload_for_rails(payload)
    q = out["sections"][0]["parts"][0]["question_sets"][0]["questions"][0]
    assert q["correct_choice"] == "B"
    assert q["tag"] == "fact"
    # 入力は変えない
    assert payload["sections"][0]["parts"][0]["question_sets"][0]["questions"][0][
        "correct_choice"
    ] == "b"


def test_normalize_rejects_unknown_tag() -> None:
    payload = {
        "title": "T",
        "sections": [
            {
                "section_type": "listening",
                "display_order": 1,
                "parts": [
                    {
                        "part_type": "part_a",
                        "display_order": 1,
                        "question_sets": [
                            {
                                "display_order": 1,
                                "questions": [
                                    {
                                        "display_order": 1,
                                        "question_text": "Q",
                                        "choice_a": "a",
                                        "choice_b": "b",
                                        "choice_c": "c",
                                        "choice_d": "d",
                                        "correct_choice": "a",
                                        "tag": "mainIdea",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError, match="tag not allowed"):
        normalize_mock_payload_for_rails(payload)


def test_normalize_exercise_payload() -> None:
    payload = {
        "section_type": "listening",
        "part_type": "part_a",
        "question_sets": [
            {
                "display_order": 1,
                "questions": [
                    {
                        "display_order": 1,
                        "question_text": "Q",
                        "choice_a": "a",
                        "choice_b": "b",
                        "choice_c": "c",
                        "choice_d": "d",
                        "correct_choice": "c",
                        "tag": "vocab",
                    }
                ],
            }
        ],
    }
    out = normalize_exercise_payload_for_rails(payload)
    assert out["question_sets"][0]["questions"][0]["correct_choice"] == "C"
