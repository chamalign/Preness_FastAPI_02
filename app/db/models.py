"""Analysis job and content (mock/exercise) models."""
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisJob(Base):
    """1件の分析レポート生成ジョブ."""

    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    attempt_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GenerationJob(Base):
    """1件の Full Mock 生成ジョブ (任意)."""

    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    request_options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ----- Mock (模擬試験) -----


class Mock(Base):
    __tablename__ = "mocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    sections: Mapped[List["MockSection"]] = relationship(
        "MockSection", back_populates="mock", order_by="MockSection.display_order", cascade="all, delete-orphan"
    )


class MockSection(Base):
    __tablename__ = "mock_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mock_id: Mapped[int] = mapped_column(Integer, ForeignKey("mocks.id", ondelete="CASCADE"), nullable=False)
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    mock: Mapped["Mock"] = relationship("Mock", back_populates="sections")
    parts: Mapped[List["MockPart"]] = relationship(
        "MockPart", back_populates="section", order_by="MockPart.display_order", cascade="all, delete-orphan"
    )


class MockPart(Base):
    __tablename__ = "mock_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mock_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mock_sections.id", ondelete="CASCADE"), nullable=False
    )
    part_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped["MockSection"] = relationship("MockSection", back_populates="parts")
    question_sets: Mapped[List["MockQuestionSet"]] = relationship(
        "MockQuestionSet",
        back_populates="part",
        order_by="MockQuestionSet.display_order",
        cascade="all, delete-orphan",
    )


class MockQuestionSet(Base):
    __tablename__ = "mock_question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mock_part_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mock_parts.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    passage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    part: Mapped["MockPart"] = relationship("MockPart", back_populates="question_sets")
    questions: Mapped[List["MockQuestion"]] = relationship(
        "MockQuestion",
        back_populates="question_set",
        order_by="MockQuestion.display_order",
        cascade="all, delete-orphan",
    )


class MockQuestion(Base):
    __tablename__ = "mock_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mock_question_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mock_question_sets.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    choice_a: Mapped[str] = mapped_column(Text, nullable=False)
    choice_b: Mapped[str] = mapped_column(Text, nullable=False)
    choice_c: Mapped[str] = mapped_column(Text, nullable=False)
    choice_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_choice: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    wrong_reason_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_c: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_d: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scripts: Mapped[Optional[List[Any]]] = mapped_column(JSON, nullable=True)
    question_set: Mapped["MockQuestionSet"] = relationship("MockQuestionSet", back_populates="questions")


# ----- Exercise (セクション別演習) -----


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    part_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    question_sets: Mapped[List["ExerciseQuestionSet"]] = relationship(
        "ExerciseQuestionSet",
        back_populates="exercise",
        order_by="ExerciseQuestionSet.display_order",
        cascade="all, delete-orphan",
    )


class ExerciseQuestionSet(Base):
    __tablename__ = "exercise_question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    passage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    exercise: Mapped["Exercise"] = relationship("Exercise", back_populates="question_sets")
    questions: Mapped[List["ExerciseQuestion"]] = relationship(
        "ExerciseQuestion",
        back_populates="question_set",
        order_by="ExerciseQuestion.display_order",
        cascade="all, delete-orphan",
    )


class ExerciseQuestion(Base):
    __tablename__ = "exercise_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exercise_question_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercise_question_sets.id", ondelete="CASCADE"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    choice_a: Mapped[str] = mapped_column(Text, nullable=False)
    choice_b: Mapped[str] = mapped_column(Text, nullable=False)
    choice_c: Mapped[str] = mapped_column(Text, nullable=False)
    choice_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_choice: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    wrong_reason_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_c: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wrong_reason_d: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scripts: Mapped[Optional[List[Any]]] = mapped_column(JSON, nullable=True)
    question_set: Mapped["ExerciseQuestionSet"] = relationship(
        "ExerciseQuestionSet", back_populates="questions"
    )
