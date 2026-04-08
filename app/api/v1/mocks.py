from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import verify_api_key
from app.schemas.mocks import MockCreate, MockCreateResponse, MockListItem
from app.services.mock_service import create_mock_from_payload, get_mock_by_id, list_mocks


router = APIRouter()


@router.post(
    "/mocks",
    response_model=MockCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mock(
    payload: MockCreate,
    _: Any = Depends(verify_api_key),
) -> MockCreateResponse:
    """
    模擬試験の問題投入エンドポイント(Notion 準拠).
    受け取った内容を FastAPI 自 DB に保存し、発番した mock_id を返す.
    """
    mock_id = create_mock_from_payload(payload)
    return MockCreateResponse(status="success", mock_id=mock_id, title=payload.title)


@router.get(
    "/mocks",
    response_model=List[MockListItem],
)
async def list_mocks_endpoint(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Any = Depends(verify_api_key),
) -> List[MockListItem]:
    """Rails 同期用: Mock 一覧を返す."""
    items = list_mocks(limit=limit, offset=offset)
    return [MockListItem(**x) for x in items]


@router.get(
    "/mocks/{mock_id}",
    response_model=MockCreate,
)
async def get_mock(
    mock_id: int,
    _: Any = Depends(verify_api_key),
) -> MockCreate:
    """Rails 同期用: 指定 mock_id の 1 件を取得. POST リクエストスキーマと同形で返す."""
    data = get_mock_by_id(mock_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock not found")
    return MockCreate(**data)

