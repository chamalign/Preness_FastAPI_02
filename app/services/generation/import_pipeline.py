"""GPT 中間形式 (full_parts / part_data) から TTS→S3→MockCreate/ExerciseCreate 保存まで."""

from __future__ import annotations

from typing import Any, Dict

from app.schemas.exercises import ExerciseCreate
from app.schemas.mocks import MockCreate
from app.services.exercise_service import create_exercise_from_payload
from app.services.mock_service import create_mock_from_payload
from app.services.rails_client import post_exercise_to_rails, post_mock_to_rails
from app.services.rails_payload_normalize import (
    normalize_exercise_payload_for_rails,
    normalize_mock_payload_for_rails,
)
from app.services.generation.audio_upload import build_audio_url_map
from app.services.generation.payload_builder import build_exercise_payload, build_mock_payload


def process_mock_from_full_parts(
    *,
    full_parts: Dict[str, Dict[str, Any]],
    title: str,
    audio_path_id: str,
) -> dict:
    """full_parts から MockCreate を作成し DB に保存する."""
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
    post_mock_to_rails(rails_payload)
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
    rails_payload = normalize_exercise_payload_for_rails(payload)
    exercise_create = ExerciseCreate.model_validate(payload)

    exercise_ids = create_exercise_from_payload(exercise_create)
    post_exercise_to_rails(rails_payload)
    exercise_id = exercise_ids[0] if exercise_ids else None
    return {"exercise_ids": exercise_ids, "exercise_id": exercise_id}
