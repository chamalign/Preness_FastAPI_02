"""Celery task: 分析レポート生成を非同期実行."""
import logging
import uuid

from app.db import init_db
from app.services.analysis.job_store import (
    get_job,
    update_job_completed,
    update_job_failed,
    update_job_running,
)
from app.services.analysis.report_generator import generate_report
from app.services.analysis.report_generator_short import generate_short_report
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def run_analysis_report(self, job_id: str) -> None:
    """
    job_id のジョブを実行: request_payload でレポート生成し DB を更新する.
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        logger.error("Invalid job_id: %s", job_id)
        return
    init_db()
    job = get_job(uid, include_payload=True)
    if not job:
        logger.error("Job not found: %s", job_id)
        return
    update_job_running(uid)
    payload = job.get("request_payload")
    if not payload:
        update_job_failed(uid, "Request payload not found")
        return
    try:
        jt = job.get("job_type") or "full"
        if jt == "short":
            result = generate_short_report(payload)
        else:
            result = generate_report(payload)
        update_job_completed(uid, result)
    except Exception as e:
        logger.exception("Report generation failed for job %s: %s", job_id, e)
        update_job_failed(uid, str(e))
