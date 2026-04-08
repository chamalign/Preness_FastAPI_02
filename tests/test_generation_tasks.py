import inspect
import uuid
from typing import Any, Callable
from unittest.mock import Mock

from app.workers.generation_tasks import run_full_mock_generation, run_practice_generation


def _invoke_celery_task(task: Any, /, **kwargs: Any) -> Any:
    """
    Celery Task オブジェクトをユニットテストから呼ぶための薄いラッパー.
    `task.run` に self 引数が必要かをシグネチャで判定して呼び分ける.
    """
    run = getattr(task, "run", None)
    if run is None:
        raise AssertionError("Task has no run()")

    params = list(inspect.signature(run).parameters.keys())
    if params and params[0] in ("self", "task"):
        return run(None, **kwargs)
    return run(**kwargs)


def test_full_generation_sets_running_then_completed(monkeypatch) -> None:
    job_id = str(uuid.uuid4())
    update_mock = Mock()

    # status 更新だけを検証する
    monkeypatch.setattr("app.workers.generation_tasks._update_job_status", update_mock)
    monkeypatch.setattr("app.workers.generation_tasks.init_db", Mock())

    monkeypatch.setattr(
        "app.workers.generation_tasks.get_fm_prompt_stems",
        lambda: [
            "FM01_Listening_Part_A",
            "FM02_Listening_Part_B",
            "FM03_Listening_Part_C",
            "FM04_Grammar_Part_A",
            "FM05_Grammar_Part_B",
            "FM06_Reading_Long3",
            "FM06_Reading_Short2",
        ],
    )
    monkeypatch.setattr("app.workers.generation_tasks.load_prompt", lambda stem: f"prompt:{stem}")
    monkeypatch.setattr("app.workers.generation_tasks.generate_problem_json", lambda prompt: {})

    monkeypatch.setattr("app.workers.generation_tasks.merge_fm06", lambda long3, short2: {"passages": []})
    monkeypatch.setattr("app.workers.generation_tasks.merge_full_mock_parts", lambda *args: {})
    monkeypatch.setattr(
        "app.workers.generation_tasks.process_mock_from_full_parts",
        lambda full_parts, title, audio_path_id: {"mock_id": 123},
    )

    _invoke_celery_task(run_full_mock_generation, title="T", job_id=job_id)

    # running -> completed の順に更新されること
    assert update_mock.call_count >= 2
    assert update_mock.call_args_list[0].args[1] == "running"
    assert update_mock.call_args_list[-1].args[1] == "completed"


def test_practice_none_marks_failed(monkeypatch) -> None:
    job_id = str(uuid.uuid4())
    update_mock = Mock()

    monkeypatch.setattr("app.workers.generation_tasks._update_job_status", update_mock)
    monkeypatch.setattr("app.workers.generation_tasks.init_db", Mock())

    monkeypatch.setattr("app.workers.generation_tasks.get_p_stem_for_part_type", lambda part_type: "P01_Listening_Part_A")
    monkeypatch.setattr("app.workers.generation_tasks.load_prompt", lambda stem: f"prompt:{stem}")
    monkeypatch.setattr("app.workers.generation_tasks.generate_problem_json", lambda prompt: None)

    process_mock = Mock()
    monkeypatch.setattr("app.workers.generation_tasks.process_practice_from_part_data", process_mock)

    _invoke_celery_task(run_practice_generation, part_type="listening_part_a", job_id=job_id)

    assert update_mock.call_count == 2
    assert update_mock.call_args_list[0].args[1] == "running"
    assert update_mock.call_args_list[1].args[1] == "failed"
    assert update_mock.call_args_list[1].kwargs.get("error_message") == "Generation returned no data"
    process_mock.assert_not_called()

