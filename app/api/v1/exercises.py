from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import verify_api_key
from app.schemas.exercises import ExerciseCreate, ExerciseCreateResponse, ExerciseListItem
from app.services.exercise_service import (
    create_exercise_from_payload,
    get_exercise_by_id,
    list_exercises,
)


router = APIRouter()


@router.post(
    "/exercises",
    response_model=ExerciseCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_exercises(
    payload: ExerciseCreate,
    _: Any = Depends(verify_api_key),
) -> ExerciseCreateResponse:
    """
    セクション別演習の問題投入エンドポイント.
    受け取った内容を基に question_set ごとに Exercise を作成し、その ID 一覧を返す.
    """
    exercise_ids = create_exercise_from_payload(payload)
    return ExerciseCreateResponse(
        status="success",
        exercise_ids=exercise_ids,
        created_count=len(exercise_ids),
    )


@router.get(
    "/exercises",
    response_model=List[ExerciseListItem],
)
async def list_exercises_endpoint(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Any = Depends(verify_api_key),
) -> List[ExerciseListItem]:
    """Rails 同期用: Exercise 一覧を返す."""
    items = list_exercises(limit=limit, offset=offset)
    return [ExerciseListItem(**x) for x in items]


@router.get(
    "/exercises/{exercise_id}",
    response_model=ExerciseCreate,
)
async def get_exercise(
    exercise_id: int,
    _: Any = Depends(verify_api_key),
) -> ExerciseCreate:
    """Rails 同期用: 指定 exercise_id の 1 件を取得. POST リクエストスキーマと同形で返す."""
    data = get_exercise_by_id(exercise_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return ExerciseCreate(**data)

