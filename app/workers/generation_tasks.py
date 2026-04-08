"""Celery task: FM / SM / P 系の生成を非同期実行."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from app.db import get_db, init_db
from app.db.models import GenerationJob
from app.services.generation import (
    get_fm_prompt_stems,
    get_sm_prompt_stems,
    get_p_stem_for_part_type,
    load_prompt,
    generate_problem_json,
    merge_fm06,
    merge_full_mock_parts,
    merge_short_mock_parts,
    process_mock_from_full_parts,
    process_practice_from_part_data,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# FM stem -> full_parts キー対応 (7 本中 FM06 は Long3+Short2 をマージ)
FM_STEM_TO_KEY = {
    "FM01_Listening_Part_A": "listening_part_a",
    "FM02_Listening_Part_B": "listening_part_b",
    "FM03_Listening_Part_C": "listening_part_c",
    "FM04_Grammar_Part_A": "grammar_part_a",
    "FM05_Grammar_Part_B": "grammar_part_b",
    "FM06_Reading_Long3": "_long3",
    "FM06_Reading_Short2": "_short2",
}


def _update_job_status(job_id: uuid.UUID, status: str, result: dict | None = None, error_message: str | None = None) -> None:
    """GenerationJob の status / result / error_message / completed_at を更新."""
    with get_db() as session:
        job = session.get(GenerationJob, job_id)
        if not job:
            return
        job.status = status
        if result is not None:
            job.result = result
        if error_message is not None:
            job.error_message = error_message
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc)


@celery_app.task(bind=True)
def run_full_mock_generation(self, title: str, job_id: str) -> None:
    """
    7 本プロンプトで生成 → FM06 マージ → full_parts → 音声→S3 → payload → DB 保存.
    job_id は UUID 文字列. 完了時に GenerationJob を更新する.
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        logger.error("Invalid job_id: %s", job_id)
        return

    # ワーカー単体起動でも DB スキーマ/拡張を揃え, 状態を確実に更新する
    init_db()
    _update_job_status(uid, "running")

    parts_raw: dict = {}
    stems = get_fm_prompt_stems()

    for stem in stems:
        for attempt in range(2):
            try:
                prompt = load_prompt(stem)
                data = generate_problem_json(prompt)
                if stem == "FM06_Reading_Long3":
                    parts_raw["_long3"] = data
                elif stem == "FM06_Reading_Short2":
                    parts_raw["_short2"] = data
                else:
                    key = FM_STEM_TO_KEY.get(stem)
                    if key:
                        parts_raw[key] = data
                break
            except Exception as e:
                logger.warning("Attempt %s failed for %s: %s", attempt + 1, stem, e)
                if attempt == 0:
                    continue
                _update_job_status(uid, "failed", error_message=f"Generation failed for {stem}: {e}")
                return

    if "_long3" not in parts_raw or "_short2" not in parts_raw:
        _update_job_status(uid, "failed", error_message="FM06 Long3 or Short2 missing")
        return

    try:
        fm06_reading = merge_fm06(parts_raw["_long3"], parts_raw["_short2"])
    except ValueError as e:
        _update_job_status(uid, "failed", error_message=str(e))
        return

    full_parts = merge_full_mock_parts(
        parts_raw["listening_part_a"],
        parts_raw["listening_part_b"],
        parts_raw["listening_part_c"],
        parts_raw["grammar_part_a"],
        parts_raw["grammar_part_b"],
        fm06_reading,
    )

    try:
        result = process_mock_from_full_parts(
            full_parts=full_parts,
            title=title,
            audio_path_id=job_id,
        )
    except Exception as e:
        logger.exception("Full Mock processing failed: %s", e)
        _update_job_status(uid, "failed", error_message=str(e))
        return

    _update_job_status(uid, "completed", result=result)
    logger.info("Full Mock generation completed: job_id=%s mock_id=%s", job_id, result.get("mock_id"))


