from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.mocks import Question, QuestionSet


class ExerciseCreate(BaseModel):
    section_type: str
    part_type: str
    question_sets: List[QuestionSet] = Field(..., min_length=1)


class ExerciseCreateResponse(BaseModel):
    status: str
    exercise_ids: List[int]
    created_count: int


class ExerciseListItem(BaseModel):
    """GET /exercises 一覧の1件."""
    id: int
    section_type: str
    part_type: str

