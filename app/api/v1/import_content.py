"""GPT 中間形式の手動投入: TTS→S3→DB (生成ジョブと同一パイプライン)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.security import verify_api_key
from app.schemas.exercises import ExerciseCreateResponse
from app.schemas.import_payload import FullMockImportBody, PracticeImportBody
from app.schemas.mocks import MockCreateResponse
from app.services.generation.full_mock_merger import FULL_MOCK_KEYS
from app.services.generation.import_pipeline import (
    process_mock_from_full_parts,
    process_practice_from_part_data,
)

router = APIRouter(prefix="/import", tags=["import"])


def _validation_error_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"status": "error", "errors": [message]},
    )


@router.post(
    "/full_mock",
    response_model=MockCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_full_mock(
    body: FullMockImportBody,
    _: Any = Depends(verify_api_key),
) -> MockCreateResponse | JSONResponse:
    """full_parts (生成ジョブと同形) を受け取り, Listening 音声を S3 に載せて Mock を保存."""
    audio_path_id = str(uuid.uuid4())
    fp = cast(
        Dict[str, Dict[str, Any]],
        {k: body.full_parts[k] for k in FULL_MOCK_KEYS},
    )
    try:
        out = process_mock_from_full_parts(
            full_parts=fp,
            title=body.title,
            audio_path_id=audio_path_id,
        )
    except ValueError as e:
        return _validation_error_response(str(e))
    return MockCreateResponse(
        status="success",
        mock_id=out["mock_id"],
        title=body.title,
    )


@router.post(
    "/short_mock",
    response_model=MockCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_short_mock(
    body: FullMockImportBody,
    _: Any = Depends(verify_api_key),
) -> MockCreateResponse | JSONResponse:
    """SM 用 full_parts (キーは FM と同じ 6 つ)."""
    audio_path_id = str(uuid.uuid4())
    fp = cast(
        Dict[str, Dict[str, Any]],
        {k: body.full_parts[k] for k in FULL_MOCK_KEYS},
    )
    try:
        out = process_mock_from_full_parts(
            full_parts=fp,
            title=body.title,
            audio_path_id=audio_path_id,
        )
    except ValueError as e:
        return _validation_error_response(str(e))
    return MockCreateResponse(
        status="success",
        mock_id=out["mock_id"],
        title=body.title,
    )


@router.post(
    "/practice",
    response_model=ExerciseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_practice(
    body: PracticeImportBody,
    _: Any = Depends(verify_api_key),
) -> ExerciseCreateResponse | JSONResponse:
    """P 系 1 パートの part_data (生成ジョブと同形)."""
    audio_path_id = str(uuid.uuid4())
    try:
        out = process_practice_from_part_data(
            part_type=body.part_type,
            part_data=body.part_data,
            audio_path_id=audio_path_id,
        )
    except ValueError as e:
        return _validation_error_response(str(e))
    ids = out["exercise_ids"]
    return ExerciseCreateResponse(
        status="success",
        exercise_ids=ids,
        created_count=len(ids),
    )
