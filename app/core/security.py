from fastapi import Depends, Header, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings


def _get_bearer_or_x_api_key(authorization: str, x_api_key: str) -> str:
    bearer_prefix = "Bearer "
    if authorization.startswith(bearer_prefix):
        return authorization[len(bearer_prefix) :].strip()
    return (x_api_key or "").strip()


async def verify_api_key(
    authorization: str = Header(default=""),
    x_api_key: str = Header(default=""),
    settings=Depends(get_settings),
) -> None:
    """
    Horiba_based_FastAPI.md に準拠した API Key 認証（問題投入用）。

    - Authorization: Bearer <CONTENT_SOURCE_API_KEY>
    - または X-Api-Key: <CONTENT_SOURCE_API_KEY>
    """
    token = _get_bearer_or_x_api_key(authorization, x_api_key)
    if not token or token != settings.content_source_api_key:
        # 設計書準拠: 401 は { "status": "error", "errors": ["Unauthorized"] } を返す
        raise JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "errors": ["Unauthorized"]},
        )


async def verify_analysis_api_key(
    authorization: str = Header(default=""),
    x_api_key: str = Header(default=""),
    settings=Depends(get_settings),
) -> None:
    """
    分析レポート API 用の認証（問題投入とは別キー）。

    - Authorization: Bearer <ANALYSIS_API_KEY>
    - または X-Api-Key: <ANALYSIS_API_KEY>
    """
    token = _get_bearer_or_x_api_key(authorization, x_api_key)
    if not token or token != settings.analysis_api_key:
        raise JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "error", "errors": ["Unauthorized"]},
        )

