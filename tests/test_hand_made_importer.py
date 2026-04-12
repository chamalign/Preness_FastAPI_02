from __future__ import annotations

import json
import random
from pathlib import Path

from app.services.hand_made_importer import (
    build_full_parts_payload,
    build_practice_part_payload_from_file,
    load_json_txt,
    pick_unused_reading_file,
)


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def test_load_json_txt_fullmock_grammar_b(tmp_path: Path) -> None:
    path = tmp_path / "05_Grammar_B.txt"
    _write_json(
        path,
        {
            "questions": [
                {
                    "question_text": "Q1",
                    "choice_a": "a",
                    "choice_b": "b",
                    "choice_c": "c",
                    "choice_d": "d",
                    "correct_choice": "a",
                }
            ]
        },
    )
    obj = load_json_txt(path)
    assert "questions" in obj
    assert isinstance(obj["questions"], list)
    assert obj["questions"], "questions should not be empty"


def test_load_json_txt_reading_short(tmp_path: Path) -> None:
    path = tmp_path / "01_Reading_short.txt"
    _write_json(
        path,
        {
            "passages": [
                {
                    "passage": "p1",
                    "questions": [
                        {
                            "question_text": "q",
                            "choice_a": "a",
                            "choice_b": "b",
                            "choice_c": "c",
                            "choice_d": "d",
                            "correct_choice": "a",
                        }
                    ],
                }
            ]
        },
    )
    obj = load_json_txt(path)
    assert "passages" in obj
    assert isinstance(obj["passages"], list)
    assert obj["passages"], "passages should not be empty"


def test_build_full_parts_payload_shape(tmp_path: Path) -> None:
    set_dir = tmp_path / "Full_Mock"
    set_dir.mkdir()
    _write_json(set_dir / "01_Listening_A.txt", {"items": []})
    _write_json(set_dir / "02_Listening_B.txt", {"items": []})
    _write_json(set_dir / "03_Listening_C.txt", {"items": []})
    _write_json(set_dir / "04_Grammar_A.txt", {"questions": []})
    _write_json(set_dir / "05_Grammar_B.txt", {"questions": [{"question_text": "x"}]})
    _write_json(
        set_dir / "06_Reading.txt",
        {"passages": [{"passage": "p", "questions": [{"question_text": "q"}]}]},
    )

    payload = build_full_parts_payload(set_dir, kind="full")
    assert payload["title"]
    full_parts = payload["full_parts"]
    assert set(full_parts.keys()) == {
        "listening_part_a",
        "listening_part_b",
        "listening_part_c",
        "grammar_part_a",
        "grammar_part_b",
        "reading",
    }
    assert "passages" in full_parts["reading"]


def test_build_practice_payload_listening_b_fix_applied(tmp_path: Path) -> None:
    part_dir = tmp_path / "Listening_B"
    part_dir.mkdir()
    path = part_dir / "01_Listening_B.txt"
    _write_json(
        path,
        {
            "items": [
                {
                    "question_text": "Actual question?",
                    "choice_a": "a",
                    "choice_b": "b",
                    "choice_c": "c",
                    "choice_d": "d",
                    "correct_choice": "a",
                    "content": {
                        "listening_script": [
                            {"speaker": "narrator", "text": "Question [number]."},
                            {"speaker": "narrator", "text": "[question_text]"},
                        ]
                    },
                }
            ]
        },
    )
    payload = build_practice_part_payload_from_file(path)
    assert payload["part_type"] == "listening_part_b"

    part_data = payload["part_data"]
    assert "items" in part_data
    assert isinstance(part_data["items"], list)

    dumped = json.dumps(part_data, ensure_ascii=False)
    assert "Question [number]." not in dumped
    assert "[question_text]" not in dumped


def test_pick_unused_reading_file_excludes_used(tmp_path: Path) -> None:
    short_dir = tmp_path / "Reading_Short"
    long_dir = tmp_path / "Reading_Long"
    short_dir.mkdir()
    long_dir.mkdir()
    f1 = short_dir / "a.txt"
    f2 = short_dir / "b.txt"
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("{}", encoding="utf-8")

    candidates = sorted(list(short_dir.glob("*.txt")) + list(long_dir.glob("*.txt")))
    assert len(candidates) >= 2

    unused = candidates[-1]
    used = candidates[:-1]

    record_path = tmp_path / "used_reading.json"
    used_rel = [str(p.relative_to(tmp_path)) for p in used]
    record_path.write_text(json.dumps({"used": used_rel}, ensure_ascii=False), encoding="utf-8")

    chosen = pick_unused_reading_file(
        reading_short_dir=short_dir,
        reading_long_dir=long_dir,
        repo_root=tmp_path,
        record_path=record_path,
        rng=random.Random(0),
        allow_all_if_exhausted=False,
        mark_used=True,
    )

    assert chosen == unused
    written = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(written["used"], list)
    assert str(unused.relative_to(tmp_path)) in written["used"]
