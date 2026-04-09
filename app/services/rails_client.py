"""Rails API へコンテンツを POST 転送するクライアント."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RailsPostError(ValueError):
    """Rails への POST が失敗したときに投げる."""


def _raise_for_status(response: httpx.Response, endpoint: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:800] if e.response.text else ""
        logger.warning(
            "Rails %s failed: status=%s body=%s",
            endpoint,
            e.response.status_code,
            body,
        )
        raise RailsPostError(
            f"Rails {endpoint} failed: status={e.response.status_code} body={body}"
        ) from e


def _get_headers() -> Dict[str, str]:
    settings = get_settings()
    token = settings.rails_api_key or settings.content_source_api_key
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def post_mock_to_rails(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """模擬試験を Rails に POST 転送する. RAILS_API_BASE_URL 未設定時はスキップ."""
    settings = get_settings()
    if not settings.rails_api_base_url:
        return None

    url = f"{settings.rails_api_base_url.rstrip('/')}/api/v1/mocks"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=_get_headers())
            _raise_for_status(response, "POST /api/v1/mocks")
            result = response.json()
            logger.info("Rails mock registered: %s", result)
            return result
    except RailsPostError:
        raise
    except Exception as e:
        logger.warning("Rails POST /api/v1/mocks error: %s", e)
        raise RailsPostError(f"Rails POST /api/v1/mocks error: {e}") from e


def post_exercise_to_rails(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """演習問題を Rails に POST 転送する. RAILS_API_BASE_URL 未設定時はスキップ."""
    settings = get_settings()
    if not settings.rails_api_base_url:
        return None

    url = f"{settings.rails_api_base_url.rstrip('/')}/api/v1/exercises"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=_get_headers())
            _raise_for_status(response, "POST /api/v1/exercises")
            result = response.json()
            logger.info("Rails exercise registered: %s", result)
            return result
    except RailsPostError:
        raise
    except Exception as e:
        logger.warning("Rails POST /api/v1/exercises error: %s", e)
        raise RailsPostError(f"Rails POST /api/v1/exercises error: {e}") from e
