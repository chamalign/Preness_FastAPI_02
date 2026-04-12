"""分析レポート API schemas (request, response)."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ----- Request: POST /api/v1/analysis/jobs -----


class PartStat(BaseModel):
    """パート別の正答数・問題数."""
    model_config = ConfigDict(extra="forbid")

    correct: int
    total: int


class ReadingPassageStat(BaseModel):
    """Reading パッセージ別の正答数・問題数."""
    model_config = ConfigDict(extra="forbid")

    passage_thema: Optional[str] = None
    correct: int
    total: int


class ListeningPartsAccuracy(BaseModel):
    """Listening: partA / partB / partC 固定."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    part_a: PartStat = Field(alias="partA")
    part_b: PartStat = Field(alias="partB")
    part_c: PartStat = Field(alias="partC")


class StructurePartsAccuracy(BaseModel):
    """Structure: partA / partB 固定."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    part_a: PartStat = Field(alias="partA")
    part_b: PartStat = Field(alias="partB")


class ReadingPartsAccuracy(BaseModel):
    """Reading: Reading_01 〜 Reading_05 固定."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reading_01: ReadingPassageStat = Field(alias="Reading_01")
    reading_02: ReadingPassageStat = Field(alias="Reading_02")
    reading_03: ReadingPassageStat = Field(alias="Reading_03")
    reading_04: ReadingPassageStat = Field(alias="Reading_04")
    reading_05: ReadingPassageStat = Field(alias="Reading_05")


class PartsAccuracy(BaseModel):
    """セクション×パート別の正答集計（キー固定）."""
    model_config = ConfigDict(extra="forbid")

    listening: ListeningPartsAccuracy
    structure: StructurePartsAccuracy
    reading: ReadingPartsAccuracy


class TagsAccuracy(BaseModel):
    """タグ別正答集計（キー固定）."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    short_conv: PartStat = Field(alias="shortConv")
    long_conv: PartStat = Field(alias="longConv")
    talk: PartStat
    sentence_struct: PartStat = Field(alias="sentenceStruct")
    verb_form: PartStat = Field(alias="verbForm")
    modifier_connect: PartStat = Field(alias="modifierConnect")
    noun_pronoun: PartStat = Field(alias="nounPronoun")
    vocab: PartStat
    inference: PartStat
    fact: PartStat


class Goal(BaseModel):
    """目標スコア."""
    model_config = ConfigDict(extra="forbid")

    target_score: int


class AnalysisRequest(BaseModel):
    """
    Full / Short 共通の分析ジョブ投入リクエスト.

    模試種別は ``parts_accuracy`` の問題数シグネチャから自動判定する（本文に exam_type は含めない）.
    """
    model_config = ConfigDict(extra="forbid")

    goal: Optional[Goal] = Field(
        default=None,
        description="目標スコア（任意）",
    )
    parts_accuracy: PartsAccuracy
    tags: TagsAccuracy


# ----- Response -----


class AnalysisJobEnqueued(BaseModel):
    """ジョブ投入成功（非同期用・予備）."""
    job_id: str
    job_type: str = "full"
    status: str = "queued"


class AnalysisJobCompleted(BaseModel):
    """同期処理完了."""
    job_id: str
    job_type: str
    status: str = "completed"


# ----- Error -----


class ErrorResponse(BaseModel):
    """422 / 401 等."""
    status: str = "error"
    errors: List[str]


def analysis_request_to_report_payload(req: AnalysisRequest) -> Dict[str, Any]:
    """generate_report / DB 保存用の従来形 dict に変換する."""
    goal: Optional[Dict[str, int]] = None
    if req.goal is not None:
        goal = req.goal.model_dump()
    return {
        "goal": goal,
        "parts_accuracy": req.parts_accuracy.model_dump(by_alias=True),
        "tags": req.tags.model_dump(by_alias=True),
    }