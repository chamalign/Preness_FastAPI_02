"""Reading 中間形式の正規化（安全な範囲）と Mock 投入前バリデーション."""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, Dict

from app.services.generation.markers import (
    IdempotencyError,
    inject_reading_markers,
)

logger = logging.getLogger(__name__)

# 語彙 [Vn] / 指示・語法 [Un] ペア. 本文と問題文で同じスパンを要求する.
_READING_MARKER_PAIR_RE = re.compile(
    r"\[([UV])(\d+)\](.*?)\[/\1\2\]",
    re.DOTALL,
)

# [U{n}] マーカーのみ (Reading 注入用)
_U_MARKER_RE = re.compile(r"\[U(\d+)\]")

_VALID_CORRECT = frozenset({"A", "B", "C", "D"})
_FORBIDDEN_SUBSTRING_IN_READING_QUESTION_TEXT = "in line"
_QUESTION_STRING_KEYS = (
    "question_text",
    "choice_a",
    "choice_b",
    "choice_c",
    "choice_d",
)


def reject_reading_question_text_if_contains_inline(
    question_text: str,
    *,
    passage_index: int,
    question_index: int,
) -> None:
    """
    Reading の question に line 参照表記を許さない. 混入時は ValueError.

    「in line」を部分文字列として含むものを拒否する (サイズ区別あり).
    """
    if _FORBIDDEN_SUBSTRING_IN_READING_QUESTION_TEXT in question_text:
        sub = _FORBIDDEN_SUBSTRING_IN_READING_QUESTION_TEXT
        raise ValueError(
            f"reading.passages[{passage_index}].questions[{question_index}]"
            f".question_text must not contain the substring {sub!r}"
        )


def _normalize_reading_marker_inner(inner: str) -> str:
    """マーカー内のテキストを比較用に正規化（前後空白・外側の引用符を除去）."""
    s = inner.strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    return s


def reject_reading_question_markers_not_in_passage(
    passage_text: str,
    question_text: str,
    *,
    passage_index: int,
    question_index: int,
) -> None:
    """
    question_text 内の [Un]/[Vn] マーカーについて, 同じ id の
    ``[Un]正規化後の語句[/Un]`` が passage_text に部分文字列として含まれることを要求する.
    マーカーが無い設問は何もしない.
    """
    for m in _READING_MARKER_PAIR_RE.finditer(question_text):
        kind, num, inner = m.group(1), m.group(2), m.group(3)
        normalized = _normalize_reading_marker_inner(inner)
        if not normalized:
            raise ValueError(
                f"reading.passages[{passage_index}].questions[{question_index}]: "
                f"marker [{kind}{num}] has empty content after normalization"
            )
        expected_span = f"[{kind}{num}]{normalized}[/{kind}{num}]"
        if expected_span not in passage_text:
            raise ValueError(
                f"reading.passages[{passage_index}].questions[{question_index}]: "
                f"passage must contain {expected_span!r} "
                f"(marker from question_text must match passage markup)"
            )


def _validate_u_markers_for_passage(
    passage_text: str,
    questions: list,
    *,
    passage_index: int,
) -> None:
    """
    [U{n}] マーカーが passage と vocab/usage 設問で一致することを確認する.

    - usage 設問は question_text に [U{n}] を1つだけ持つこと（vocab は [Vn] を使うためチェック対象外）
    - 設問の [U{n}] 番号の順序が passage 内の出現順と一致すること
    - 番号は 1 から連番で抜け・重複なし
    """
    passage_nums = [int(m.group(1)) for m in _U_MARKER_RE.finditer(passage_text)]

    question_nums: list[int] = []
    for qi, q in enumerate(questions, start=1):
        if q.get("tag") not in ("usage", "vocab"):
            continue
        qt: str = q.get("question_text") or ""
        found = [int(n) for n in _U_MARKER_RE.findall(qt)]
        if len(found) != 1:
            raise ValueError(
                f"reading.passages[{passage_index}].questions[{qi}].question_text "
                f"must contain exactly one [U{{n}}] marker (found {len(found)})"
            )
        question_nums.append(found[0])

    if passage_nums != question_nums:
        raise ValueError(
            f"reading.passages[{passage_index}]: passage [U] markers {passage_nums} "
            f"do not match vocab/usage question [U] markers {question_nums}"
        )

    if question_nums:
        expected = list(range(1, len(question_nums) + 1))
        if question_nums != expected:
            raise ValueError(
                f"reading.passages[{passage_index}]: [U] marker numbers {question_nums} "
                f"must be 1-based consecutive (expected {expected})"
            )


