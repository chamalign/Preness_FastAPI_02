"""Database session for analysis jobs."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base, engine
from app.db.models import (  # noqa: F401 - ensure models are registered
    AnalysisJob,
    GenerationJob,
    Exercise,
    ExerciseQuestion,
    ExerciseQuestionSet,
    Mock,
    MockPart,
    MockQuestion,
    MockQuestionSet,
    MockSection,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a transactional scope for DB operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create tables if not exists. Add analysis_jobs.job_type for existing DBs."""
    Base.metadata.create_all(bind=engine)
    _ensure_analysis_jobs_job_type()
    _ensure_scripts_columns()


def _ensure_scripts_columns() -> None:
    """PostgreSQL: mock_questions / exercise_questions に scripts JSON カラムを追加 (idempotent)."""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            for table in ("mock_questions", "exercise_questions"):
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS scripts JSON"
                    )
                )
            conn.commit()
    except Exception:
        pass


def _ensure_analysis_jobs_job_type() -> None:
    """PostgreSQL: add job_type column if missing (idempotent)."""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(
                text(
                    "ALTER TABLE analysis_jobs ADD COLUMN IF NOT EXISTS job_type "
                    "VARCHAR(16) NOT NULL DEFAULT 'full'"
                )
            )
            conn.commit()
    except Exception:
        pass
