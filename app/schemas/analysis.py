"""分析レポート API schemas (request, response)."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----- Request: POST /api/v1/analysis/jobs -----


class PartStat(BaseModel):
    """パート別の正答数・問題数."""
    model_config = ConfigDict(extra="forbid")

    correct: int
    total: int


class ReadingPassageStat(BaseModel):
    """Reading パッセージ別の正答数・問題数."""
    model_config = ConfigDict(extra="forbid")

    passage_theme: Optional[str] = None
    correct: int
    total: int


def _unused_reading_passage_stat() -> ReadingPassageStat:
    """short 模試で Reading_03〜05 を省略したときに補完する未実施パッセージ."""
    return ReadingPassageStat(correct=0, total=0)


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
    """Reading: Reading_01 / Reading_02 は必須. Reading_03〜05 は省略 or null 時は未実施 (0 問) とみなす."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    reading_01: ReadingPassageStat = Field(alias="Reading_01")
    reading_02: ReadingPassageStat = Field(alias="Reading_02")
    reading_03: ReadingPassageStat = Field(
        default_factory=_unused_reading_passage_stat,
        alias="Reading_03",
    )
    reading_04: ReadingPassageStat = Field(
        default_factory=_unused_reading_passage_stat,
        alias="Reading_04",
    )
    reading_05: ReadingPassageStat = Field(
        default_factory=_unused_reading_passage_stat,
        alias="Reading_05",
    )

    @field_validator("reading_03", "reading_04", "reading_05", mode="before")
    @classmethod
    def _coerce_null_to_unused(cls, v: Any) -> Any:
        """Rails が null を明示送信した場合でも未実施パッセージ扱いにする."""
        if v is None:
            return {"correct": 0, "total": 0}
        return v


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


class ScoresOut(BaseModel):
    """セクション換算スコア（レスポンス用）."""
    listening: int
    structure: int
    reading: int
    total: int


class NarrativesOut(BaseModel):
    """GPT 生成ナラティブ（レスポンス用）."""
    summary_closing: str
    strength: str
    challenge: str


class AnalysisReportResponse(BaseModel):
    """POST /api/v1/analysis/jobs 成功時のレスポンス."""
    job_id: str
    exam_type: str
    scores: ScoresOut
    narratives: NarrativesOut


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