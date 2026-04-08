"""Problem generation services: prompts, OpenAI, merge, payload."""

from app.services.generation.prompt_loader import (
    get_fm_prompt_stems,
    get_sm_prompt_stems,
    get_p_stem_for_part_type,
    load_prompt,
    get_fm_prompt_paths,
)
from app.services.generation.openai_client import generate_problem_json
from app.services.generation.fm06_merger import merge_fm06
from app.services.generation.full_mock_merger import merge_full_mock_parts
from app.services.generation.short_mock_merger import merge_short_mock_parts
from app.services.generation.payload_builder import build_mock_payload, build_exercise_payload
from app.services.generation.import_pipeline import (
    process_mock_from_full_parts,
    process_practice_from_part_data,
)

__all__ = [
    "get_fm_prompt_stems",
    "get_sm_prompt_stems",
    "get_p_stem_for_part_type",
    "get_fm_prompt_paths",
    "load_prompt",
    "generate_problem_json",
    "merge_fm06",
    "merge_full_mock_parts",
    "merge_short_mock_parts",
    "build_mock_payload",
    "build_exercise_payload",
    "process_mock_from_full_parts",
    "process_practice_from_part_data",
]
