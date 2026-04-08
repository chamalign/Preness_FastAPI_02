"""手動投入: GPT 中間形式 (full_parts / part_data) のリクエストボディ."""

from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator

from app.schemas.generation import PART_TYPES
from app.services.generation.full_mock_merger import FULL_MOCK_KEYS


class FullMockImportBody(BaseModel):
    """FM/SM 共通: 6 パート分の full_parts とタイトル."""

    title: str
    full_parts: Dict[str, Any] = Field(..., description="listening_part_a ～ reading の 6 キー")

    @model_validator(mode="after")
    def full_parts_shape(self) -> "FullMockImportBody":
        missing = [k for k in FULL_MOCK_KEYS if k not in self.full_parts]
        if missing:
            raise ValueError(
                "full_parts に次のキーが必要です: "
                + ", ".join(FULL_MOCK_KEYS)
                + f" (不足: {', '.join(missing)})"
            )
        for k in FULL_MOCK_KEYS:
            v = self.full_parts[k]
            if not isinstance(v, dict):
                raise ValueError(f"full_parts[{k}] はオブジェクトである必要があります")
        return self


class PracticeImportBody(BaseModel):
    """P 系 1 パート."""

    part_type: str = Field(..., description="listening_part_a 等")
    part_data: Dict[str, Any]

    @model_validator(mode="after")
    def part_type_valid(self) -> "PracticeImportBody":
        if self.part_type not in PART_TYPES:
            raise ValueError(
                f"part_type は次のいずれかにしてください: {', '.join(PART_TYPES)}"
            )
        return self
