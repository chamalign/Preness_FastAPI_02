"""分析レポート生成: スコア計算（一般式）+ GPT（総評・強み・課題）.

Full / Short 共通ロジック. 問題数は parts_accuracy の total を合算して使うため
問題数が固定でない場合も正しく動作する.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# スコア計算（一般式 + クランプ）
# ---------------------------------------------------------------------------

def _calc_section_score(correct: int, total: int, ss_min: int, ss_max: int) -> int:
    """
    セクションスコアの一般式.

    chance = total × 0.25
    SS = clamp(
        ((ss_max - ss_min) / (total - chance)) × (correct - chance) + ss_min,
        ss_min, ss_max
    )

    total == 0 や total == chance（total が 0 に近い）の場合は ss_min を返す.
    """
    if total <= 0:
        return ss_min
    chance = total * 0.25
    denominator = total - chance
    if denominator <= 0:
        return ss_min
    raw = (ss_max - ss_min) / denominator * (correct - chance) + ss_min
    return max(ss_min, min(ss_max, round(raw)))


def calculate_scores(parts_accuracy: Dict[str, Any]) -> Dict[str, Any]:
    """
    parts_accuracy（listening / structure / reading の各パート集計）から
    セクション換算スコア・トータルスコアを計算する.

    Full / Short どちらも同じ関数で処理できる（問題数は total を合算）.

    Returns:
        {listening, structure, reading, total, max}
    """
    listening_parts = parts_accuracy.get("listening", {})
    structure_parts = parts_accuracy.get("structure", {})
    reading_parts = parts_accuracy.get("reading", {})

    l_correct = sum(p.get("correct", 0) for p in listening_parts.values())
    l_total = sum(p.get("total", 0) for p in listening_parts.values())

    s_correct = sum(p.get("correct", 0) for p in structure_parts.values())
    s_total = sum(p.get("total", 0) for p in structure_parts.values())

    r_correct = sum(p.get("correct", 0) for p in reading_parts.values())
    r_total = sum(p.get("total", 0) for p in reading_parts.values())

    ss_l = _calc_section_score(l_correct, l_total, ss_min=31, ss_max=68)
    ss_s = _calc_section_score(s_correct, s_total, ss_min=31, ss_max=68)
    ss_r = _calc_section_score(r_correct, r_total, ss_min=31, ss_max=67)

    total = max(310, min(677, round((10 / 3) * (ss_l + ss_s + ss_r))))

    return {
        "listening": ss_l,
        "structure": ss_s,
        "reading": ss_r,
        "total": total,
        "max": 677,
    }


# ---------------------------------------------------------------------------
# GPT ナラティブ生成（総評・強み・課題）
# ---------------------------------------------------------------------------

def _generate_narratives_with_gpt(
    parts_accuracy: Dict[str, Any],
    tags: Dict[str, Any],
    scores: Dict[str, Any],
    goal: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """
    GPT を使って総評・強み・課題の3段落を生成する.

    OpenAI キーの優先順:
      ANALYSIS_OPENAI_API_KEY → ANALYSIS_API_KEY → OPENAI_API_KEY
    """
    settings = get_settings()
    api_key = (
        settings.analysis_openai_api_key
        or settings.analysis_api_key
        or settings.openai_api_key
    )
    if not api_key:
        return {
            "summary_closing": "（総評は API キー設定後に生成されます）",
            "strength": "（強みは API キー設定後に生成されます）",
            "challenge": "（課題は API キー設定後に生成されます）",
        }

    goal_score = goal.get("target_score") if goal else None
    ctx = json.dumps(
        {
            "scores": scores,
            "goal_score": goal_score,
            "parts_accuracy": parts_accuracy,
            "tags": tags,
        },
        ensure_ascii=False,
    )
    prompt = f"""あなたはTOEFL ITPの模試分析の専門家です。以下の模試結果を踏まえ、受験者向けに次の3つの文章を日本語で作成してください。
- 総評（summary_closing）: スコアと目標点を踏まえた励ましと次の一手のアドバイス
- 強み（strength）: tags の正答率が高かった領域の良い点
- 課題（challenge）: tags の正答率が低い領域と具体的な学習アドバイス

tags のキーは問題タイプ（shortConv, longConv, talk, sentenceStruct, verbForm, modifierConnect, nounPronoun, vocab, inference, fact 等）です。

模試結果:
{ctx}

以下のJSON形式のみで返してください。説明は不要です。
{{"summary_closing": "総評の段落", "strength": "強みの段落", "challenge": "課題の段落"}}
"""
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": prompt}],
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=1200,
        )
        text = (response.output_text or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(text[start: end + 1])
            return {
                "summary_closing": obj.get("summary_closing") or "",
                "strength": obj.get("strength") or "",
                "challenge": obj.get("challenge") or "",
            }
    except Exception as e:
        logger.warning("GPT narrative generation failed: %s", e)

    return {
        "summary_closing": "（総評の生成でエラーが発生しました）",
        "strength": "（強みの生成でエラーが発生しました）",
        "challenge": "（課題の生成でエラーが発生しました）",
    }


# ---------------------------------------------------------------------------
# メイン: Full / Short 共通エントリポイント
# ---------------------------------------------------------------------------

def generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: goal（任意）, parts_accuracy, tags

    Full / Short 両方をこの関数で処理する（問題数は parts_accuracy の total から計算）.
    Returns: {scores, narratives, report_date}
    """
    parts_accuracy = payload.get("parts_accuracy") or {}
    tags = payload.get("tags") or {}
    goal = payload.get("goal")

    if not parts_accuracy:
        raise ValueError("parts_accuracy must not be empty")

    scores = calculate_scores(parts_accuracy)
    narratives = _generate_narratives_with_gpt(parts_accuracy, tags, scores, goal)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "scores": scores,
        "narratives": narratives,
        "report_date": report_date,
    }
