"""Full Mock 用ペイロード組み立て (MockCreate 形)."""

from typing import Any, Dict, List, Literal, Optional

# scripts / conversation_audio_url の格納先ポリシー.
# "questions"     : questions[].scripts + questions[].conversation_audio_url に入れる (現行 Rails 方針)
# "question_sets" : question_sets[].scripts + question_sets[].conversation_audio_url に入れる
# "both"          : 両方に入れる (移行期間用)
ScriptPlacement = Literal["questions", "question_sets", "both"]
SCRIPT_PLACEMENT: ScriptPlacement = "questions"


def build_listening_part_for_api(
    part_json: Dict[str, Any],
    part_type: str,
    display_order: int,
    audio_url_map: Optional[Dict[str, str]] = None,
    block_starts_per_part: Optional[Dict[str, List[int]]] = None,
    script_placement: Optional[ScriptPlacement] = None,
) -> Dict[str, Any]:
    """
    Listening 1 パート分を API 用 question_sets に変換.
    audio_url_map: 分割時は part_type:block_start:passage, part_type:idx:question. 非分割時は part_type:idx.
    block_starts_per_part: 各 part のブロック先頭 item 番号のリスト. 同一ブロックの items は
      1 つの question_set にまとめられる（Listening B/C の「1会話+4問」形式に対応）.
    script_placement: None のときはモジュール定数 SCRIPT_PLACEMENT を使用.
    """
    placement: ScriptPlacement = script_placement if script_placement is not None else SCRIPT_PLACEMENT

    items = part_json.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError(f"Listening part JSON の items が不正です: {part_type}")

    # フェーズ1: block_start が同じ items を同一グループにまとめる.
    # block_starts_per_part が未指定の場合は各 item が独立ブロック（従来動作と同じ）.
    grouped: Dict[int, List[tuple]] = {}
    for idx, item in enumerate(items, start=1):
        block_starts = (block_starts_per_part or {}).get(part_type)
        if block_starts:
            block_start = max((b for b in block_starts if b <= idx), default=idx)
        else:
            block_start = idx
        grouped.setdefault(block_start, []).append((idx, item))

    # フェーズ2: ブロックごとに 1 つの question_set を生成し, 複数問をまとめる.
    question_sets: List[Dict[str, Any]] = []
    for qs_order, (block_start, block_items) in enumerate(grouped.items(), start=1):
        passage_url = None
        if audio_url_map:
            passage_url = audio_url_map.get(f"{part_type}:{block_start}:passage")
            if passage_url is None:
                passage_url = audio_url_map.get(f"{part_type}:{block_start}")

        # question_set レベルの placement 用フィールド.
        # qs_scripts にはブロック先頭 item のスクリプトを代表値として使う.
        first_item = block_items[0][1]
        first_scripts = (first_item.get("content") or {}).get("listening_script")
        qs_conv_audio = passage_url if placement in ("question_sets", "both") else None
        qs_scripts = first_scripts if placement in ("question_sets", "both") else None

        questions: List[Dict[str, Any]] = []
        for q_order, (idx, item) in enumerate(block_items, start=1):
            question_url = (audio_url_map or {}).get(f"{part_type}:{idx}:question")

            content = item.get("content")
            if not isinstance(content, dict) or content.get("listening_script") is None:
                raise ValueError(
                    f"Listening item[{idx}] ({part_type}): content.listening_script is required"
                )
            scripts = content["listening_script"]

            # placement に応じて各フィールドの配置先を決める.
            q_conv_audio = passage_url if placement in ("questions", "both") else None
            q_scripts = scripts if placement in ("questions", "both") else None

            questions.append({
                "display_order": q_order,
                "question_text": item["question_text"],
                "question_audio_url": question_url,
                "conversation_audio_url": q_conv_audio,
                "choice_a": item["choice_a"],
                "choice_b": item["choice_b"],
                "choice_c": item["choice_c"],
                "choice_d": item["choice_d"],
                "correct_choice": item["correct_choice"],
                "explanation": item.get("explanation"),
                "tag": item.get("tag"),
                "scripts": q_scripts,
                "wrong_reason_a": item.get("wrong_reason_a"),
                "wrong_reason_b": item.get("wrong_reason_b"),
                "wrong_reason_c": item.get("wrong_reason_c"),
                "wrong_reason_d": item.get("wrong_reason_d"),
            })

        question_sets.append({
            "display_order": qs_order,
            "passage": None,
            "conversation_audio_url": qs_conv_audio,
            "scripts": qs_scripts,
            "questions": questions,
        })

    return {
        "part_type": part_type,
        "display_order": display_order,
        "question_sets": question_sets,
    }


