"""分析レポート生成: スコア計算（一般式）+ GPT（総評・強み・課題）.

Full / Short 共通ロジック. 問題数は parts_accuracy の total を合算して使うため
問題数が固定でない場合も正しく動作する.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import openai

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 一時的なエラーのみリトライ対象. 認証・モデル不正等は即座に上位へ伝播させる.
_RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)

_TAGS_DISPLAY_NAME: Dict[str, str] = {
    "shortConv": "短い会話",
    "longConv": "長い会話",
    "talk": "講義",
    "sentenceStruct": "文構造",
    "verbForm": "動詞の形",
    "modifierConnect": "修飾/接続",
    "nounPronoun": "名詞/代名詞",
    "vocab": "語彙",
    "inference": "推論",
    "fact": "事実照合",
}


def _build_gpt_ctx(
    parts_accuracy: Dict[str, Any],
    tags: Dict[str, Any],
    scores: Dict[str, Any],
    goal_score: Optional[int],
) -> str:
    """
    GPT に渡すコンテキストは「表示名のみ」に正規化する.

    - tags のキー（sentenceStruct 等）や Reading_0x の固定キーを
      レポート文章に出さないため, GPT には見せない.
    """
    tags_display: Dict[str, Any] = {}
    for k, v in (tags or {}).items():
        display = _TAGS_DISPLAY_NAME.get(k)
        if display:
            tags_display[display] = v

    reading_list = []
    reading_parts = (parts_accuracy or {}).get("reading") or {}
    for i in range(1, 6):
        rk = f"Reading_{i:02d}"
        rp = reading_parts.get(rk) or {}
        total = rp.get("total") or 0
        if total <= 0:
            continue
        theme = (rp.get("passage_theme") or "").strip()
        title = theme or f"読解パッセージ{i}"
        reading_list.append(
            {
                "title": title,
                "correct": rp.get("correct", 0),
                "total": total,
            }
        )

    parts_display = {
        "listening": (parts_accuracy or {}).get("listening") or {},
        "structure": (parts_accuracy or {}).get("structure") or {},
        "reading": reading_list,
    }

    return json.dumps(
        {
            "scores": scores,
            "goal_score": goal_score,
            "parts_accuracy": parts_display,
            "tags": tags_display,
        },
        ensure_ascii=False,
    )


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

async def _generate_narratives_with_gpt(
    parts_accuracy: Dict[str, Any],
    tags: Dict[str, Any],
    scores: Dict[str, Any],
    goal: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """GPT を使って総評・強み・課題の3段落を生成する.

    OpenAI キーの優先順: ANALYSIS_OPENAI_API_KEY → OPENAI_API_KEY
    一時エラー（レート制限・接続・タイムアウト）は最大3回リトライ.
    設定ミス系エラー（認証・モデル不正等）は即座に上位へ伝播させる.
    """
    settings = get_settings()
    api_key = settings.analysis_openai_api_key or settings.openai_api_key
    if not api_key:
        raise RuntimeError("ANALYSIS_OPENAI_API_KEY が設定されていません")

    goal_score = goal.get("target_score") if goal else None
    ctx = _build_gpt_ctx(parts_accuracy, tags, scores, goal_score)
    prompt = f"""あなたはTOEFL ITPの模試分析の専門家です.以下の模試結果を踏まえ, 受験者向けに次の3つの文章を日本語で作成してください.
- 総評（summary_closing）: スコアと目標点を踏まえた励ましと次の一手のアドバイス
- 強み（strength）: tags の正答率が高かった領域の良い点
- 課題（challenge）: tags の正答率が低い領域と具体的な学習アドバイス

注意:
- 模試結果のJSONに含まれる「表示名」だけを使い, 内部のタグ名や問題ファイル名のような記号的な文字列は本文に出さないでください.
- Reading は passage の title（テーマ）で言及し, Reading_01 のような固定キーは出さないでください.

scores の見方（正答率や100点満点ではありません）:
- listening と structure はセクション換算スコアで, おおよそのレンジは 31 から 68 です.
- reading はセクション換算スコアで, おおよそのレンジは 31 から 67 です.
- total は推定総合スコアで, おおよそのレンジは 310 から 677 です.
- max は満点の目安で 677 です.

模試結果:
{ctx}

以下のJSON形式のみで返してください.説明は不要です.
{{"summary_closing": "総評の段落", "strength": "強みの段落", "challenge": "課題の段落"}}
"""

    client = openai.AsyncOpenAI(api_key=api_key, timeout=10.0)
    last_exc: Exception = RuntimeError("no attempts made")

    for attempt in range(3):
        try:
            response = await client.responses.create(
                model="gpt-5-mini",
                input=[{"role": "user", "content": prompt}],
                reasoning={"effort": "low"},
                text={"verbosity": "low"},
                max_output_tokens=2000,
            )
            text = (response.output_text or "").strip()
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise RuntimeError(f"GPT response contained no JSON: {text[:200]!r}")
            obj = json.loads(text[start: end + 1])
            return {
                "summary_closing": obj.get("summary_closing") or "",
                "strength": obj.get("strength") or "",
                "challenge": obj.get("challenge") or "",
            }
        except _RETRYABLE_ERRORS as e:
            last_exc = e
            wait = 2 ** attempt
            logger.warning(
                "GPT narrative generation attempt %d/3 failed (retryable): %s — retrying in %ds",
                attempt + 1, e, wait,
            )
            if attempt < 2:
                await asyncio.sleep(wait)
        except Exception:
            raise

    raise last_exc


# ---------------------------------------------------------------------------
# メイン: Full / Short 共通エントリポイント
# ---------------------------------------------------------------------------

async def generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    narratives = await _generate_narratives_with_gpt(parts_accuracy, tags, scores, goal)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "scores": scores,
        "narratives": narratives,
        "report_date": report_date,
    }
