"""Rails API へコンテンツを POST 転送するクライアント."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_headers() -> Dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.content_source_api_key}",
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
            response.raise_for_status()
            result = response.json()
            logger.info("Rails mock registered: %s", result)
            return result
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Rails POST /api/v1/mocks failed: status=%s body=%s",
            e.response.status_code,
            e.response.text[:500],
        )
    except Exception as e:
        logger.warning("Rails POST /api/v1/mocks error: %s", e)
    return None


def post_exercise_to_rails(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """演習問題を Rails に POST 転送する. RAILS_API_BASE_URL 未設定時はスキップ."""
    settings = get_settings()
    if not settings.rails_api_base_url:
        return None

    url = f"{settings.rails_api_base_url.rstrip('/')}/api/v1/exercises"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=_get_headers())
            response.raise_for_status()
            result = response.json()
            logger.info("Rails exercise registered: %s", result)
            return result
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Rails POST /api/v1/exercises failed: status=%s body=%s",
            e.response.status_code,
            e.response.text[:500],
        )
    except Exception as e:
        logger.warning("Rails POST /api/v1/exercises error: %s", e)
    return None