def build_structure_part_for_api(
    part_json: Dict[str, Any],
    part_type: str,
    display_order: int,
) -> Dict[str, Any]:
    """Structure (Grammar) 1 パート分を API 用に変換."""
    questions_src = part_json.get("questions")
    if not isinstance(questions_src, list) or not questions_src:
        raise ValueError(f"Structure part JSON の questions が不正です: {part_type}")

    questions: List[Dict[str, Any]] = []
    for idx, qsrc in enumerate(questions_src, start=1):
        q = {
            "display_order": idx,
            "question_text": qsrc["question_text"],
            "choice_a": qsrc["choice_a"],
            "choice_b": qsrc["choice_b"],
            "choice_c": qsrc["choice_c"],
            "choice_d": qsrc["choice_d"],
            "correct_choice": qsrc["correct_choice"],
            "explanation": qsrc.get("explanation"),
            "tag": qsrc.get("tag"),
            "wrong_reason_a": qsrc.get("wrong_reason_a"),
            "wrong_reason_b": qsrc.get("wrong_reason_b"),
            "wrong_reason_c": qsrc.get("wrong_reason_c"),
            "wrong_reason_d": qsrc.get("wrong_reason_d"),
        }
        questions.append(q)

    return {
        "part_type": part_type,
        "display_order": display_order,
        "question_sets": [{"display_order": 1, "questions": questions}],
    }


def build_reading_section_for_api(
    reading_json: Dict[str, Any],
    display_order: int,
) -> Dict[str, Any]:
    """Reading セクションを API 用に変換."""
    passages = reading_json.get("passages")
    if not isinstance(passages, list) or not passages:
        raise ValueError("Reading JSON の passages が不正です")

    question_sets: List[Dict[str, Any]] = []
    for i, passage in enumerate(passages, start=1):
        qs_src = passage.get("questions") or []
        if not isinstance(qs_src, list) or not qs_src:
            raise ValueError(f"Reading passage[{i}] の questions が不正です")

        qs: List[Dict[str, Any]] = []
        for j, qsrc in enumerate(qs_src, start=1):
            qs.append(
                {
                    "display_order": j,
                    "question_text": qsrc["question_text"],
                    "choice_a": qsrc["choice_a"],
                    "choice_b": qsrc["choice_b"],
                    "choice_c": qsrc["choice_c"],
                    "choice_d": qsrc["choice_d"],
                    "correct_choice": qsrc["correct_choice"],
                    "explanation": qsrc.get("explanation"),
                    "tag": qsrc.get("tag"),
                    "wrong_reason_a": qsrc.get("wrong_reason_a"),
                    "wrong_reason_b": qsrc.get("wrong_reason_b"),
                    "wrong_reason_c": qsrc.get("wrong_reason_c"),
                    "wrong_reason_d": qsrc.get("wrong_reason_d"),
                }
            )
        question_sets.append(
            {"display_order": i, "passage": passage["passage"], "questions": qs}
        )

    return {
        "section_type": "reading",
        "display_order": display_order,
        "parts": [
            {
                "part_type": "passages",
                "display_order": 1,
                "question_sets": question_sets,
            }
        ],
    }


