"""import_pipeline: 音声アップロードをモックし DB 保存のみ差し替えて結線を検証."""
from unittest.mock import patch

import pytest

from app.schemas.import_payload import FullMockImportBody, PracticeImportBody
from app.services.generation.import_pipeline import (
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
            }
        ]
    }


def _reading() -> dict:
    return {
        "passages": [
            {
                "passage": "P",
                "questions": [
                    {
                        "question_text": "RQ",
                        "choice_a": "a",
                        "choice_b": "b",
                        "choice_c": "c",
                        "choice_d": "d",
                        "correct_choice": "a",
                    }
                ],
            }
        ]
    }


def _minimal_full_parts() -> dict:
    lp = {"items": [_listening_item()]}
    return {
        "listening_part_a": lp,
        "listening_part_b": lp,
        "listening_part_c": lp,
        "grammar_part_a": _grammar_part(),
        "grammar_part_b": _grammar_part(),
        "reading": _reading(),
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
    )
    assert out == {"mock_id": 99}


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


def test_full_mock_import_body_rejects_missing_key() -> None:
    with pytest.raises(ValueError, match="不足"):
        FullMockImportBody.model_validate(
            {"title": "x", "full_parts": {"listening_part_a": {}}}
        )


def test_practice_import_body_rejects_bad_part_type() -> None:
    with pytest.raises(ValueError, match="part_type"):
        PracticeImportBody.model_validate({"part_type": "invalid", "part_data": {}})
