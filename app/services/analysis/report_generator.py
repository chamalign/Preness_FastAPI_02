"""分析レポート生成: tag 別正答率 + 採点 + GPT (総評・強み・課題)."""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _raw_to_scaled_section(raw: int, total: int) -> int:
    if total <= 0:
        return 31
    pct = raw / total
    return min(68, max(31, int(31 + (68 - 31) * pct)))


def _build_answers_map(answers: List[Dict[str, Any]]) -> Dict[str, str]:
    """answers 配列を item_id -> "A"|"B"|"C"|"D" の辞書に."""
    out: Dict[str, str] = {}
    for a in answers:
        qid = (a.get("question_id") or "").strip()
        if not qid:
            continue
        choice = a.get("selected_choice")
        if choice and isinstance(choice, str) and choice.strip().upper() in ("A", "B", "C", "D"):
            out[qid] = choice.strip().upper()
    return out


def _normalize_section_id(section_id: str, section_type: str) -> str:
    s = (section_id or section_type or "").strip().upper()
    if s in ("L", "S", "R"):
        return s
    m = {"LISTENING": "L", "STRUCTURE": "S", "READING": "R"}
    return m.get(s, s[:1] if s else "")


def _run_scoring(
    items: List[Dict[str, Any]],
    answers: Dict[str, str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    採点: セクション合計 + tag 別集計 (Listening / 文法 / Reading の内訳は tag 必須).
    """
    per_item: List[Dict[str, Any]] = []
    sections: Dict[str, Dict[str, Any]] = {}

    for it in items:
        item_id = (it.get("item_id") or it.get("question_id") or "").strip()
        if not item_id:
            continue
        tag = (it.get("tag") or "").strip()
        if not tag:
            raise ValueError(
                "items[].tag は分析レポートに必須です (Listening Part 別・文法カテゴリ別・Reading タイプ別の算出に使用). "
                f"question_id={item_id}"
            )
        correct_choice = (it.get("correct_choice") or it.get("correct_option") or "").strip().upper()
        section_id = _normalize_section_id(
            it.get("section_id") or "",
            it.get("section_type") or "",
        )
        part = (it.get("part") or "").strip()

        user_choice = answers.get(item_id)
        if not user_choice:
            status = "unanswered"
        elif user_choice not in ("A", "B", "C", "D"):
            status = "invalid"
        elif user_choice == correct_choice:
            status = "correct"
        else:
            status = "incorrect"

        per_item.append({
            "item_id": item_id,
            "status": status,
            "section_id": section_id,
            "part": part,
            "tag": tag,
        })

        if not section_id:
            raise ValueError(
                f"section_id / section_type が無い設問があります. question_id={item_id}"
            )
        if section_id not in sections:
            sections[section_id] = {
                "section_id": section_id,
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
                "invalid": 0,
                "by_tag": {},
            }
        sec = sections[section_id]
        if status in ("correct", "incorrect", "unanswered", "invalid"):
            sec[status] += 1
        if tag not in sec["by_tag"]:
            sec["by_tag"][tag] = {
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
                "invalid": 0,
            }
        sec["by_tag"][tag][status] += 1

    return sections, per_item


def _sections_to_scores_and_tag_accuracy(
    sections: Dict[str, Any],
    total_correct: int,
    total_questions: int,
) -> tuple[Dict[str, Any], Dict[str, Dict[str, int]]]:
    """セクション換算スコア + tag 別正答率 % (listening / grammar / reading)."""
    listening = structure = reading = 0
    structure_part_score = written_expr_score = 0
    tag_accuracy: Dict[str, Dict[str, int]] = {
        "listening": {},
        "grammar": {},
        "reading": {},
    }

    for sid, sec in sections.items():
        total_s = sec["correct"] + sec["incorrect"] + sec["unanswered"] + sec["invalid"]
        raw = sec["correct"]
        scaled = _raw_to_scaled_section(raw, total_s) if total_s else 31
        if sid == "L":
            listening = scaled
            for t, pdata in sec.get("by_tag", {}).items():
                pt = pdata["correct"] + pdata["incorrect"] + pdata["unanswered"] + pdata["invalid"]
                tag_accuracy["listening"][t] = int(100 * pdata["correct"] / pt) if pt else 0
        elif sid == "S":
            structure = scaled
            structure_part_score = scaled // 2
            written_expr_score = scaled - structure_part_score
            for t, pdata in sec.get("by_tag", {}).items():
                pt = pdata["correct"] + pdata["incorrect"] + pdata["unanswered"] + pdata["invalid"]
                tag_accuracy["grammar"][t] = int(100 * pdata["correct"] / pt) if pt else 0
        elif sid == "R":
            reading = scaled
            for t, pdata in sec.get("by_tag", {}).items():
                pt = pdata["correct"] + pdata["incorrect"] + pdata["unanswered"] + pdata["invalid"]
                tag_accuracy["reading"][t] = int(100 * pdata["correct"] / pt) if pt else 0

    total_scaled = listening + structure + reading
    scores = {
        "total": total_scaled,
        "max": 677,
        "listening": listening,
        "structure": structure,
        "reading": reading,
        "structure_part_score": structure_part_score,
        "written_expr_score": written_expr_score,
    }
    return scores, tag_accuracy


def _generate_narratives_with_gpt(
    scores: Dict[str, Any],
    tag_accuracy: Dict[str, Dict[str, int]],
    sections: Dict[str, Any],
) -> Dict[str, str]:
    settings = get_settings()
    # 分離方針:
    # - analysis はまず ANALYSIS_OPENAI_API_KEY
    # - 未設定なら ANALYSIS_API_KEY（Rails認証用キーと同一運用）
    # - 最終的に OPENAI_API_KEY へフォールバック（後方互換）
    api_key = settings.analysis_openai_api_key or settings.analysis_api_key or settings.openai_api_key
    if not api_key:
        return {
            "summary_closing": "（総評は API キー設定後に生成されます）",
            "strength": "（強みは API キー設定後に生成されます）",
            "challenge": "（課題は API キー設定後に生成されます）",
        }

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        # OpenAI モデル名はドキュメント表記に合わせる
        model_name = "gpt-5-mini"
        slim_sections = {
            sid: {
                "correct": sec["correct"],
                "total": sec["correct"] + sec["incorrect"] + sec["unanswered"] + sec["invalid"],
            }
            for sid, sec in sections.items()
        }
        summary = json.dumps(
            {
                "scores": scores,
                "tag_accuracy": tag_accuracy,
                "section_totals": slim_sections,
            },
            ensure_ascii=False,
        )
        prompt = f"""あなたはTOEFL ITPの模試分析の専門家です。以下の模試結果を踏まえ、受験者向けに次の3つの文章を日本語で作成してください。
- 総評（summary_closing）: 全体の結果を踏まえた励ましと次の一手のアドバイス
- 強み（strength）: tag_accuracy に基づき、正答率が高かった Listening のパート・文法カテゴリ・Reading タイプの良い点
- 課題（challenge）: tag_accuracy に基づき、伸ばすべき領域と具体的な学習アドバイス

tag_accuracy のキー:
- listening: Listening Part 別（tag = 問題タイプ）
- grammar: Structure 文法カテゴリ別
- reading: Reading 問題タイプ別

模試結果:
{summary}

以下のJSON形式のみで返してください。説明は不要です。
{{"summary_closing": "総評の段落", "strength": "強みの段落", "challenge": "課題の段落"}}
"""
        response = client.responses.create(
            model=model_name,
            input=[{"role": "user", "content": prompt}],
            # chat.completions だと長文で message.content が空になりがちなので、
            # generation と同様に responses API へ寄せる.
            reasoning={"effort": "low"},
            text={"verbosity": "low"},
            max_output_tokens=1200,
        )
        text = (response.output_text or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(text[start : end + 1])
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


def generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload: attempt_id, exam_type, student_name, exam_date, answers, items
    各 item に tag (必須) と section, correct_choice が必要.
    """
    answers_list = payload.get("answers") or []
    items_list = payload.get("items") or []
    if not items_list:
        raise ValueError("items must not be empty")
    if answers_list and isinstance(answers_list[0], dict):
        answers_map = _build_answers_map(answers_list)
    else:
        answers_map = _build_answers_map(
            [a.model_dump() if hasattr(a, "model_dump") else a for a in answers_list]
        )

    items = []
    for it in items_list:
        if hasattr(it, "model_dump"):
            it = it.model_dump()
        items.append(it)

    sections, per_item = _run_scoring(items, answers_map)
    total_correct = sum(1 for p in per_item if p.get("status") == "correct")
    total_questions = len(per_item)
    scores, tag_accuracy = _sections_to_scores_and_tag_accuracy(
        sections, total_correct, total_questions
    )
    narratives = _generate_narratives_with_gpt(scores, tag_accuracy, sections)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta = {
        "title": "TOEFL ITP®︎ 模試分析レポート",
        "student_name": payload.get("student_name"),
        "exam_date": payload.get("exam_date"),
        "exam_type": payload.get("exam_type", "full"),
        "report_date": report_date,
    }
    return {
        "meta": meta,
        "scores": scores,
        "tag_accuracy": tag_accuracy,
        "narratives": narratives,
    }
