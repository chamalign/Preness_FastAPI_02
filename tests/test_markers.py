"""inject_reading_markers のテスト."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.generation.markers import (
    IdempotencyError,
    MarkerError,
    inject_reading_markers,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _q(
    question_text: str,
    tag: str,
    *,
    target_phrase: str | None = None,
    target_paragraph: int | None = None,
    target_sentence: int | None = None,
) -> dict:
    return {
        "question_text": question_text,
        "choice_a": "a",
        "choice_b": "b",
        "choice_c": "c",
        "choice_d": "d",
        "correct_choice": "A",
        "tag": tag,
        "target_phrase": target_phrase,
        "target_paragraph": target_paragraph,
        "target_sentence": target_sentence,
    }


# ──────────────────────────────────────────────
# test 1: 3つの vocab 設問に [U1][U2][U3] が順番に振られる
# ──────────────────────────────────────────────
def test_inject_reading_markers_three_vocab() -> None:
    passage = (
        "The swift river flows through the valley. "
        "They enjoy the view from the bridge.\n\n"
        "The process facilitates the growth of plants. "
        "It requires sunshine and water."
    )
    questions = [
        _q(
            'The word "swift" in paragraph 1, sentence 1 is closest in meaning to',
            "vocab",
            target_phrase="swift",
            target_paragraph=1,
            target_sentence=1,
        ),
        _q(
            'The word "They" in paragraph 1, sentence 2 refers to',
            "usage",
            target_phrase="They",
            target_paragraph=1,
            target_sentence=2,
        ),
        _q(
            'The word "facilitates" in paragraph 2, sentence 1 is closest in meaning to',
            "vocab",
            target_phrase="facilitates",
            target_paragraph=2,
            target_sentence=1,
        ),
    ]
    marked_passage, marked_questions = inject_reading_markers(passage, questions)

    assert "[U1]swift[/U1]" in marked_passage
    assert "[U2]They[/U2]" in marked_passage
    assert "[U3]facilitates[/U3]" in marked_passage

    # 出現順が U1 < U2 < U3
    p1 = marked_passage.index("[U1]")
    p2 = marked_passage.index("[U2]")
    p3 = marked_passage.index("[U3]")
    assert p1 < p2 < p3

    assert '"[U1]swift[/U1]"' in marked_questions[0]["question_text"]
    assert '"[U2]They[/U2]"' in marked_questions[1]["question_text"]
    assert '"[U3]facilitates[/U3]"' in marked_questions[2]["question_text"]


# ──────────────────────────────────────────────
# test 2: vocab と usage が混在しても順序通りにカウンターが振られる
# ──────────────────────────────────────────────
def test_inject_reading_markers_mixed_vocab_and_usage() -> None:
    passage = (
        "Scientists observe phenomena carefully. "
        "They record their findings systematically. "
        "New discoveries transform our understanding."
    )
    questions = [
        _q(
            'The word "phenomena" in paragraph 1 is closest in meaning to',
            "vocab",
            target_phrase="phenomena",
            target_paragraph=1,
            target_sentence=1,
        ),
        _q(
            'The word "They" in paragraph 1, sentence 2 refers to',
            "usage",
            target_phrase="They",
            target_paragraph=1,
            target_sentence=2,
        ),
        _q(
            'The word "transform" in paragraph 1 is closest in meaning to',
            "vocab",
            target_phrase="transform",
            target_paragraph=1,
            target_sentence=3,
        ),
    ]
    marked_passage, marked_questions = inject_reading_markers(passage, questions)

    assert "[U1]phenomena[/U1]" in marked_passage
    assert "[U2]They[/U2]" in marked_passage
    assert "[U3]transform[/U3]" in marked_passage

    assert '"[U1]phenomena[/U1]"' in marked_questions[0]["question_text"]
    assert '"[U2]They[/U2]"' in marked_questions[1]["question_text"]
    assert '"[U3]transform[/U3]"' in marked_questions[2]["question_text"]


# ──────────────────────────────────────────────
# test 3: mainIdea / fact / inference / not / rhetorical はスキップ
# ──────────────────────────────────────────────
def test_inject_reading_markers_skips_non_vocab_usage() -> None:
    passage = "The planet orbits the sun. Life evolved over billions of years."
    questions = [
        _q("The passage mainly discusses", "mainIdea"),
        _q("According to the passage", "fact"),
        _q("It can be inferred that", "inference"),
        _q("Which of the following is NOT mentioned", "not"),
        _q("Why does the author mention this?", "rhetorical"),
    ]
    original_texts = [q["question_text"] for q in questions]
    marked_passage, marked_questions = inject_reading_markers(passage, questions)

    # passage に U マーカーが追加されていない
    assert "[U" not in marked_passage

    # 各設問の question_text が変更されていない
    for orig, marked_q in zip(original_texts, marked_questions):
        assert marked_q["question_text"] == orig


# ──────────────────────────────────────────────
# test 4: target_phrase が passage に存在しない → MarkerError
# ──────────────────────────────────────────────
def test_inject_reading_markers_phrase_not_in_passage() -> None:
    passage = "Water flows downhill. Rivers carry sediment."
    questions = [
        _q(
            'The word "nonexistent" in paragraph 1 is closest in meaning to',
            "vocab",
            target_phrase="nonexistent",
            target_paragraph=1,
            target_sentence=1,
        ),
    ]
    with pytest.raises(MarkerError) as exc_info:
        inject_reading_markers(passage, questions)

    err = exc_info.value
    assert err.item_index == 0
    assert "not found in passage" in err.reason


# ──────────────────────────────────────────────
# test 5: target_phrase が passage 内に2回以上 → MarkerError
# ──────────────────────────────────────────────
def test_inject_reading_markers_phrase_duplicated_in_passage() -> None:
    passage = "Water is clear. Water flows freely."
    questions = [
        _q(
            'The word "Water" in paragraph 1 is closest in meaning to',
            "vocab",
            target_phrase="Water",
            target_paragraph=1,
            target_sentence=1,
        ),
    ]
    with pytest.raises(MarkerError) as exc_info:
        inject_reading_markers(passage, questions)

    err = exc_info.value
    assert err.item_index == 0
    assert "appears 2 times" in err.reason


# ──────────────────────────────────────────────
# test 6: passage にはあるが question_text にない → MarkerError
# ──────────────────────────────────────────────
def test_inject_reading_markers_phrase_not_in_question_text() -> None:
    passage = "Photosynthesis converts sunlight into energy. Plants use this process."
    questions = [
        _q(
            "Which of the following best describes what plants do?",  # "Photosynthesis" not here
            "vocab",
            target_phrase="Photosynthesis",
            target_paragraph=1,
            target_sentence=1,
        ),
    ]
    with pytest.raises(MarkerError) as exc_info:
        inject_reading_markers(passage, questions)

    err = exc_info.value
    assert err.item_index == 0
    assert "not found in question_text" in err.reason


# ──────────────────────────────────────────────
# test 7: question_text に "X" と X の両方がある → 引用符付き形が優先
# ──────────────────────────────────────────────
def test_inject_reading_markers_quoted_form_preferred() -> None:
    passage = "The word rapid describes swift movement."
    questions = [
        _q(
            'rapid The word "rapid" in paragraph 1 describes',
            "vocab",
            target_phrase="rapid",
            target_paragraph=1,
            target_sentence=1,
        ),
    ]
    _, marked_questions = inject_reading_markers(passage, questions)
    qt = marked_questions[0]["question_text"]

    # 引用符付き形がマーカー化されている
    assert '"[U1]rapid[/U1]"' in qt
    # 先頭の裸の rapid は変更されていない (引用符付きを優先したため)
    assert qt.startswith("rapid ")


# ──────────────────────────────────────────────
# test 8: 既にマーカーがある passage → IdempotencyError
# ──────────────────────────────────────────────
def test_inject_reading_markers_idempotency() -> None:
    passage = "The [U1]swift[/U1] river flows down the valley."
    questions = [
        _q(
            'The word "swift" in paragraph 1 is closest in meaning to',
            "vocab",
            target_phrase="swift",
            target_paragraph=1,
            target_sentence=1,
        ),
    ]
    with pytest.raises(IdempotencyError):
        inject_reading_markers(passage, questions)


# ──────────────────────────────────────────────
# test 9: フィクスチャ golden file 比較
# ──────────────────────────────────────────────
def test_inject_reading_markers_fixture_p06() -> None:
    input_data = json.loads((FIXTURES / "p06_good_input.txt").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "p06_good_output.json").read_text(encoding="utf-8"))

    passage = input_data["passage"]
    questions = input_data["questions"]

    marked_passage, marked_questions = inject_reading_markers(passage, questions)

    assert marked_passage == expected["passage"], "passage mismatch"
    for i, (got_q, exp_q) in enumerate(zip(marked_questions, expected["questions"])):
        assert got_q["question_text"] == exp_q["question_text"], (
            f"question[{i}] question_text mismatch:\n"
            f"  got:      {got_q['question_text']!r}\n"
            f"  expected: {exp_q['question_text']!r}"
        )
