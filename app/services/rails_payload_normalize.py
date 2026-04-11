"""
Rails API (hinatahoriba/Preness) の Question バリデーションに合わせた payload 正規化.

- correct_choice: %w[A B C D]（大文字）
- tag: Rails Question::TAGS のいずれか（必須・空不可）
- U+FFFD（置換文字）を含む文字列は不正として拒否
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, Dict

# app/models/question.rb (Rails) と一致させる
RAILS_QUESTION_TAGS: frozenset[str] = frozenset(
    {
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
)

logger = logging.getLogger(__name__)

# 旧tag/揺れを Rails の許可 tag に寄せる
#
# 例:
# - reading の mainIdea / rhetorical / not など
# - usage / usage系
RAILS_TAG_ALIASES: dict[str, str] = {
    "mainIdea": "inference",
    "rhetorical": "inference",
    "not": "fact",
    "usage": "vocab",
}

RAILS_TAG_FALLBACK = "fact"

_REPLACEMENT_CHAR = "\ufffd"


def _reject_replacement_char(value: str, ctx: str) -> None:
    if _REPLACEMENT_CHAR in value:
        raise ValueError(
            f"Invalid UTF-8 or replacement character in field ({ctx}): "
            "fix source file encoding (use UTF-8 without corrupt bytes)."
        )


_CHOICE_TAG_RE: dict[str, re.Pattern[str]] = {
    "choice_a": re.compile(r"\[A\](.*?)\[/A\]", re.DOTALL),
    "choice_b": re.compile(r"\[B\](.*?)\[/B\]", re.DOTALL),
    "choice_c": re.compile(r"\[C\](.*?)\[/C\]", re.DOTALL),
    "choice_d": re.compile(r"\[D\](.*?)\[/D\]", re.DOTALL),
}


def _extract_choices_from_tags(question_text: str) -> dict[str, str] | None:
    """
    question_text に [A]...[/A] 〜 [D]...[/D] が4つ揃っていれば
    {"choice_a": ..., "choice_b": ..., "choice_c": ..., "choice_d": ...} を返す.
    揃っていなければ None (Part A や Listening には適用しない).
    """
    result: dict[str, str] = {}
    for key, pat in _CHOICE_TAG_RE.items():
        m = pat.search(question_text)
        if not m:
            return None
        result[key] = m.group(1).strip()
    return result


def _normalize_correct_choice_rails(value: Any, ctx: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"correct_choice must be a string ({ctx})")
    s = value.strip()
    _reject_replacement_char(s, ctx)
    m = re.search(r"([ABCDabcd])", s)
    if not m:
        raise ValueError(f"correct_choice must contain A/B/C/D ({ctx}): {value!r}")
    return m.group(1).upper()


def _normalize_tag_rails(value: Any, ctx: str) -> str:
    if value is None:
        raise ValueError(f"tag is required for Rails ({ctx})")
    if not isinstance(value, str):
        raise ValueError(f"tag must be a string ({ctx})")
    s = value.strip()
    if not s:
        raise ValueError(f"tag is required for Rails ({ctx})")
    _reject_replacement_char(s, ctx)

    if s in RAILS_QUESTION_TAGS:
        return s

    alias = RAILS_TAG_ALIASES.get(s)
    if alias is not None:
        if alias not in RAILS_QUESTION_TAGS:
            raise ValueError(f"internal tag alias is invalid: {s!r} -> {alias!r}")
        return alias

    # それ以外はフォールバックしつつ観測できるように warning を残す
    if RAILS_TAG_FALLBACK not in RAILS_QUESTION_TAGS:
        raise ValueError(f"internal tag fallback is invalid: {RAILS_TAG_FALLBACK!r}")
    logger.warning("Unknown tag for Rails; falling back: tag=%r ctx=%s", s, ctx)
    return RAILS_TAG_FALLBACK


def _patch_question_dict(q: Dict[str, Any], ctx: str) -> None:
    """同一 dict を in-place で Rails 送信用に更新."""
    cc_ctx = f"{ctx}.correct_choice"
    tag_ctx = f"{ctx}.tag"
    q["correct_choice"] = _normalize_correct_choice_rails(q.get("correct_choice"), cc_ctx)
    q["tag"] = _normalize_tag_rails(q.get("tag"), tag_ctx)
    # [A]...[/A] タグが4つ揃っていれば choice_* をタグ内テキストで上書き (Grammar Part B 用)
    qt = q.get("question_text", "")
    if isinstance(qt, str):
        extracted = _extract_choices_from_tags(qt)
        if extracted:
            q.update(extracted)
    # その他の主要テキストに置換文字が混ざっていないか
    for key in (
        "question_text",
        "choice_a",
        "choice_b",
        "choice_c",
        "choice_d",
        "explanation",
    ):
        v = q.get(key)
        if isinstance(v, str) and _REPLACEMENT_CHAR in v:
            _reject_replacement_char(v, f"{ctx}.{key}")


def normalize_mock_payload_for_rails(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock 作成用 payload の deep copy を返す. questions 内の correct_choice / tag を Rails 向けに更新.
    不正な場合は ValueError.
    """
    out = copy.deepcopy(payload)
    sections = out.get("sections")
    if not isinstance(sections, list):
        raise ValueError("payload.sections must be a list")
    for si, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ValueError(f"sections[{si}] must be an object")
        parts = sec.get("parts")
        if not isinstance(parts, list):
            raise ValueError(f"sections[{si}].parts must be a list")
        for pi, part in enumerate(parts):
            if not isinstance(part, dict):
                raise ValueError(f"sections[{si}].parts[{pi}] must be an object")
            qsets = part.get("question_sets")
            if not isinstance(qsets, list):
                raise ValueError(f"sections[{si}].parts[{pi}].question_sets must be a list")
            for qi, qset in enumerate(qsets):
                if not isinstance(qset, dict):
                    raise ValueError(
                        f"sections[{si}].parts[{pi}].question_sets[{qi}] must be an object"
                    )
                questions = qset.get("questions")
                if not isinstance(questions, list):
                    raise ValueError(
                        f"sections[{si}].parts[{pi}].question_sets[{qi}].questions must be a list"
                    )
                for qj, q in enumerate(questions):
                    if not isinstance(q, dict):
                        raise ValueError(
                            f"sections[{si}].parts[{pi}].question_sets[{qi}].questions[{qj}] "
                            "must be an object"
                        )
                    ctx = (
                        f"sections[{si}] part={part.get('part_type')} "
                        f"qset={qset.get('display_order')} q={q.get('display_order')}"
                    )
                    _patch_question_dict(q, ctx)
    return out


def normalize_exercise_payload_for_rails(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Exercise 作成用 payload の deep copy を返す. question_sets[].questions を Rails 向けに更新.
    """
    out = copy.deepcopy(payload)
    qsets = out.get("question_sets")
    if not isinstance(qsets, list):
        raise ValueError("payload.question_sets must be a list")
    for qi, qset in enumerate(qsets):
        if not isinstance(qset, dict):
            raise ValueError(f"question_sets[{qi}] must be an object")
        questions = qset.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"question_sets[{qi}].questions must be a list")
        for qj, q in enumerate(questions):
            if not isinstance(q, dict):
                raise ValueError(f"question_sets[{qi}].questions[{qj}] must be an object")
            ctx = f"question_sets[{qi}] q={q.get('display_order')}"
            _patch_question_dict(q, ctx)
    return out
