"""分析レポート API: Full / Short ジョブ投入・状態取得."""
from typing import Any, Optional, Union
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import verify_analysis_api_key
from app.schemas.analysis import (
    AnalysisJobCreate,
    AnalysisJobEnqueued,
    AnalysisJobStatus,
    AnalysisResult,
    AnalysisShortResult,
    ErrorResponse,
    ShortAnalysisJobCreate,
)
from app.services.analysis.job_store import create_job, get_job
from app.workers.analysis_tasks import run_analysis_report

router = APIRouter()


def _parse_job_result(
    job_type: str,
    raw: Optional[dict],
) -> Optional[Union[AnalysisResult, AnalysisShortResult]]:
    if not raw:
        return None
    if job_type == "short":
        return AnalysisShortResult(**raw)
    return AnalysisResult(**raw)


@router.post(
    "/analysis/jobs",
    response_model=AnalysisJobEnqueued,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def enqueue_analysis_job(
    payload: AnalysisJobCreate,
    _: Any = Depends(verify_analysis_api_key),
) -> AnalysisJobEnqueued:
    """
    Full 模試の分析レポート生成ジョブを 1 件投入する.
    """
    request_payload = payload.model_dump()
    job_id = create_job(
        attempt_id=payload.attempt_id,
        request_payload=request_payload,
        job_type="full",
    )
    run_analysis_report.delay(str(job_id))
    return AnalysisJobEnqueued(job_id=str(job_id), job_type="full", status="queued")


@router.post(
    "/analysis/short/jobs",
    response_model=AnalysisJobEnqueued,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def enqueue_short_analysis_job(
    payload: ShortAnalysisJobCreate,
    _: Any = Depends(verify_analysis_api_key),
) -> AnalysisJobEnqueued:
    """Short 模試の分析レポートジョブを 1 件投入する (85 問 + passages 2×10)."""
    request_payload = payload.model_dump()
    job_id = create_job(
        attempt_id=payload.attempt_id,
        request_payload=request_payload,
        job_type="short",
    )
    run_analysis_report.delay(str(job_id))
    return AnalysisJobEnqueued(job_id=str(job_id), job_type="short", status="queued")


@router.get(
    "/analysis/jobs/{job_id}",
    response_model=AnalysisJobStatus,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_analysis_job_status(
    job_id: str,
    _: Any = Depends(verify_analysis_api_key),
) -> AnalysisJobStatus:
    """ジョブの状態と結果を取得. job_type が short のとき result は Short スキーマ."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "errors": ["Job not found"]},
        )
    job = get_job(uid)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "errors": ["Job not found"]},
        )
    jt = job.get("job_type") or "full"
    if jt not in ("full", "short"):
        jt = "full"
    result = _parse_job_result(jt, job.get("result"))
    return AnalysisJobStatus(
        job_id=job["job_id"],
        job_type=jt,
        status=job["status"],
        result=result,
        error_message=job.get("error_message"),
    )
