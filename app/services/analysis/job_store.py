"""Analysis job persistence (PostgreSQL)."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from app.db import get_db, init_db
from app.db.models import AnalysisJob


def create_job(
    attempt_id: str,
    request_payload: Dict[str, Any],
    job_type: str = "full",
) -> uuid.UUID:
    """ジョブを 1 件作成し job_id を返す. job_type: full | short."""
    init_db()
    with get_db() as session:
        job = AnalysisJob(
            attempt_id=attempt_id,
            job_type=job_type,
            status="queued",
            request_payload=request_payload,
        )
        session.add(job)
        session.flush()
        job_id = job.id
    return job_id


def get_job(job_id: uuid.UUID, include_payload: bool = False) -> Optional[Dict[str, Any]]:
    """job_id でジョブを取得. 存在しなければ None. include_payload=True で request_payload を含む (ワーカー用)."""
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            return None
        jt = getattr(job, "job_type", None) or "full"
        out = {
            "job_id": str(job.id),
            "attempt_id": job.attempt_id,
            "job_type": jt,
            "status": job.status,
            "result": job.result,
            "error_message": job.error_message,
        }
        if include_payload:
            out["request_payload"] = job.request_payload
        return out
    finally:
        session.close()


def update_job_running(job_id: uuid.UUID) -> None:
    """ジョブを running に更新 (ワーカー開始時に呼ぶ)."""
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "running"
            job.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def update_job_completed(job_id: uuid.UUID, result: Dict[str, Any]) -> None:
    """ジョブを completed にし result を保存."""
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "completed"
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def update_job_failed(job_id: uuid.UUID, error_message: str) -> None:
    """ジョブを failed にし error_message を保存."""
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()
