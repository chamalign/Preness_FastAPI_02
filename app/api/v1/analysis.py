"""分析レポート API: Full / Short 共通のジョブ投入エンドポイント（同期処理）."""
import logging
import uuid
from typing import Any, Union

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.security import verify_analysis_api_key
from app.schemas.analysis import (
    AnalysisReportResponse,
    AnalysisRequest,
    ErrorResponse,
    NarrativesOut,
    ScoresOut,
    analysis_request_to_report_payload,
)
from app.services.analysis.exam_inference import infer_exam_type
from app.services.analysis.report_generator import generate_report

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/analysis/jobs",
    response_model=AnalysisReportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Report generation failed"},
    },
)
async def enqueue_analysis_job(
    payload: AnalysisRequest,
    _: Any = Depends(verify_analysis_api_key),
) -> Union[AnalysisReportResponse, JSONResponse]:
    """
    Full / Short 模試の分析レポートを同期で生成し, レスポンスとして返す.

    模試種別は ``parts_accuracy`` の問題数から自動判定する.
    スコア計算・GPT 文面生成をすべて同一リクエスト内で完結させ, 結果を直接返す.
    """
    try:
        exam_type = infer_exam_type(payload.parts_accuracy)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(errors=[str(e)]).model_dump(),
        )

    request_payload = analysis_request_to_report_payload(payload)
    job_id = uuid.uuid4()

    try:
        result = await generate_report(request_payload)
    except Exception as e:
        logger.exception("Report generation failed for job %s: %s", job_id, e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(errors=[str(e)]).model_dump(),
        )

    scores = result["scores"]
    narratives = result["narratives"]

    return AnalysisReportResponse(
        job_id=str(job_id),
        exam_type=exam_type,
        scores=ScoresOut(
            listening=scores["listening"],
            structure=scores["structure"],
            reading=scores["reading"],
            total=scores["total"],
        ),
        narratives=NarrativesOut(
            summary_closing=narratives["summary_closing"],
            strength=narratives["strength"],
            challenge=narratives["challenge"],
        ),
    )
