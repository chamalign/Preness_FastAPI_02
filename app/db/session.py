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
    Base.metadata.create_all(bind=engine)
    _ensure_analysis_jobs_job_type()
    _ensure_scripts_columns()
    _ensure_conversation_audio_url_columns()
    _ensure_scripts_on_question_sets()
    _ensure_passage_theme_on_question_sets()


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


def _ensure_conversation_audio_url_columns() -> None:
    """PostgreSQL: mock_questions / exercise_questions に conversation_audio_url カラムを追加 (idempotent)."""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            for table in ("mock_questions", "exercise_questions"):
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS conversation_audio_url VARCHAR(2048)"
                    )
                )
            conn.commit()
    except Exception:
        pass


def _ensure_scripts_on_question_sets() -> None:
    """PostgreSQL: mock_question_sets / exercise_question_sets に scripts JSON カラムを追加 (idempotent)."""
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            for table in ("mock_question_sets", "exercise_question_sets"):
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS scripts JSON"
                    )
                )
            conn.commit()
    except Exception:
        pass


def _ensure_passage_theme_on_question_sets() -> None:
    """
    mock_question_sets / exercise_question_sets に passage_theme を用意する (idempotent).

    既存DBに旧カラム名のみある場合は PostgreSQL で RENAME する.
    """
    try:
        from sqlalchemy import text

        dialect = engine.dialect.name
        with engine.connect() as conn:
            for table in ("mock_question_sets", "exercise_question_sets"):
                if dialect == "postgresql":
                    conn.execute(
                        text(
                            f"""
                            DO $body$
                            BEGIN
                              IF EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = '{table}'
                                  AND column_name = 'passage_thema'
                              ) AND NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = '{table}'
                                  AND column_name = 'passage_theme'
                              ) THEN
                                ALTER TABLE {table} RENAME COLUMN passage_thema TO passage_theme;
                              ELSIF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = '{table}'
                                  AND column_name = 'passage_theme'
                              ) THEN
                                ALTER TABLE {table} ADD COLUMN passage_theme VARCHAR(512);
                              END IF;
                            END
                            $body$;
                            """
                        )
                    )
                else:
                    try:
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} RENAME COLUMN passage_thema TO passage_theme"
                            )
                        )
                    except Exception:
                        pass
                    try:
                        conn.execute(
                            text(
                                f"ALTER TABLE {table} ADD COLUMN passage_theme VARCHAR(512)"
                            )
                        )
                    except Exception:
                        pass
            conn.commit()
    except Exception:
        pass


def _ensure_analysis_jobs_job_type() -> None:
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
