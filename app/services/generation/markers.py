"""Reading 問題の [U{n}] マーカー注入."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 略語の後のピリオドで文分割しないよう lookbehind を固定長で列挙する.
# e.g. / i.e. / etc. / U.S. → 3文字, Mr. / Ms. / Dr. / St. → 2文字
_SENTENCE_END = re.compile(
    r"(?<!e\.g)(?<!i\.e)(?<!etc)(?<!U\.S)"
    r"(?<!Mr)(?<!Ms)(?<!Dr)(?<!St)"
    r"[.!?]+\s+"
)

_U_MARKER_RE = re.compile(r"\[U\d+\]")


class MarkerError(ValueError):
    """passage / question_text へのマーカー注入で不整合が見つかったとき."""

    def __init__(self, item_index: int, reason: str) -> None:
        self.item_index = item_index
        self.reason = reason
        super().__init__(f"item[{item_index}]: {reason}")


class IdempotencyError(ValueError):
    """既にマーカーが注入済みの passage に再注入しようとしたとき."""


def split_into_sentences(paragraph: str) -> list[str]:
    """段落を文単位に分割する.略語の末尾ピリオドでは分割しない."""
    parts = _SENTENCE_END.split(paragraph.strip() + " ")
    return [p.strip() for p in parts if p.strip()]


def verify_location(passage: str, phrase: str, para_idx: int, sent_idx: int) -> bool:
    """
    phrase が passage の (para_idx, sent_idx) に存在するか確認する.
    True を返すか, 警告ログを出して False を返す.例外は出さない.
    """
    paragraphs = passage.split("\n\n")
    if para_idx < 1 or para_idx > len(paragraphs):
        logger.warning("paragraph index %d out of range (passage has %d paragraphs)", para_idx, len(paragraphs))
        return False
    para = paragraphs[para_idx - 1]
    sentences = split_into_sentences(para)
    if sent_idx < 1 or sent_idx > len(sentences):
        logger.warning(
            "sentence index %d out of range in paragraph %d (has %d sentences)",
            sent_idx, para_idx, len(sentences),
        )
        return False
    return phrase in sentences[sent_idx - 1]


def inject_reading_markers(
    passage: str,
    questions: list[dict],
) -> tuple[str, list[dict]]:
    """
    Reading 問題用に, passage と各 vocab/usage 設問の question_text に
    同番号の [U{n}]...[/U{n}] マーカーを対で挿入する.

    vocab と usage は同じカウンターを共有する.
    引数のリスト/文字列は変更しない（純粋関数）.

    Raises:
        IdempotencyError: passage に既に [U{n}] マーカーが含まれる場合.
        MarkerError: 不整合があれば設問番号と理由を含めて送出.
    """
    if _U_MARKER_RE.search(passage):
        raise IdempotencyError(
            "Passage already contains [U{n}] markers; refusing to double-inject"
        )

    out_passage = passage
    out_questions: list[dict] = []
    marker_counter = 1

    for i, q in enumerate(questions):
        tag = q.get("tag") or ""
        if tag not in ("vocab", "usage"):
            out_questions.append(dict(q))
            continue

        phrase = q.get("target_phrase")
        para_idx = q.get("target_paragraph")
        sent_idx = q.get("target_sentence")

        if not phrase or phrase == "null":
            raise MarkerError(i, "target_phrase missing for vocab/usage")

        count = out_passage.count(phrase)
        if count == 0:
            raise MarkerError(i, f"target_phrase '{phrase}' not found in passage")
        if count >= 2:
            raise MarkerError(
                i,
                f"target_phrase '{phrase}' appears {count} times in passage; must be exactly once",
            )

        if para_idx is not None and sent_idx is not None:
            if not verify_location(out_passage, phrase, para_idx, sent_idx):
                logger.warning(
                    "item[%d]: phrase %r not found at paragraph %d, sentence %d (soft check)",
                    i, phrase, para_idx, sent_idx,
                )

        n = marker_counter
        out_passage = out_passage.replace(phrase, f"[U{n}]{phrase}[/U{n}]", 1)

        q_copy = dict(q)
        qt: str = q.get("question_text") or ""
        quoted = f'"{phrase}"'
        if quoted in qt:
            q_copy["question_text"] = qt.replace(quoted, f'"[U{n}]{phrase}[/U{n}]"', 1)
        elif phrase in qt:
            q_copy["question_text"] = qt.replace(phrase, f"[U{n}]{phrase}[/U{n}]", 1)
        else:
            raise MarkerError(i, f"target_phrase '{phrase}' not found in question_text")

        out_questions.append(q_copy)
        marker_counter += 1

    return out_passage, out_questions
