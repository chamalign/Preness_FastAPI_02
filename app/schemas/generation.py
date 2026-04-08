"""Generation job API 用スキーマ."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

JOB_TYPES = ("full_mock", "short_mock", "practice")
PART_TYPES = ("listening_part_a", "listening_part_b", "listening_part_c", "grammar_part_a", "grammar_part_b", "reading")


class GenerationJobCreate(BaseModel):
    """ジョブ投入リクエスト."""
    title: str = Field(..., description="Mock のタイトル (full_mock / short_mock 時). practice 時は未使用でも可.")
    job_type: Literal["full_mock", "short_mock", "practice"] = Field(
        default="full_mock",
        description="full_mock | short_mock | practice",
    )
    part_type: Optional[str] = Field(
        default=None,
        description="practice 時に必須. listening_part_a, listening_part_b, listening_part_c, grammar_part_a, grammar_part_b, reading のいずれか.",
    )

    @model_validator(mode="after")
    def part_type_required_for_practice(self):
        if self.job_type == "practice":
            if not self.part_type or self.part_type not in PART_TYPES:
                raise ValueError("job_type が practice のときは part_type を指定し、listening_part_a / listening_part_b / listening_part_c / grammar_part_a / grammar_part_b / reading のいずれかにしてください")
        return self


class GenerationJobAccepted(BaseModel):
    """ジョブ投入レスポンス (202)."""
    job_id: str = Field(..., description="ジョブ ID (UUID)")
    status: str = Field(default="queued", description="ステータス")


class GenerationJobStatus(BaseModel):
    """ジョブ状態レスポンス."""
    job_id: str = Field(..., description="ジョブ ID")
    status: str = Field(..., description="queued | running | completed | failed")
    result: Optional[dict[str, Any]] = Field(default=None, description="完了時 mock_id (FM/SM) または exercise_id (P 系)")
    error_message: Optional[str] = Field(default=None, description="失敗時のエラー")
