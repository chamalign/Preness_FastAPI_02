#!/usr/bin/env python3
"""P系統 Gemini 出力ファイル (P01〜P06) を読み込み, practice パイプラインを実行する.

実行方法:
    cd /path/to/FastAPI
    python scripts/run_practice_check.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# .env を os.environ に注入してから app モジュールをインポートする.
# pydantic_settings の env_file は CWD 依存のため, 絶対パス指定で確実にロードする.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=False)

from app.services.generation.import_pipeline import process_practice_from_part_data  # noqa: E402
from app.services.generation.gemini_parser import (  # noqa: E402
    parse_p01_listening,
    parse_p04_grammar_a,
    parse_p05_grammar_b,
    parse_p06_reading,
)
from app.services.generation.reading_content import prepare_reading_for_mock  # noqa: E402

GEMINI_DIR = Path(
    "/Users/buruhamuhamu/Library/CloudStorage/"
    "GoogleDrive-kyoya.sasaki2027@gmail.com/"
    ".shortcut-targets-by-id/"
    "1B4hLNZCgAxW2SitvbUHdbY3ZD084K7NC/"
    "Preness/04_試験問題コンテンツ/問題生成/"
    "Test_output_by_Gemini/セクション別"
)

PARTS: list[tuple[str, Path, object, str]] = [
    ("listening_part_a", GEMINI_DIR / "P01.txt", parse_p01_listening, "P01"),
    ("listening_part_b", GEMINI_DIR / "P02.txt", parse_p01_listening, "P02"),
    ("listening_part_c", GEMINI_DIR / "P03.txt", parse_p01_listening, "P03"),
    ("grammar_part_a",   GEMINI_DIR / "P04.txt", parse_p04_grammar_a, "P04"),
    ("grammar_part_b",   GEMINI_DIR / "P05.txt", parse_p05_grammar_b, "P05"),
    ("reading",          GEMINI_DIR / "P06.txt", parse_p06_reading,   "P06"),
]


def main() -> None:
    errors: list[str] = []

    for part_type, path, parser, name in PARTS:
        print(f"\n{'=' * 60}")
        print(f"  {name}: {part_type}")
        print(f"{'=' * 60}")
        try:
            text = path.read_text(encoding="utf-8")
            part_data = parser(text)

            if part_type == "reading":
                passages = part_data.get("passages", [])
                print(f"  [U{{n}}] マーカー注入中 ({len(passages)} passage(s))...")
                full_parts_tmp: dict = {"reading": part_data}
                prepare_reading_for_mock(full_parts_tmp, expected_passages=len(passages))
                part_data = full_parts_tmp["reading"]

            print("  パイプライン実行中...")
            result = process_practice_from_part_data(
                part_type=part_type,
                part_data=part_data,
                audio_path_id=f"gemini-check-{name.lower()}",
            )
            print(f"  完了: {result}")
        except Exception as exc:
            msg = f"[ERROR] {name}: {exc}"
            print(f"  {msg}")
            traceback.print_exc()
            errors.append(msg)

    print(f"\n{'=' * 60}")
    if errors:
        print(f"  完了 (エラーあり: {len(errors)} / {len(PARTS)})")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  全 {len(PARTS)} パート完了")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