def sanitize_reading(reading: Dict[str, Any]) -> Dict[str, Any]:
    """
    reading dict のコピーを返す. インプレースは変更しない.

    - question_text / choice_a〜d: 前後空白を除去
    - correct_choice: 前後空白除去後に大文字化（A-D）
    """
    out = copy.deepcopy(reading)
    passages = out.get("passages")
    if not isinstance(passages, list):
        return out
    for passage in passages:
        if not isinstance(passage, dict):
            continue
        questions = passage.get("questions")
        if not isinstance(questions, list):
            continue
        for q in questions:
            if not isinstance(q, dict):
                continue
            for key in _QUESTION_STRING_KEYS:
                val = q.get(key)
                if isinstance(val, str):
                    q[key] = val.strip()
            cc = q.get("correct_choice")
            if isinstance(cc, str):
                q["correct_choice"] = cc.strip().upper()
    return out


def validate_reading(
    reading: Dict[str, Any],
    *,
    expected_passages: int,
    questions_per_passage: int = 10,
) -> None:
    """
    Mock 用 reading を検証する. 不整合なら ValueError.

    - passages の要素数 == expected_passages
    - 各 passage: passage が非空 str, questions が questions_per_passage 件
    - 各 question: 必須キーと correct_choice in A-D
    - 各 question: question_text に「in line」を含めない (paragraph/sentence を使う想定)
    - 各 question: question_text に [Un]/[Vn] がある場合, 本文に同じマークの同一語が必要
    """
    if not isinstance(reading, dict):
        raise ValueError("reading must be a dict")
    passages = reading.get("passages")
    if not isinstance(passages, list):
        raise ValueError("reading.passages must be a list")
    got = len(passages)
    if got != expected_passages:
        raise ValueError(
            f"reading.passages must have exactly {expected_passages} passage(s) (got {got})"
        )

    for pi, passage in enumerate(passages, start=1):
        if not isinstance(passage, dict):
            raise ValueError(f"reading.passages[{pi}] must be an object")
        text = passage.get("passage")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"reading.passages[{pi}].passage must be a non-empty string"
            )
        questions = passage.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"reading.passages[{pi}].questions must be a list")
        qn = len(questions)
        if qn != questions_per_passage:
            raise ValueError(
                f"reading.passages[{pi}].questions must have exactly "
                f"{questions_per_passage} item(s) (got {qn})"
            )
        for qi, q in enumerate(questions, start=1):
            if not isinstance(q, dict):
                raise ValueError(
                    f"reading.passages[{pi}].questions[{qi}] must be an object"
                )
            for key in _QUESTION_STRING_KEYS:
                if key not in q:
                    raise ValueError(
                        f"reading.passages[{pi}].questions[{qi}] missing required key: {key}"
                    )
                val = q[key]
                if not isinstance(val, str) or not val:
                    raise ValueError(
                        f"reading.passages[{pi}].questions[{qi}].{key} must be a non-empty string"
                    )
            qt = q["question_text"]
            reject_reading_question_text_if_contains_inline(
                qt,
                passage_index=pi,
                question_index=qi,
            )
            reject_reading_question_markers_not_in_passage(
                text,
                qt,
                passage_index=pi,
                question_index=qi,
            )
            cc = q.get("correct_choice")
            if cc not in _VALID_CORRECT:
                raise ValueError(
                    f"reading.passages[{pi}].questions[{qi}].correct_choice must be "
                    f"one of A/B/C/D (got {cc!r})"
                )
        _validate_u_markers_for_passage(text, questions, passage_index=pi)


def prepare_reading_for_mock(
    full_parts: Dict[str, Any],
    *,
    expected_passages: int,
    questions_per_passage: int = 10,
) -> None:
    """full_parts['reading'] を inject markers → sanitize → validate し, 結果で置き換える."""
    reading = full_parts.get("reading")
    if not isinstance(reading, dict):
        raise ValueError('full_parts["reading"] must be a dict')

    # vocab/usage 設問の対象語句に [U{n}] マーカーを注入する.
    # 既にマーカーが入っている passage は IdempotencyError を swallow してスキップ.
    passages = reading.get("passages")
    if isinstance(passages, list):
        for passage_block in passages:
            if not isinstance(passage_block, dict):
                continue
            passage_text = passage_block.get("passage")
            questions = passage_block.get("questions")
            if not isinstance(passage_text, str) or not isinstance(questions, list):
                continue
            try:
                marked_passage, marked_questions = inject_reading_markers(
                    passage_text, questions
                )
                passage_block["passage"] = marked_passage
                passage_block["questions"] = marked_questions
            except IdempotencyError:
                logger.debug("passage already has [U] markers; skipping injection")

    sanitized = sanitize_reading(reading)
    validate_reading(
        sanitized,
        expected_passages=expected_passages,
        questions_per_passage=questions_per_passage,
    )
    full_parts["reading"] = sanitized
