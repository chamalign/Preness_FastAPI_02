"""分析レポート API: Full / Short 共通のジョブ投入エンドポイント（同期処理）."""
import logging
from typing import Any, Union

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.security import verify_analysis_api_key
from app.schemas.analysis import (
    AnalysisJobCompleted,
    AnalysisRequest,
    ErrorResponse,
    analysis_request_to_report_payload,
)
from app.services.analysis.exam_inference import infer_exam_type
from app.services.analysis.job_store import (
    create_job,
    update_job_completed,
    update_job_failed,
    update_job_running,
)
from app.services.analysis.report_generator import generate_report
from app.services.rails_client import RailsPostError, post_analysis_report_to_rails

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analysis/jobs",
    response_model=AnalysisJobCompleted,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Report generation failed"},
    },
)
async def enqueue_analysis_job(
    payload: AnalysisRequest,
    _: Any = Depends(verify_analysis_api_key),
) -> Union[AnalysisJobCompleted, JSONResponse]:
    """
    Full / Short 模試の分析レポートを同期で生成し, Rails に POST する.

    模試種別は ``parts_accuracy`` の問題数から自動判定する.
    スコア計算・GPT 文面生成・Rails への POST をすべて同一リクエスト内で完結させる.
    """
    try:
        exam_type = infer_exam_type(payload.parts_accuracy)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(errors=[str(e)]).model_dump(),
        )

    request_payload = analysis_request_to_report_payload(payload)
    job_id = create_job(
        request_payload=request_payload,
        job_type=exam_type,
    )

    update_job_running(job_id)

    try:
        result = generate_report(request_payload)
        update_job_completed(job_id, result)
    except Exception as e:
        logger.exception("Report generation failed for job %s: %s", job_id, e)
        update_job_failed(job_id, str(e))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(errors=[str(e)]).model_dump(),
        )

    try:
        post_analysis_report_to_rails(
            job_id=str(job_id),
            exam_type=exam_type,
            scores=result["scores"],
            narratives=result["narratives"],
        )
    except RailsPostError as e:
        logger.warning("Rails POST failed for job %s: %s", job_id, e)

    return AnalysisJobCompleted(
        job_id=str(job_id),
        job_type=exam_type,
        status="completed",
    )
