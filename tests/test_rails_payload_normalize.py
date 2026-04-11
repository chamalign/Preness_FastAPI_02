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
    out = normalize_mock_payload_for_rails(payload)
    q = out["sections"][0]["parts"][0]["question_sets"][0]["questions"][0]
    # mainIdea は inference に寄せる
    assert q["tag"] == "inference"


def test_normalize_fallbacks_unknown_tag_to_fact() -> None:
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
                                        "tag": "completely_unknown_tag",
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
    assert q["tag"] == "fact"


def _grammar_b_mock_payload(question_text: str, choice_a: str = "A") -> dict:
    return {
        "title": "T",
        "sections": [
            {
                "section_type": "structure",
                "display_order": 2,
                "parts": [
                    {
                        "part_type": "part_b",
                        "display_order": 2,
                        "question_sets": [
                            {
                                "display_order": 1,
                                "questions": [
                                    {
                                        "display_order": 1,
                                        "question_text": question_text,
                                        "choice_a": choice_a,
                                        "choice_b": "B",
                                        "choice_c": "C",
                                        "choice_d": "D",
                                        "correct_choice": "A",
                                        "tag": "verbForm",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_grammar_b_choices_extracted_from_tags() -> None:
    """Grammar Part B: [A]...[/A] タグから choice_* を抽出して上書きする."""
    qt = "The [A]recent[/A] discovered [B]fossils[/B] [C]provide[/C] researchers [D]with[/D] insights."
    out = normalize_mock_payload_for_rails(_grammar_b_mock_payload(qt))
    q = out["sections"][0]["parts"][0]["question_sets"][0]["questions"][0]
    assert q["choice_a"] == "recent"
    assert q["choice_b"] == "fossils"
    assert q["choice_c"] == "provide"
    assert q["choice_d"] == "with"


def test_grammar_b_choices_not_overwritten_when_no_tags() -> None:
    """タグがない場合 (Part A 相当) は choice_* を変更しない."""
    qt = "_______ process by which plants convert light into energy is known as photosynthesis."
    out = normalize_mock_payload_for_rails(_grammar_b_mock_payload(qt, choice_a="It is the"))
    q = out["sections"][0]["parts"][0]["question_sets"][0]["questions"][0]
    assert q["choice_a"] == "It is the"


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
