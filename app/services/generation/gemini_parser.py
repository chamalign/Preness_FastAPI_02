"""Gemini plain-text 出力 (===ITEM:N=== / ===PASSAGE=== 形式) を pipeline dict に変換するパーサー."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_ITEM_RE = re.compile(r"===ITEM:(\d+)===\n(.*?)\n===END:\1===", re.DOTALL)
_PASSAGE_RE = re.compile(r"===PASSAGE===\n(.*?)\n===END_PASSAGE===", re.DOTALL)


def _parse_fields(block_text: str) -> Dict[str, str]:
    """@field_name\\nvalue 形式をパース.多行 value（@passage など）も扱える."""
    fields: Dict[str, str] = {}
    text = "\n" + block_text
    parts = re.split(r"\n@", text)
    for part in parts[1:]:
        newline = part.find("\n")
        if newline == -1:
            key = part.strip()
            value = ""
        else:
            key = part[:newline].strip()
            value = part[newline + 1:].strip()
        fields[key] = value
    return fields


def _or_none(v: str) -> Optional[str]:
    s = v.strip()
    return None if s.lower() == "null" or s == "" else s


def _or_none_int(v: str) -> Optional[int]:
    s = v.strip()
    if s.lower() == "null" or s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_listening_script(text: str) -> List[Dict[str, str]]:
    """---turn--- 区切りスクリプトを [{speaker, text}] のリストに変換."""
    turns = []
    for block in text.split("---turn---"):
        block = block.strip()
        if not block:
            continue
        speaker: Optional[str] = None
        turn_text: Optional[str] = None
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("speaker:"):
                speaker = line[len("speaker:"):].strip()
            elif line.startswith("text:"):
                turn_text = line[len("text:"):].strip()
        if speaker and turn_text:
            turns.append({"speaker": speaker, "text": turn_text})
    return turns


def _common_question_fields(f: Dict[str, str]) -> Dict[str, Any]:
    """choice/correct_choice/tag/explanation/wrong_reason の共通フィールドを抽出."""
    return {
        "choice_a": f.get("choice_a", ""),
        "choice_b": f.get("choice_b", ""),
        "choice_c": f.get("choice_c", ""),
        "choice_d": f.get("choice_d", ""),
        "correct_choice": f.get("correct_choice", "").strip().upper(),
        "tag": _or_none(f.get("tag", "")),
        "explanation": _or_none(f.get("explanation", "")),
        "wrong_reason_a": _or_none(f.get("wrong_reason_a", "")),
        "wrong_reason_b": _or_none(f.get("wrong_reason_b", "")),
        "wrong_reason_c": _or_none(f.get("wrong_reason_c", "")),
        "wrong_reason_d": _or_none(f.get("wrong_reason_d", "")),
    }


def parse_p01_listening(text: str) -> Dict[str, Any]:
    items = []
    for m in _ITEM_RE.finditer(text):
        f = _parse_fields(m.group(2))
        script = _parse_listening_script(f.get("listening_script", ""))
        item: Dict[str, Any] = {
            "question_text": f.get("question_text", ""),
            **_common_question_fields(f),
            "content": {"listening_script": script},
        }
        items.append(item)
    return {"items": items}


def parse_p04_grammar_a(text: str) -> Dict[str, Any]:
    questions = []
    for m in _ITEM_RE.finditer(text):
        f = _parse_fields(m.group(2))
        q: Dict[str, Any] = {
            "question_text": f.get("question_text", ""),
            **_common_question_fields(f),
        }
        questions.append(q)
    return {"questions": questions}


def parse_p05_grammar_b(text: str) -> Dict[str, Any]:
    """@question_template の {A}〜{D} を [A]chunk_a[/A]〜[D]chunk_d[/D] に置換して
    question_text を組み立てる.choice_a〜d は "A"〜"D" のラベル文字列.
    """
    questions = []
    for m in _ITEM_RE.finditer(text):
        f = _parse_fields(m.group(2))
        template = f.get("question_template", "")
        chunks = {
            "A": f.get("chunk_a", ""),
            "B": f.get("chunk_b", ""),
            "C": f.get("chunk_c", ""),
            "D": f.get("chunk_d", ""),
        }
        question_text = template
        for letter, chunk in chunks.items():
            question_text = question_text.replace(f"{{{letter}}}", f"[{letter}]{chunk}[/{letter}]")
        q: Dict[str, Any] = {
            "question_text": question_text,
            **_common_question_fields(f),
        }
        questions.append(q)
    return {"questions": questions}


def _parse_reading_question(f: Dict[str, str]) -> Dict[str, Any]:
    """===ITEM:N=== フィールド dict から reading 設問 dict を組み立てる（vocab/usage の target_* 含む）."""
    return {
        "question_text": f.get("question_text", ""),
        **_common_question_fields(f),
        "target_phrase": _or_none(f.get("target_phrase", "")),
        "target_paragraph": _or_none_int(f.get("target_paragraph", "")),
        "target_sentence": _or_none_int(f.get("target_sentence", "")),
    }


def parse_p06_reading(text: str) -> Dict[str, Any]:
    """単一パッセージ版.===PASSAGE===...===END_PASSAGE=== と ===ITEM:1===...===ITEM:10=== を取得する."""
    pm = _PASSAGE_RE.search(text)
    if not pm:
        raise ValueError("===PASSAGE===...===END_PASSAGE=== block not found")
    pf = _parse_fields(pm.group(1))
    passage_text = pf.get("passage", "")
    passage_theme = _or_none(pf.get("passage_theme", ""))

    questions = [
        _parse_reading_question(_parse_fields(m.group(2)))
        for m in _ITEM_RE.finditer(text)
    ]

    return {
        "passages": [
            {
                "passage": passage_text,
                "passage_theme": passage_theme,
                "questions": questions,
            }
        ]
    }


def parse_multi_passage_reading(text: str, items_per_passage: int = 10) -> Dict[str, Any]:
    """複数の ===PASSAGE===...===END_PASSAGE=== ブロックと, グローバル連番の ===ITEM:N=== ブロックを
    パースする.アイテム番号はパッセージをまたいで連番（passage1: 1–10, passage2: 11–20, ...）.
    各パッセージの [U{n}] マーカーカウンターはパッセージごとにリセットされる.
    """
    passage_matches = list(_PASSAGE_RE.finditer(text))
    if not passage_matches:
        raise ValueError("===PASSAGE===...===END_PASSAGE=== block not found")

    all_items = list(_ITEM_RE.finditer(text))

    passages = []
    for i, pm in enumerate(passage_matches):
        pf = _parse_fields(pm.group(1))
        passage_text = pf.get("passage", "")
        passage_theme = _or_none(pf.get("passage_theme", ""))

        start = i * items_per_passage
        end = start + items_per_passage
        passage_items = all_items[start:end]
        questions = [
            _parse_reading_question(_parse_fields(m.group(2)))
            for m in passage_items
        ]

        passages.append(
            {
                "passage": passage_text,
                "passage_theme": passage_theme,
                "questions": questions,
            }
        )

    return {"passages": passages}


def parse_fm06_reading(text: str) -> Dict[str, Any]:
    return parse_multi_passage_reading(text, items_per_passage=10)


def parse_sm06_reading(text: str) -> Dict[str, Any]:
    return parse_multi_passage_reading(text, items_per_passage=10)