SM_STEM_TO_KEY = {
    "SM01_Listening_Part_A": "listening_part_a",
    "SM02_Listening_Part_B": "listening_part_b",
    "SM03_Listening_Part_C": "listening_part_c",
    "SM04_Grammar_Part_A": "grammar_part_a",
    "SM05_Grammar_Part_B": "grammar_part_b",
    "SM06_Reading": "reading",
}


@celery_app.task(bind=True)
def run_short_mock_generation(self, title: str, job_id: str) -> None:
    """6 本プロンプトで SM 生成 → full_parts → 音声→S3 → payload → DB 保存."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        logger.error("Invalid job_id: %s", job_id)
        return

    # ワーカー単体起動でも DB スキーマ/拡張を揃え, 状態を確実に更新する
    init_db()
    _update_job_status(uid, "running")

    parts_raw: dict = {}
    stems = get_sm_prompt_stems()

    for stem in stems:
        for attempt in range(2):
            try:
                prompt = load_prompt(stem)
                data = generate_problem_json(prompt)
                key = SM_STEM_TO_KEY.get(stem)
                if key:
                    parts_raw[key] = data
                break
            except Exception as e:
                logger.warning("Attempt %s failed for %s: %s", attempt + 1, stem, e)
                if attempt == 0:
                    continue
                _update_job_status(uid, "failed", error_message=f"Generation failed for {stem}: {e}")
                return

    if len(parts_raw) != 6:
        _update_job_status(uid, "failed", error_message="SM 6 パートが揃いません")
        return

    full_parts = merge_short_mock_parts(
        parts_raw["listening_part_a"],
        parts_raw["listening_part_b"],
        parts_raw["listening_part_c"],
        parts_raw["grammar_part_a"],
        parts_raw["grammar_part_b"],
        parts_raw["reading"],
    )

    try:
        result = process_mock_from_full_parts(
            full_parts=full_parts,
            title=title,
            audio_path_id=job_id,
        )
    except Exception as e:
        logger.exception("Short Mock processing failed: %s", e)
        _update_job_status(uid, "failed", error_message=str(e))
        return

    _update_job_status(uid, "completed", result=result)
    logger.info("Short Mock generation completed: job_id=%s mock_id=%s", job_id, result.get("mock_id"))


@celery_app.task(bind=True)
def run_practice_generation(self, part_type: str, job_id: str) -> None:
    """
    P 系 1 パート生成 → (Listening なら音声→S3) → ExerciseCreate → DB 保存.
    part_type: listening_part_a, listening_part_b, listening_part_c, grammar_part_a, grammar_part_b, reading.
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        logger.error("Invalid job_id: %s", job_id)
        return

    # ワーカー単体起動でも DB スキーマ/拡張を揃え, 状態を確実に更新する
    init_db()
    _update_job_status(uid, "running")

    try:
        stem = get_p_stem_for_part_type(part_type)
    except ValueError as e:
        _update_job_status(uid, "failed", error_message=str(e))
        return

    data = None
    for attempt in range(2):
        try:
            prompt = load_prompt(stem)
            data = generate_problem_json(prompt)
            break
        except Exception as e:
            logger.warning("Attempt %s failed for %s: %s", attempt + 1, stem, e)
            if attempt == 1:
                _update_job_status(uid, "failed", error_message=f"Generation failed for {stem}: {e}")
                return
    if data is None:
        _update_job_status(uid, "failed", error_message="Generation returned no data")
        return

    try:
        result = process_practice_from_part_data(
            part_type=part_type,
            part_data=data,
            audio_path_id=job_id,
        )
    except Exception as e:
        logger.exception("Practice processing failed: %s", e)
        _update_job_status(uid, "failed", error_message=str(e))
        return

    _update_job_status(uid, "completed", result=result)
    logger.info(
        "Practice generation completed: job_id=%s part_type=%s exercise_ids=%s",
        job_id,
        part_type,
        result.get("exercise_ids"),
    )
