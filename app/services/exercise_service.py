"""Exercise (セクション別演習) の DB 保存サービス."""
from typing import Any, Dict, List, Optional

from app.db import get_db
from app.db.models import Exercise, ExerciseQuestion, ExerciseQuestionSet
from app.schemas.exercises import ExerciseCreate


def _scripts_for_db(scripts: Any) -> Any:
    """Pydantic ScriptTurn または dict のリストを JSON 保存用の list[dict] にする."""
    if scripts is None:
        return None
    out: List[Any] = []
    for t in scripts:
        if hasattr(t, "model_dump"):
            out.append(t.model_dump())
        elif isinstance(t, dict):
            out.append(t)
        else:
            out.append(dict(t))
    return out


def _exercise_orm_to_dict(exercise: Exercise) -> Dict[str, Any]:
    """ORM Exercise を API レスポンス用の辞書（ExerciseCreate 同形）に変換."""
    question_sets = []
    for qs in exercise.question_sets:
        questions = []
        for q in qs.questions:
            questions.append({
                "display_order": q.display_order,
                "question_text": q.question_text,
                "question_audio_url": q.audio_url,
                "choice_a": q.choice_a,
                "choice_b": q.choice_b,
                "choice_c": q.choice_c,
                "choice_d": q.choice_d,
                "correct_choice": q.correct_choice,
                "explanation": q.explanation,
                "tag": q.tag,
                "wrong_reason_a": q.wrong_reason_a,
                "wrong_reason_b": q.wrong_reason_b,
                "wrong_reason_c": q.wrong_reason_c,
                "wrong_reason_d": q.wrong_reason_d,
                "scripts": q.scripts,
            })
        question_sets.append({
            "display_order": qs.display_order,
            "passage": qs.passage,
            "conversation_audio_url": qs.audio_url,
            "questions": questions,
        })
    return {
        "section_type": exercise.section_type,
        "part_type": exercise.part_type,
        "question_sets": question_sets,
    }


def list_exercises(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Exercise 一覧を id 降順で返す."""
    with get_db() as session:
        rows = (
            session.query(Exercise)
            .order_by(Exercise.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [
            {"id": e.id, "section_type": e.section_type, "part_type": e.part_type}
            for e in rows
        ]


def get_exercise_by_id(exercise_id: int) -> Optional[Dict[str, Any]]:
    """exercise_id で 1 件取得. 存在しなければ None."""
    with get_db() as session:
        exercise = session.get(Exercise, exercise_id)
        if exercise is None:
            return None
        return _exercise_orm_to_dict(exercise)


def create_exercise_from_payload(payload: ExerciseCreate) -> List[int]:
    """
    ExerciseCreate を基に、question_set ごとに 1 件の Exercise を作成し、
    発番した exercise_id の一覧を返す.
    """
    created_ids: List[int] = []
    with get_db() as session:
        for qs in payload.question_sets:
            exercise = Exercise(
                section_type=payload.section_type,
                part_type=payload.part_type,
            )
            session.add(exercise)
            session.flush()

            eqs = ExerciseQuestionSet(
                exercise_id=exercise.id,
                display_order=qs.display_order,
                passage=qs.passage,
                audio_url=qs.conversation_audio_url,
            )
            session.add(eqs)
            session.flush()

            for q in qs.questions:
                eq = ExerciseQuestion(
                    exercise_question_set_id=eqs.id,
                    display_order=q.display_order,
                    question_text=q.question_text,
                    audio_url=q.question_audio_url,
                    choice_a=q.choice_a,
                    choice_b=q.choice_b,
                    choice_c=q.choice_c,
                    choice_d=q.choice_d,
                    correct_choice=q.correct_choice,
                    explanation=q.explanation,
                    tag=q.tag,
                    wrong_reason_a=q.wrong_reason_a,
                    wrong_reason_b=q.wrong_reason_b,
                    wrong_reason_c=q.wrong_reason_c,
                    wrong_reason_d=q.wrong_reason_d,
                    scripts=_scripts_for_db(q.scripts),
                )
                session.add(eq)

            created_ids.append(exercise.id)

    return created_ids
