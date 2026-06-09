"""GPT 中間形式 (full_parts / part_data) から TTS→S3→MockCreate/ExerciseCreate 保存まで."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.schemas.exercises import ExerciseCreate
from app.schemas.mocks import MockCreate
from app.services.exercise_service import create_exercise_from_payload
from app.services.mock_service import create_mock_from_payload
from app.services.rails_client import (
    post_diagnostic_to_rails,
    post_exercise_to_rails,
    post_mock_to_rails,
)
from app.services.rails_payload_normalize import (
    normalize_exercise_payload_for_rails,
    normalize_mock_payload_for_rails,
)
from app.services.generation.audio_upload import build_audio_url_map
from app.services.generation.payload_builder import build_exercise_payload, build_mock_payload
from app.services.generation.reading_content import prepare_reading_for_mock

logger = logging.getLogger(__name__)

# Rails 送信と同時にバックアップとして保存するディレクトリ
# app/services/generation/ の 3 階層上が FastAPI ルート
_OUTPUTS_DIR = Path(__file__).resolve().parents[3] / "outputs"


def _save_rails_payload(payload: Dict[str, Any], filename: str) -> Path:
    """payload を _OUTPUTS_DIR/{filename}.json に書き出して Path を返す."""
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUTS_DIR / f"{filename}.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved Rails payload: %s", out_path)
    return out_path


def _full_parts_to_mock_id_and_rails_payload(
    *,
    full_parts: Dict[str, Dict[str, Any]],
    title: str,
    audio_path_id: str,
    expected_reading_passages: int,
) -> tuple[int, Dict[str, Any]]:
    """full_parts を検証・変換し DB 保存用 MockCreate と Rails 送信用ペイロードを組み立てる."""
    for part_key in ("listening_part_a", "listening_part_b", "listening_part_c"):
        part = full_parts.get(part_key)
        if not isinstance(part, dict):
            continue
        items = part.get("items")
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"{part_key}.items must be a list")
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"{part_key}.items[{idx}] must be an object")
            content = item.get("content") or {}
            if not isinstance(content, dict):
                raise ValueError(f"{part_key}.items[{idx}].content must be an object")
            script = content.get("listening_script")
            if script is None:
                raise ValueError(
                    f"{part_key}.items[{idx}].content.listening_script is required for Listening parts"
                )
            if not isinstance(script, list):
                raise ValueError(f"{part_key}.items[{idx}].content.listening_script must be a list")

    prepare_reading_for_mock(full_parts, expected_passages=expected_reading_passages)

    audio_url_map, block_starts_per_part = build_audio_url_map(
        full_parts, audio_path_id, s3_prefix_override=None
    )
    payload = build_mock_payload(
        full_parts, title, audio_url_map, block_starts_per_part=block_starts_per_part
    )
    # Rails 向け tag / correct_choice を検証・正規化（失敗時は DB 保存前に落とす）
    rails_payload = normalize_mock_payload_for_rails(payload)
    mock_create = MockCreate.model_validate(payload)

    mock_id = create_mock_from_payload(mock_create)
    return mock_id, rails_payload


def process_mock_from_full_parts(
    *,
    full_parts: Dict[str, Dict[str, Any]],
    title: str,
    audio_path_id: str,
    expected_reading_passages: int = 5,
) -> dict:
    """full_parts から MockCreate を作成し DB に保存し, Rails 送信用 payload を outputs/ に書き出す."""
    mock_id, rails_payload = _full_parts_to_mock_id_and_rails_payload(
        full_parts=full_parts,
        title=title,
        audio_path_id=audio_path_id,
        expected_reading_passages=expected_reading_passages,
    )
    _save_rails_payload(rails_payload, f"mock_{audio_path_id}")
    post_mock_to_rails(rails_payload)
    return {"mock_id": mock_id}


def process_diagnostic_from_full_parts(
    *,
    full_parts: Dict[str, Dict[str, Any]],
    title: str,
    audio_path_id: str,
) -> dict:
    """実力診断用 full_parts から MockCreate を作成し DB に保存し, Rails 送信用 payload を outputs/ に書き出す."""
    mock_id, rails_payload = _full_parts_to_mock_id_and_rails_payload(
        full_parts=full_parts,
        title=title,
        audio_path_id=audio_path_id,
        expected_reading_passages=2,
    )
    _save_rails_payload(rails_payload, f"diagnostic_{audio_path_id}")
    post_diagnostic_to_rails(rails_payload)
    return {"mock_id": mock_id}


def process_practice_from_part_data(
    *,
    part_type: str,
    part_data: Dict[str, Any],
    audio_path_id: str,
) -> dict:
    """practice 1 パートの payload 作成と DB 保存."""
    if part_type.startswith("listening_"):
        items = part_data.get("items")
        if items is not None and not isinstance(items, list):
            raise ValueError(f"{part_type}.items must be a list")
        if isinstance(items, list):
            for idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    raise ValueError(f"{part_type}.items[{idx}] must be an object")
                content = item.get("content") or {}
                if not isinstance(content, dict):
                    raise ValueError(f"{part_type}.items[{idx}].content must be an object")
                script = content.get("listening_script")
                if script is None:
                    raise ValueError(
                        f"{part_type}.items[{idx}].content.listening_script is required for Listening parts"
                    )
                if not isinstance(script, list):
                    raise ValueError(
                        f"{part_type}.items[{idx}].content.listening_script must be a list"
                    )

    if part_type.startswith("listening_"):
        full_parts_single = {part_type: part_data}
        audio_url_map, block_starts_per_part = build_audio_url_map(
            full_parts_single, audio_path_id, s3_prefix_override=None
        )
    else:
        audio_url_map = None
        block_starts_per_part = None

    payload = build_exercise_payload(
        part_type, part_data, audio_url_map, block_starts_per_part=block_starts_per_part
    )

    if part_type.startswith("listening_"):
        qsets = payload.get("question_sets", [])
        if len(qsets) > 1:
            all_questions = []
            first_conv_audio = None
            first_scripts = None
            for qs in qsets:
                for q in qs.get("questions", []):
                    q = dict(q)
                    if first_conv_audio is None:
                        first_conv_audio = q.get("conversation_audio_url")
                    if first_scripts is None:
                        first_scripts = q.get("scripts")
                    q["display_order"] = len(all_questions) + 1
                    all_questions.append(q)
            payload["question_sets"] = [
                {
                    "display_order": 1,
                    "passage": None,
                    "conversation_audio_url": first_conv_audio,
                    "scripts": first_scripts,
                    "questions": all_questions,
                }
            ]

    rails_payload = normalize_exercise_payload_for_rails(payload)
    exercise_create = ExerciseCreate.model_validate(payload)

    _save_rails_payload(rails_payload, f"exercise_{part_type}_{audio_path_id}")
    exercise_ids = create_exercise_from_payload(exercise_create)
    post_exercise_to_rails(rails_payload)
    exercise_id = exercise_ids[0] if exercise_ids else None
    return {"exercise_ids": exercise_ids, "exercise_id": exercise_id}
