"""Load FM / SM / P generation prompts from prompts/completed."""

import random
from pathlib import Path
from typing import List, Tuple

from app.core.config import get_settings

# FM 用 7 本: FM01～FM05, FM06_Reading_Long3, FM06_Reading_Short2
FM_PROMPT_STEMS = [
    "FM01_Listening_Part_A",
    "FM02_Listening_Part_B",
    "FM03_Listening_Part_C",
    "FM04_Grammar_Part_A",
    "FM05_Grammar_Part_B",
    "FM06_Reading_Long3",
    "FM06_Reading_Short2",
]

# SM 用 6 本: SM01～SM06 (SM06 は 1 本)
SM_PROMPT_STEMS = [
    "SM01_Listening_Part_A",
    "SM02_Listening_Part_B",
    "SM03_Listening_Part_C",
    "SM04_Grammar_Part_A",
    "SM05_Grammar_Part_B",
    "SM06_Reading",
]

# P 系: P01～P05 + P06 は Long/Short の 2 プロンプトからランダム選択
P_PROMPT_STEMS = [
    "P01_Listening_Part_A",
    "P02_Listening_Part_B",
    "P03_Listening_Part_C",
    "P04_Grammar_Part_A",
    "P05_Grammar_Part_B",
    "P06_Reading_Long",
    "P06_Reading_Short",
]

# part_type (API) -> stem
P_PART_TYPE_TO_STEM = {
    "listening_part_a": "P01_Listening_Part_A",
    "listening_part_b": "P02_Listening_Part_B",
    "listening_part_c": "P03_Listening_Part_C",
    "grammar_part_a": "P04_Grammar_Part_A",
    "grammar_part_b": "P05_Grammar_Part_B",
    "reading": None,  # P06: ランダムで Long または Short
}


def get_fm_prompt_stems() -> List[str]:
    """FM 用プロンプトの stem 一覧 (7 本)."""
    return list(FM_PROMPT_STEMS)


def get_sm_prompt_stems() -> List[str]:
    """SM 用プロンプトの stem 一覧 (6 本)."""
    return list(SM_PROMPT_STEMS)


def get_p_prompt_stems() -> List[str]:
    """P 用プロンプトの stem 一覧 (P01～P05 + P06_Long, P06_Short)."""
    return list(P_PROMPT_STEMS)


def get_p_stem_for_part_type(part_type: str) -> str:
    """P 系で part_type に対応する stem を返す. reading の場合は Long/Short をランダムに選ぶ."""
    stem = P_PART_TYPE_TO_STEM.get(part_type)
    if stem is not None:
        return stem
    if part_type == "reading":
        return random.choice(["P06_Reading_Long", "P06_Reading_Short"])
    raise ValueError(f"不明な part_type: {part_type}")


def get_fm_prompt_paths() -> List[Tuple[str, Path]]:
    """(stem, Path) のリスト。get_settings().generation_prompts_dir をスキャンし FM*.txt を返す."""
    settings = get_settings()
    base = Path(settings.generation_prompts_dir)
    if not base.is_dir():
        return []
    result = []
    for stem in FM_PROMPT_STEMS:
        path = base / f"{stem}.txt"
        if path.is_file():
            result.append((stem, path))
    return result


def load_prompt(stem: str) -> str:
    """指定 stem の .txt 内容を UTF-8 で読み込む."""
    settings = get_settings()
    path = Path(settings.generation_prompts_dir) / f"{stem}.txt"
    if not path.is_file():
        raise ValueError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
