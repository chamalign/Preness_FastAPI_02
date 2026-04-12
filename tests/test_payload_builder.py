"""payload_builder: build_listening_part_for_api のグループ化ロジックを検証."""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.generation.payload_builder import SCRIPT_PLACEMENT, build_listening_part_for_api


def _make_item(q_text: str, script_body: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "question_text": q_text,
        "choice_a": "A",
        "choice_b": "B",
        "choice_c": "C",
        "choice_d": "D",
        "correct_choice": "a",
        "tag": "longConv",
        "content": {"listening_script": script_body},
    }


_SHARED_SCRIPT = [
    {"speaker": "narrator", "text": "Question 1."},
    {"speaker": "man", "text": "Hello."},
    {"speaker": "woman", "text": "Hi there."},
    {"speaker": "narrator", "text": "What are they doing?"},
]


def test_listening_bc_grouped_into_one_question_set() -> None:
    """Listening B/C: 同一ブロックの 4 items が 1 question_set × 4 questions にまとまる."""
    items = [_make_item(f"Q{i}", _SHARED_SCRIPT) for i in range(1, 5)]
    part_json = {"items": items}

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_b",
        display_order=2,
        audio_url_map=None,
        block_starts_per_part={"part_b": [1]},
    )

    assert result["part_type"] == "part_b"
    question_sets = result["question_sets"]
    assert len(question_sets) == 1, f"Expected 1 question_set, got {len(question_sets)}"

    qs = question_sets[0]
    assert qs["display_order"] == 1
    assert len(qs["questions"]) == 4, f"Expected 4 questions, got {len(qs['questions'])}"

    for expected_order, q in enumerate(qs["questions"], start=1):
        assert q["display_order"] == expected_order
        assert q["question_text"] == f"Q{expected_order}"


def test_listening_a_each_item_independent_question_set() -> None:
    """Listening A: 各 item が独立ブロックのとき 4 question_sets × 1 question になる."""
    scripts = [
        [{"speaker": "man", "text": f"Conversation {i}."}]
        for i in range(1, 5)
    ]
    items = [_make_item(f"Q{i}", scripts[i - 1]) for i in range(1, 5)]
    part_json = {"items": items}

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_a",
        display_order=1,
        audio_url_map=None,
        block_starts_per_part={"part_a": [1, 2, 3, 4]},
    )

    question_sets = result["question_sets"]
    assert len(question_sets) == 4, f"Expected 4 question_sets, got {len(question_sets)}"

    for i, qs in enumerate(question_sets, start=1):
        assert qs["display_order"] == i
        assert len(qs["questions"]) == 1
        assert qs["questions"][0]["display_order"] == 1
        assert qs["questions"][0]["question_text"] == f"Q{i}"


def test_listening_bc_audio_url_shared_per_block() -> None:
    """Listening B/C: ブロック内の全 question が同じ passage_url を共有し, question_audio_url は個別."""
    items = [_make_item(f"Q{i}", _SHARED_SCRIPT) for i in range(1, 5)]
    part_json = {"items": items}
    audio_url_map = {
        "part_b:1:passage": "https://example.com/passage.wav",
        "part_b:1:question": "https://example.com/q1.wav",
        "part_b:2:question": "https://example.com/q2.wav",
        "part_b:3:question": "https://example.com/q3.wav",
        "part_b:4:question": "https://example.com/q4.wav",
    }

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_b",
        display_order=2,
        audio_url_map=audio_url_map,
        block_starts_per_part={"part_b": [1]},
        # SCRIPT_PLACEMENT="questions" の場合 passage_url は q.conversation_audio_url に入る
        script_placement="questions",
    )

    qs = result["question_sets"][0]
    # question_sets レベルには入らない ("questions" placement の仕様)
    assert qs["conversation_audio_url"] is None

    for i, q in enumerate(qs["questions"], start=1):
        assert q["conversation_audio_url"] == "https://example.com/passage.wav"
        assert q["question_audio_url"] == f"https://example.com/q{i}.wav"


def test_script_placement_questions_sets_scripts_on_question() -> None:
    """SCRIPT_PLACEMENT='questions' のとき scripts は question に付き question_set には None."""
    items = [_make_item(f"Q{i}", _SHARED_SCRIPT) for i in range(1, 5)]
    part_json = {"items": items}

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_b",
        display_order=2,
        audio_url_map=None,
        block_starts_per_part={"part_b": [1]},
        script_placement="questions",
    )

    qs = result["question_sets"][0]
    assert qs["scripts"] is None
    for q in qs["questions"]:
        assert q["scripts"] == _SHARED_SCRIPT


def test_script_placement_question_sets_sets_scripts_on_qs() -> None:
    """SCRIPT_PLACEMENT='question_sets' のとき scripts は question_set に付き question には None."""
    items = [_make_item(f"Q{i}", _SHARED_SCRIPT) for i in range(1, 5)]
    part_json = {"items": items}

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_b",
        display_order=2,
        audio_url_map=None,
        block_starts_per_part={"part_b": [1]},
        script_placement="question_sets",
    )

    qs = result["question_sets"][0]
    assert qs["scripts"] == _SHARED_SCRIPT
    for q in qs["questions"]:
        assert q["scripts"] is None


def test_no_block_starts_falls_back_to_individual() -> None:
    """block_starts_per_part が None のとき, 各 item が独立 question_set になる."""
    items = [_make_item(f"Q{i}", _SHARED_SCRIPT) for i in range(1, 3)]
    part_json = {"items": items}

    result = build_listening_part_for_api(
        part_json=part_json,
        part_type="part_c",
        display_order=3,
        audio_url_map=None,
        block_starts_per_part=None,
    )

    assert len(result["question_sets"]) == 2