def build_mock_payload(
    full_parts: Dict[str, Dict[str, Any]],
    title: str,
    audio_url_map: Optional[Dict[str, str]] = None,
    block_starts_per_part: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, Any]:
    """
    full_parts (listening_part_a ～ reading) から MockCreate 形のペイロードを構築.
    audio_url_map: 例 {"part_a:1": "https://...", "part_b:1": "..."}. 未指定時は audio_url は None.
    """
    listening_section = {
        "section_type": "listening",
        "display_order": 1,
        "parts": [
            build_listening_part_for_api(
                part_json=full_parts["listening_part_a"],
                part_type="part_a",
                display_order=1,
                audio_url_map=audio_url_map,
                block_starts_per_part=block_starts_per_part,
            ),
            build_listening_part_for_api(
                part_json=full_parts["listening_part_b"],
                part_type="part_b",
                display_order=2,
                audio_url_map=audio_url_map,
                block_starts_per_part=block_starts_per_part,
            ),
            build_listening_part_for_api(
                part_json=full_parts["listening_part_c"],
                part_type="part_c",
                display_order=3,
                audio_url_map=audio_url_map,
                block_starts_per_part=block_starts_per_part,
            ),
        ],
    }
    structure_section = {
        "section_type": "structure",
        "display_order": 2,
        "parts": [
            build_structure_part_for_api(
                part_json=full_parts["grammar_part_a"],
                part_type="part_a",
                display_order=1,
            ),
            build_structure_part_for_api(
                part_json=full_parts["grammar_part_b"],
                part_type="part_b",
                display_order=2,
            ),
        ],
    }
    reading_section = build_reading_section_for_api(
        reading_json=full_parts["reading"],
        display_order=3,
    )
    return {
        "title": title,
        "sections": [listening_section, structure_section, reading_section],
    }


# P 系 → ExerciseCreate 用 (part_key -> section_type, part_type)
EXERCISE_PART_MAPPING: Dict[str, tuple] = {
    "listening_part_a": ("listening", "part_a"),
    "listening_part_b": ("listening", "part_b"),
    "listening_part_c": ("listening", "part_c"),
    "grammar_part_a": ("structure", "part_a"),
    "grammar_part_b": ("structure", "part_b"),
    "reading": ("reading", "passages"),
}


def build_exercise_payload(
    part_key: str,
    part_json: Dict[str, Any],
    audio_url_map: Optional[Dict[str, str]] = None,
    block_starts_per_part: Optional[Dict[str, List[int]]] = None,
) -> Dict[str, Any]:
    """
    P 系 1 パート分から ExerciseCreate 形のペイロードを構築.
    part_key: listening_part_a, listening_part_b, listening_part_c, grammar_part_a, grammar_part_b, reading.
    """
    if part_key not in EXERCISE_PART_MAPPING:
        raise ValueError(f"不明な part_key: {part_key}")
    section_type, part_type = EXERCISE_PART_MAPPING[part_key]

    if part_key == "reading":
        passages = part_json.get("passages")
        if not isinstance(passages, list) or not passages:
            raise ValueError("Reading JSON の passages が不正です")
        question_sets = []
        for i, passage in enumerate(passages, start=1):
            qs_src = passage.get("questions") or []
            if not isinstance(qs_src, list) or not qs_src:
                raise ValueError(f"Reading passage[{i}] の questions が不正です")
            qs = []
            for j, qsrc in enumerate(qs_src, start=1):
                qs.append({
                    "display_order": j,
                    "question_text": qsrc["question_text"],
                    "choice_a": qsrc["choice_a"],
                    "choice_b": qsrc["choice_b"],
                    "choice_c": qsrc["choice_c"],
                    "choice_d": qsrc["choice_d"],
                    "correct_choice": qsrc["correct_choice"],
                    "explanation": qsrc.get("explanation"),
                    "tag": qsrc.get("tag"),
                    "wrong_reason_a": qsrc.get("wrong_reason_a"),
                    "wrong_reason_b": qsrc.get("wrong_reason_b"),
                    "wrong_reason_c": qsrc.get("wrong_reason_c"),
                    "wrong_reason_d": qsrc.get("wrong_reason_d"),
                })
            question_sets.append({
                "display_order": i,
                "passage": passage["passage"],
                "audio_url": None,
                "questions": qs,
            })
        return {
            "section_type": section_type,
            "part_type": part_type,
            "question_sets": question_sets,
        }
    if part_key.startswith("listening_"):
        part = build_listening_part_for_api(
            part_json,
            part_type,
            1,
            audio_url_map=audio_url_map,
            block_starts_per_part=block_starts_per_part,
        )
        return {
            "section_type": section_type,
            "part_type": part_type,
            "question_sets": part["question_sets"],
        }
    part = build_structure_part_for_api(part_json, part_type, 1)
    question_sets = []
    for qs in part["question_sets"]:
        question_sets.append({
            "display_order": qs["display_order"],
            "passage": qs.get("passage"),
            "audio_url": qs.get("audio_url"),
            "questions": qs["questions"],
        })
    return {
        "section_type": section_type,
        "part_type": part_type,
        "question_sets": question_sets,
    }
