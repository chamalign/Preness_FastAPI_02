"""Analysis report API schemas (request, response, result)."""
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ----- Request (POST /api/v1/analysis/jobs) -----


class AnswerItem(BaseModel):
    """1問分の回答 (Rails の answers と対応)."""
    question_id: str = Field(..., description="Rails question.id を文字列で (item_id と同一)")
    selected_choice: Optional[str] = Field(None, description="A|B|C|D または skip 時は null")
    skipped: bool = Field(default=False)


class AnalysisItemMeta(BaseModel):
    """1問分のメタデータ (section, part, tag, 正解)."""
    item_id: str = Field(..., description="question_id と同一に揃える")
    question_id: str = Field(..., description="Rails question.id を文字列で")
    section_id: Optional[str] = Field(None, description="L|S|R など")
    section_type: Optional[str] = Field(None, description="listening|structure|reading")
    part: Optional[str] = Field(None, description="Part_A, Part_B, passages など")
    tag: str = Field(
        ...,
        min_length=1,
        description="必須. Listening Part 別・文法カテゴリ・Reading タイプ別正答率の算出キー",
    )
    correct_choice: str = Field(..., pattern="^[ABCD]$")


class AnalysisJobCreate(BaseModel):
    """分析ジョブ投入リクエスト."""
    attempt_id: str = Field(..., description="Rails の attempt.id など一意キー")
    exam_type: str = Field(default="full", description="short | full")
    student_name: Optional[str] = Field(None, description="レポート表示用")
    exam_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    answers: List[AnswerItem] = Field(..., min_length=1)
    items: List[AnalysisItemMeta] = Field(..., min_length=1)


# ----- Response: POST (202) -----


class AnalysisJobEnqueued(BaseModel):
    """ジョブ投入成功."""
    job_id: str
    job_type: str = "full"
    status: str = "queued"


# ----- Short mock: POST /api/v1/analysis/short/jobs -----


class ShortPassageIn(BaseModel):
    """Reading パッセージ 1 件. theme は表示用, question_ids は 1 問以上."""
    theme: str = Field(..., min_length=1)
    question_ids: List[str] = Field(..., min_length=1)


class ShortAnalysisJobCreate(BaseModel):
    """
    Short 模試分析. 各 item に tag 必須. L/S/R それぞれ1問以上.
    passages の各 question_id は Reading 設問かつ passages 間で重複なし.
    """
    attempt_id: str = Field(..., description="Rails attempt.id など")
    student_name: Optional[str] = None
    exam_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    goal_score: Optional[int] = Field(None, description="目標点, null 可")
    answers: List[AnswerItem] = Field(..., min_length=1)
    items: List[AnalysisItemMeta] = Field(..., min_length=1)
    passages: List[ShortPassageIn] = Field(..., min_length=1)


# ----- Response: GET (200) -----


class AnalysisResultMeta(BaseModel):
    """レポート meta."""
    title: str = "TOEFL ITP®︎ 模試分析レポート"
    student_name: Optional[str] = None
    exam_date: Optional[str] = None
    exam_type: Optional[str] = None
    report_date: Optional[str] = None


class AnalysisResultScores(BaseModel):
    """レポート scores."""
    total: int = 0
    max: int = 677
    listening: Optional[int] = None
    structure: Optional[int] = None
    reading: Optional[int] = None
    structure_part_score: Optional[int] = None
    written_expr_score: Optional[int] = None


class AnalysisResultNarratives(BaseModel):
    """総評・強み・課題 (GPT 生成)."""
    summary_closing: Optional[str] = None
    strength: Optional[str] = None
    challenge: Optional[str] = None


class AnalysisResult(BaseModel):
    """分析レポート結果. tag 別正答率は tag_accuracy (旧 part_accuracy は読み取り互換)."""
    meta: AnalysisResultMeta
    scores: AnalysisResultScores
    tag_accuracy: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    narratives: AnalysisResultNarratives

    @model_validator(mode="before")
    @classmethod
    def _legacy_part_accuracy(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("tag_accuracy") and data.get(
            "part_accuracy"
        ):
            data = {**data, "tag_accuracy": data["part_accuracy"]}
        return data


class AnalysisShortPassageOut(BaseModel):
    theme: str
    score: int
    max: int


class AnalysisShortNarratives(BaseModel):
    summary_bullets: List[str] = Field(default_factory=list)
    summary_closing: Optional[str] = None
    strength: Optional[str] = None
    challenge: Optional[str] = None


class AnalysisShortResultMeta(BaseModel):
    title: str = "TOEFL ITP®︎ 模試分析レポート (Short)"
    student_name: Optional[str] = None
    exam_date: Optional[str] = None
    exam_type: str = "short"
    report_date: Optional[str] = None
    goal_score: Optional[int] = None
    community_threshold: int = 550


class AnalysisShortResult(BaseModel):
    """Short 模試の result. tag_accuracy が正, latest は tag フラット互換."""
    meta: AnalysisShortResultMeta
    scores: AnalysisResultScores
    tag_accuracy: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    latest: Dict[str, int] = Field(default_factory=dict)
    passages: List[AnalysisShortPassageOut]
    narratives: AnalysisShortNarratives

    @model_validator(mode="before")
    @classmethod
    def _legacy_latest_only(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("tag_accuracy") and data.get(
            "latest"
        ):
            la = data["latest"]
            if isinstance(la, dict):
                data = {
                    **data,
                    "tag_accuracy": {
                        "listening": {},
                        "grammar": {},
                        "reading": {},
                    },
                }
        return data


class AnalysisJobStatus(BaseModel):
    """ジョブ状態取得レスポンス. job_type で result の形が異なる."""
    job_id: str
    job_type: Literal["full", "short"] = "full"
    status: str  # queued | running | completed | failed
    result: Optional[Union[AnalysisResult, AnalysisShortResult]] = None
    error_message: Optional[str] = None


# ----- Error (問題投入 API と同じ形式) -----


class ErrorResponse(BaseModel):
    """422 / 404 等."""
    status: str = "error"
    errors: List[str]
