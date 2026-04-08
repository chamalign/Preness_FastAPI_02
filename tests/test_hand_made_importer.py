from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from app.services.hand_made_importer import (
    build_full_parts_payload,
    build_practice_part_payload_from_file,
    load_json_txt,
    pick_unused_reading_file,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_json_txt_fullmock_grammar_b() -> None:
    path = REPO_ROOT / "hand_made" / "Full_Mock" / "05_Grammar_B.txt"
    obj = load_json_txt(path)
    assert "questions" in obj
    assert isinstance(obj["questions"], list)
    assert obj["questions"], "questions should not be empty"


def test_load_json_txt_reading_short() -> None:
    path = REPO_ROOT / "hand_made" / "Excecise" / "Reading_Short" / "01_Reading_short.txt"
    obj = load_json_txt(path)
    assert "passages" in obj
    assert isinstance(obj["passages"], list)
    assert obj["passages"], "passages should not be empty"


def test_build_full_parts_payload_shape() -> None:
    set_dir = REPO_ROOT / "hand_made" / "Full_Mock"
    payload = build_full_parts_payload(set_dir, kind="full")
    assert payload["title"]  # normalized or set_dir.name
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


def test_build_practice_payload_listening_b_fix_applied() -> None:
    path = REPO_ROOT / "hand_made" / "Excecise" / "Listening_B" / "01_Listening_B.txt"
    payload = build_practice_part_payload_from_file(path)
    assert payload["part_type"] == "listening_part_b"

    part_data = payload["part_data"]
    assert "items" in part_data
    assert isinstance(part_data["items"], list)

    dumped = json.dumps(part_data, ensure_ascii=False)
    assert "Question [number]." not in dumped
    assert "[question_text]" not in dumped


def test_pick_unused_reading_file_excludes_used(tmp_path: Path) -> None:
    short_dir = REPO_ROOT / "hand_made" / "Excecise" / "Reading_Short"
    long_dir = REPO_ROOT / "hand_made" / "Excecise" / "Reading_Long"
    candidates = sorted(list(short_dir.glob("*.txt")) + list(long_dir.glob("*.txt")))
    assert len(candidates) >= 2

    # 最後の候補だけ unused にする
    unused = candidates[-1]
    used = candidates[:-1]

    record_path = tmp_path / "used_reading.json"
    used_rel = [str(p.relative_to(REPO_ROOT)) for p in used]
    record_path.write_text(json.dumps({"used": used_rel}, ensure_ascii=False), encoding="utf-8")

    chosen = pick_unused_reading_file(
        reading_short_dir=short_dir,
        reading_long_dir=long_dir,
        repo_root=REPO_ROOT,
        record_path=record_path,
        rng=random.Random(0),
        allow_all_if_exhausted=False,
        mark_used=True,
    )

    assert chosen == unused
    written = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(written["used"], list)
    assert str(unused.relative_to(REPO_ROOT)) in written["used"]
