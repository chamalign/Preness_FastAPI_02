"""Generation job API: FM / SM / P 系の生成ジョブ投入と状態取得."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import verify_api_key
from app.db import get_db
from app.db.models import GenerationJob
from app.schemas.generation import GenerationJobAccepted, GenerationJobCreate, GenerationJobStatus
from app.workers.generation_tasks import (
    run_full_mock_generation,
    run_short_mock_generation,
    run_practice_generation,
)

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post(
    "/jobs",
    response_model=GenerationJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation_job(
    body: GenerationJobCreate,
    _: Any = Depends(verify_api_key),
) -> GenerationJobAccepted:
    """
    生成ジョブをキューに投入する.
    job_type: full_mock | short_mock | practice.
    practice の場合は part_type 必須 (listening_part_a, listening_part_b, listening_part_c, grammar_part_a, grammar_part_b, reading).
    """
    request_options = {"title": body.title, "job_type": body.job_type}
    if body.part_type:
        request_options["part_type"] = body.part_type

    with get_db() as session:
        job = GenerationJob(status="queued", request_options=request_options)
        session.add(job)
        session.flush()
        job_id = job.id

    if body.job_type == "full_mock":
        run_full_mock_generation.delay(title=body.title, job_id=str(job_id))
    elif body.job_type == "short_mock":
        run_short_mock_generation.delay(title=body.title or "Short Mock", job_id=str(job_id))
    else:
        run_practice_generation.delay(part_type=body.part_type, job_id=str(job_id))

    return GenerationJobAccepted(job_id=str(job_id), status="queued")


@router.get(
    "/jobs/{job_id}",
    response_model=GenerationJobStatus,
)
async def get_generation_job(
    job_id: uuid.UUID,
    _: Any = Depends(verify_api_key),
) -> GenerationJobStatus:
    """ジョブ状態と result (mock_id 等) を返す."""
    with get_db() as session:
        job = session.get(GenerationJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return GenerationJobStatus(
            job_id=str(job.id),
            status=job.status,
            result=job.result,
            error_message=job.error_message,
        )
