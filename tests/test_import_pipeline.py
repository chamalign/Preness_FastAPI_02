"""import_pipeline: 音声アップロードをモックし DB 保存のみ差し替えて結線を検証."""
from unittest.mock import patch

import pytest

from app.schemas.import_payload import FullMockImportBody, PracticeImportBody
from app.services.generation.import_pipeline import (
    process_diagnostic_from_full_parts,
    process_mock_from_full_parts,
    process_practice_from_part_data,
)


def _listening_item() -> dict:
    return {
        "question_text": "Q",
        "choice_a": "a",
        "choice_b": "b",
        "choice_c": "c",
        "choice_d": "d",
        "correct_choice": "a",
        "tag": "fact",
        "content": {"listening_script": [{"speaker": "M", "text": "Hi"}]},
    }


def _grammar_part() -> dict:
    return {
        "questions": [
            {
                "question_text": "GQ",
                "choice_a": "a",
                "choice_b": "b",
                "choice_c": "c",
                "choice_d": "d",
                "correct_choice": "a",
                "tag": "fact",
            }
        ]
    }


def _reading_question(q_index: int) -> dict:
    return {
        "question_text": f"RQ{q_index}",
        "choice_a": "a",
        "choice_b": "b",
        "choice_c": "c",
        "choice_d": "d",
        "correct_choice": "b",
        "tag": "fact",
    }


def _reading_passages(count: int, questions_per: int = 10) -> dict:
    passages = []
    for pi in range(count):
        passages.append(
            {
                "passage": f"Passage {pi + 1} body.",
                "questions": [_reading_question(qi) for qi in range(1, questions_per + 1)],
            }
        )
    return {"passages": passages}


def _minimal_full_parts() -> dict:
    lp = {"items": [_listening_item()]}
    return {
        "listening_part_a": lp,
        "listening_part_b": lp,
        "listening_part_c": lp,
        "grammar_part_a": _grammar_part(),
        "grammar_part_b": _grammar_part(),
        "reading": _reading_passages(5),
    }


@patch("app.services.generation.import_pipeline.create_mock_from_payload", return_value=99)
@patch(
    "app.services.generation.import_pipeline.build_audio_url_map",
    return_value=({}, {}),
)
def test_process_mock_from_full_parts_wiring(_mock_au, _mock_create) -> None:
    out = process_mock_from_full_parts(
        full_parts=_minimal_full_parts(),
        title="T",
        audio_path_id="test-uuid",
        expected_reading_passages=5,
    )
    assert out == {"mock_id": 99}


def test_process_mock_rejects_wrong_reading_passage_count() -> None:
    bad = _minimal_full_parts()
    bad["reading"] = _reading_passages(1)
    with pytest.raises(ValueError, match="exactly 5"):
        process_mock_from_full_parts(
            full_parts=bad,
            title="T",
            audio_path_id="u",
            expected_reading_passages=5,
        )


def test_process_mock_rejects_reading_question_text_with_in_line() -> None:
    bad = _minimal_full_parts()
    q = bad["reading"]["passages"][0]["questions"][0]
    q["question_text"] = "RQ1 in line 1 is closest in meaning to"
    with pytest.raises(ValueError, match=r"must not contain the substring"):
        process_mock_from_full_parts(
            full_parts=bad,
            title="T",
            audio_path_id="u",
            expected_reading_passages=5,
        )


def test_process_diagnostic_rejects_reading_question_text_with_in_line() -> None:
    fp = _minimal_full_parts()
    fp["reading"] = _reading_passages(2)
    q = fp["reading"]["passages"][0]["questions"][0]
    q["question_text"] = "Bad in line 1"
    with pytest.raises(ValueError, match=r"must not contain the substring"):
        process_diagnostic_from_full_parts(
            full_parts=fp,
            title="Diag",
            audio_path_id="diag-uuid",
        )


def test_process_mock_rejects_reading_question_marker_missing_in_passage() -> None:
    bad = _minimal_full_parts()
    q = bad["reading"]["passages"][0]["questions"][0]
    q["question_text"] = 'The [V1]"alpha"[/V1] here'
    with pytest.raises(ValueError, match="passage must contain"):
        process_mock_from_full_parts(
            full_parts=bad,
            title="T",
            audio_path_id="u",
            expected_reading_passages=5,
        )


@patch("app.services.generation.import_pipeline.create_mock_from_payload", return_value=101)
@patch(
    "app.services.generation.import_pipeline.build_audio_url_map",
    return_value=({}, {}),
)
def test_process_diagnostic_from_full_parts_wiring(_mock_au, _mock_create) -> None:
    fp = _minimal_full_parts()
    fp["reading"] = _reading_passages(2)
    out = process_diagnostic_from_full_parts(
        full_parts=fp,
        title="Diag",
        audio_path_id="diag-uuid",
    )
    assert out == {"mock_id": 101}


@patch("app.services.generation.import_pipeline.create_exercise_from_payload", return_value=[7])
@patch(
    "app.services.generation.import_pipeline.build_audio_url_map",
    return_value=({}, {}),
)
def test_process_practice_listening_wiring(_mock_au, _mock_create) -> None:
    part = {"items": [_listening_item()]}
    out = process_practice_from_part_data(
        part_type="listening_part_a",
        part_data=part,
        audio_path_id="p-uuid",
    )
    assert out == {"exercise_ids": [7], "exercise_id": 7}


@patch("app.services.generation.import_pipeline.create_exercise_from_payload", return_value=[8])
def test_process_practice_grammar_no_audio(mock_create) -> None:
    part = _grammar_part()
    out = process_practice_from_part_data(
        part_type="grammar_part_a",
        part_data=part,
        audio_path_id="g-uuid",
    )
    assert out == {"exercise_ids": [8], "exercise_id": 8}


@patch("app.services.generation.import_pipeline.create_exercise_from_payload", return_value=[9])
def test_process_practice_reading_rejects_question_text_with_in_line(mock_create) -> None:
    part = _reading_passages(1)
    part["passages"][0]["questions"][0]["question_text"] = "Q in line 1?"
    with pytest.raises(ValueError, match=r"must not contain the substring"):
        process_practice_from_part_data(
            part_type="reading",
            part_data=part,
            audio_path_id="r-uuid",
        )


def test_full_mock_import_body_rejects_missing_key() -> None:
    with pytest.raises(ValueError, match="不足"):
        FullMockImportBody.model_validate(
            {"title": "x", "full_parts": {"listening_part_a": {}}}
        )


def test_practice_import_body_rejects_bad_part_type() -> None:
    with pytest.raises(ValueError, match="part_type"):
        PracticeImportBody.model_validate({"part_type": "invalid", "part_data": {}})
