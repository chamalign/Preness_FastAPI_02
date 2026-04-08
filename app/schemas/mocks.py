from typing import List, Optional

from pydantic import field_validator

from pydantic import BaseModel, Field


class ScriptTurn(BaseModel):
    speaker: str
    text: str


class Question(BaseModel):
    display_order: int
    question_text: str
    question_audio_url: Optional[str] = None
    choice_a: str
    choice_b: str
    choice_c: str
    choice_d: str
    correct_choice: str = Field(..., pattern="^[abcd]$")
    explanation: Optional[str] = None
    tag: Optional[str] = None
    scripts: Optional[List[ScriptTurn]] = None
    wrong_reason_a: Optional[str] = None
    wrong_reason_b: Optional[str] = None
    wrong_reason_c: Optional[str] = None
    wrong_reason_d: Optional[str] = None

    @field_validator("correct_choice", mode="before")
    @classmethod
    def normalize_correct_choice(cls, v: object) -> object:
        """
        モデル出力の揺れ（例: "A", "B", "b." など）を a/b/c/d に正規化する。
        """
        if isinstance(v, str):
            import re

            s = v.strip()
            # 可能性がある形式から A/B/C/D を 1 文字だけ抽出して小文字化する
            m = re.search(r"([ABCDabcd])", s)
            if m:
                return m.group(1).lower()
        return v


class QuestionSet(BaseModel):
    display_order: int
    passage: Optional[str] = None
    conversation_audio_url: Optional[str] = None
    questions: List[Question] = Field(..., min_length=1)


class Part(BaseModel):
    part_type: str
    display_order: int
    question_sets: List[QuestionSet] = Field(..., min_length=1)


class Section(BaseModel):
    section_type: str
    display_order: int
    parts: List[Part] = Field(..., min_length=1)


class MockCreate(BaseModel):
    title: str
    sections: List[Section] = Field(..., min_length=1)


class MockCreateResponse(BaseModel):
    status: str
    mock_id: int
    title: str


class MockListItem(BaseModel):
    """GET /mocks 一覧の1件."""
    id: int
    title: str

