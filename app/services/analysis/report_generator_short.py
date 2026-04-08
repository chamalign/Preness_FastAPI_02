"""Short 模試用分析レポート: tag 別正答率 (必須) + passages 別スコア."""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.services.analysis.report_generator import _build_answers_map, _normalize_section_id, _raw_to_scaled_section

logger = logging.getLogger(__name__)

TAG_ALIASES: Dict[str, str] = {
    "short_conv": "shortConv",
    "longconv": "longConv",
    "long_conv": "longConv",
    "talks": "talk",
    "sentence_struct": "sentenceStruct",
    "sentencestructure": "sentenceStruct",
    "modifier_connect": "modifierConnect",
    "noun_pronoun": "nounPronoun",
    "nounpronoun": "nounPronoun",
}

KNOWN_TAGS: Set[str] = {
    "shortConv",
    "longConv",
    "talk",
    "sentenceStruct",
    "verbForm",
    "modifierConnect",
    "nounPronoun",
    "vocab",
    "inference",
    "fact",
}


def _canonical_tag(tag: str) -> str:
    t = (tag or "").strip()
    if not t:
        return ""
    if t in KNOWN_TAGS:
        return t
    tl = t.lower().replace("-", "_")
    return TAG_ALIASES.get(tl, t)


def _fill_counts(
    items: List[Dict[str, Any]],
    answers_map: Dict[str, str],
    qid_to_correct: Dict[str, str],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    sections: Dict[str, Dict[str, Dict[str, int]]] = {"L": {}, "S": {}, "R": {}}
    for it in items:
        if hasattr(it, "model_dump"):
            it = it.model_dump()
        qid = (it.get("item_id") or it.get("question_id") or "").strip()
        tag = _canonical_tag((it.get("tag") or "").strip())
        sid = _normalize_section_id(
            str(it.get("section_id") or ""),
            str(it.get("section_type") or ""),
        )
        if tag not in sections[sid]:
            sections[sid][tag] = {
                "correct": 0,
                "incorrect": 0,
                "unanswered": 0,
                "invalid": 0,
            }
        correct_choice = qid_to_correct[qid]
        user_choice = answers_map.get(qid)
        if not user_choice:
            status = "unanswered"
        elif user_choice not in ("A", "B", "C", "D"):
            status = "invalid"
        elif user_choice == correct_choice:
            status = "correct"
        else:
            status = "incorrect"
        sections[sid][tag][status] += 1
    return sections


def _section_scaled_scores(
    sections: Dict[str, Dict[str, Dict[str, int]]],
) -> Tuple[int, int, int]:
    def sec_totals(sid: str) -> Tuple[int, int]:
        c = t = 0
        for pdata in sections[sid].values():
            c += pdata["correct"]
            t += (
                pdata["correct"]
                + pdata["incorrect"]
                + pdata["unanswered"]
                + pdata["invalid"]
            )
        return c, t

    lc, lt = sec_totals("L")
    sc, st = sec_totals("S")
    rc, rt = sec_totals("R")
    return (
        _raw_to_scaled_section(lc, lt) if lt else 31,
        _raw_to_scaled_section(sc, st) if st else 31,
        _raw_to_scaled_section(rc, rt) if rt else 31,
    )


def _tag_accuracy_from_sections(
    sections: Dict[str, Dict[str, Dict[str, int]]],
) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {
        "listening": {},
        "grammar": {},
        "reading": {},
    }
    sid_map = {"L": "listening", "S": "grammar", "R": "reading"}
    for sid, name in sid_map.items():
        for t, pdata in sections[sid].items():
            pt = (
                pdata["correct"]
                + pdata["incorrect"]
                + pdata["unanswered"]
                + pdata["invalid"]
            )
            out[name][t] = int(100 * pdata["correct"] / pt) if pt else 0
    return out


def _latest_flat(tag_accuracy: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    latest: Dict[str, int] = {}
    for tags in tag_accuracy.values():
        for tk, pv in tags.items():
            latest[tk] = pv
    return latest


def _passage_scores_flex(
    passages: List[Dict[str, Any]],
    answers_map: Dict[str, str],
    qid_to_correct: Dict[str, str],
    reading_qids: Set[str],
) -> List[Dict[str, Any]]:
    out = []
    for i, p in enumerate(passages):
        theme = (p.get("theme") or "").strip()
        qids = p.get("question_ids") or []
        if not qids:
            raise ValueError(f"passages[{i}]: question_ids must not be empty")
        correct = 0
        for qid in qids:
            qid = str(qid).strip()
            if not qid:
                raise ValueError(f"passages[{i}]: empty question_id")
            if qid not in reading_qids:
                raise ValueError(
                    f"passages[{i}]: question_id {qid} must be a Reading item"
                )
            u = answers_map.get(qid)
            if u and u == qid_to_correct[qid]:
                correct += 1
        mx = len(qids)
        out.append({"theme": theme or f"Passage {i + 1}", "score": correct, "max": mx})
    return out


def _reading_qids(items: List[Dict[str, Any]]) -> Set[str]:
    s: Set[str] = set()
    for it in items:
        if hasattr(it, "model_dump"):
            it = it.model_dump()
        sid = _normalize_section_id(
            str(it.get("section_id") or ""),
            str(it.get("section_type") or ""),
        )
        if sid == "R":
            qid = (it.get("item_id") or it.get("question_id") or "").strip()
            if qid:
                s.add(qid)
    return s


def _generate_short_narratives(
    tag_accuracy: Dict[str, Dict[str, int]],
    scores: Dict[str, Any],
    summary_bullets: List[str],
) -> Dict[str, Any]:
    settings = get_settings()
    placeholder = {
        "summary_closing": "（総評は API キー設定後に生成されます）",
        "strength": "（強みは API キー設定後に生成されます）",
        "challenge": "（課題は API キー設定後に生成されます）",
    }
    # 分離方針:
    # - analysis はまず ANALYSIS_OPENAI_API_KEY
    # - 未設定なら ANALYSIS_API_KEY（Rails認証キーと同一運用）
    # - 最終的に OPENAI_API_KEY へフォールバック（後方互換）
    api_key = settings.analysis_openai_api_key or settings.analysis_api_key or settings.openai_api_key
    if not api_key:
        return {**placeholder, "summary_bullets": summary_bullets}

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        # OpenAI モデル名はドキュメント表記に合わせる
        model_name = "gpt-5-mini"
        ctx = json.dumps(
            {"tag_accuracy": tag_accuracy, "scores": scores, "summary_bullets": summary_bullets},
            ensure_ascii=False,
        )
        prompt = f"""あなたはTOEFL ITP Short模試分析の専門家です。tag_accuracy は Listening Part 別・文法カテゴリ別・Reading タイプ別の正答率(%)です。以下に基づき日本語で回答してください。
1. summary_closing: 箇条書きの次に続く総評段落
2. strength: 正答率が高い tag の領域
3. challenge: 伸ばすべき tag と学習アドバイス

データ:
{ctx}

次のJSONのみ返すこと。
{{"summary_closing": "...", "strength": "...", "challenge": "..."}}
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
                "summary_bullets": summary_bullets,
                "summary_closing": obj.get("summary_closing") or "",
                "strength": obj.get("strength") or "",
                "challenge": obj.get("challenge") or "",
            }
    except Exception as e:
        logger.warning("GPT short narrative failed: %s", e)
    return {
        "summary_bullets": summary_bullets,
        "summary_closing": "（総評の生成でエラーが発生しました）",
        "strength": "（強みの生成でエラーが発生しました）",
        "challenge": "（課題の生成でエラーが発生しました）",
    }


def generate_short_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    answers_list = payload.get("answers") or []
    items_list = payload.get("items") or []
    passages_in = payload.get("passages") or []

    if not items_list:
        raise ValueError("items must not be empty")
    if not passages_in:
        raise ValueError("passages must not be empty")

    items_norm: List[Dict[str, Any]] = []
    for it in items_list:
        if hasattr(it, "model_dump"):
            it = it.model_dump()
        items_norm.append(it)

    qid_to_correct: Dict[str, str] = {}
    seen: Set[str] = set()
    for it in items_norm:
        qid = (it.get("item_id") or it.get("question_id") or "").strip()
        if not qid:
            continue
        if qid in seen:
            raise ValueError(f"duplicate question_id: {qid}")
        seen.add(qid)
        if not (it.get("tag") or "").strip():
            raise ValueError("items[].tag は Short 分析に必須です. question_id=" + qid)
        cc = (it.get("correct_choice") or "").strip().upper()
        if cc not in ("A", "B", "C", "D"):
            raise ValueError(f"invalid correct_choice for question_id={qid}")
        qid_to_correct[qid] = cc

    answers_map = _build_answers_map(
        answers_list
        if not answers_list or isinstance(answers_list[0], dict)
        else [a.model_dump() if hasattr(a, "model_dump") else a for a in answers_list]
    )

    sections = _fill_counts(items_norm, answers_map, qid_to_correct)
    for sid in ("L", "S", "R"):
        if not sections[sid]:
            raise ValueError(
                f"Short 分析には Listening/Structure/Reading それぞれ1問以上必要です. "
                f"不足: section {sid}"
            )

    listening, structure, reading = _section_scaled_scores(sections)
    total_scaled = listening + structure + reading
    tag_accuracy = _tag_accuracy_from_sections(sections)
    latest = _latest_flat(tag_accuracy)

    scores = {
        "total": total_scaled,
        "max": 677,
        "listening": listening,
        "structure": structure,
        "reading": reading,
        "structure_part_score": structure // 2,
        "written_expr_score": structure - structure // 2,
    }

    reading_ids = _reading_qids(items_norm)
    all_pq: List[str] = []
    for p in passages_in:
        for q in p.get("question_ids") or []:
            all_pq.append(str(q).strip())
    if len(all_pq) != len(set(all_pq)):
        raise ValueError("passages: question_ids must be disjoint")

    passages_out = _passage_scores_flex(
        passages_in, answers_map, qid_to_correct, reading_ids
    )

    goal_score = payload.get("goal_score")
    community_threshold = 550
    gs: Optional[int] = int(goal_score) if goal_score is not None else None

    if gs is not None:
        gap = gs - total_scaled
        goal_line = f"・目標({gs}点): {'達成' if gap <= 0 else f'あと{gap}点'}"
    else:
        goal_line = "・目標: 未設定"

    if total_scaled >= community_threshold:
        comm_line = f"・選抜コミュニティ: 参加条件({community_threshold}点)を達成"
    else:
        comm_line = (
            f"・選抜コミュニティ: 参加条件({community_threshold}点)まであと"
            f"{community_threshold - total_scaled}点"
        )

    summary_bullets = [
        f"・総合: {total_scaled}点 / 677点",
        goal_line,
        comm_line,
    ]

    narratives = _generate_short_narratives(tag_accuracy, scores, summary_bullets)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta = {
        "title": "TOEFL ITP®︎ 模試分析レポート (Short)",
        "student_name": payload.get("student_name"),
        "exam_date": payload.get("exam_date"),
        "exam_type": "short",
        "report_date": report_date,
        "goal_score": gs,
        "community_threshold": community_threshold,
    }

    return {
        "meta": meta,
        "scores": scores,
        "tag_accuracy": tag_accuracy,
        "latest": latest,
        "passages": passages_out,
        "narratives": narratives,
    }
