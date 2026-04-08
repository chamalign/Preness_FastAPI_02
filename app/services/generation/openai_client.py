"""OpenAI API client for problem generation (Responses API)."""

import json
import logging
import time
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRIES = 2
_RATE_LIMIT_BACKOFF_SEC = 2.0


def _load_api_config() -> Dict[str, Any]:
    """api_config.yaml を読み込む (FastAPI ルート). 無ければデフォルト dict."""
    try:
        import yaml
    except ImportError:
        return {}
    from pathlib import Path
    # FastAPI ルート: app/services/generation -> 3 段上で app, 4 段上で FastAPI
    base = Path(__file__).resolve().parent
    for _ in range(3):
        base = base.parent
    config_path = base / "api_config.yaml"
    if not config_path.is_file():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _is_temperature_unsupported_error(err: Exception) -> bool:
    msg = str(err)
    return ("temperature" in msg) and (
        "not supported" in msg.lower()
        or "unsupported parameter" in msg.lower()
        or "unrecognized" in msg.lower()
    )


def _is_insufficient_quota_error(err: Exception) -> bool:
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        e = body.get("error")
        if isinstance(e, dict) and e.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(err).lower()


def _is_retryable_rate_limit_error(err: Exception) -> bool:
    if _is_insufficient_quota_error(err):
        return False
    if getattr(err, "status_code", None) == 429:
        return True
    low = str(err).lower()
    if "rate_limit" in low or "rate limit" in low:
        return "insufficient_quota" not in low
    return False


def _request_id_from_error(err: Exception) -> Optional[str]:
    for attr in ("request_id", "requestId"):
        if hasattr(err, attr):
            v = getattr(err, attr, None)
            if v:
                return str(v)
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        rid = body.get("request_id")
        if rid:
            return str(rid)
        e = body.get("error")
        if isinstance(e, dict) and e.get("request_id"):
            return str(e["request_id"])
    return None


def _log_responses_kwargs_summary(kwargs: Dict[str, Any]) -> None:
    reasoning = kwargs.get("reasoning")
    effort = None
    if isinstance(reasoning, dict):
        effort = reasoning.get("effort")
    text_cfg = kwargs.get("text")
    verbosity = None
    if isinstance(text_cfg, dict):
        verbosity = text_cfg.get("verbosity")
    logger.debug(
        "openai responses.create summary: model=%s has_temperature=%s reasoning.effort=%s "
        "max_output_tokens=%s service_tier=%s text.verbosity=%s",
        kwargs.get("model"),
        "temperature" in kwargs,
        effort,
        kwargs.get("max_output_tokens"),
        kwargs.get("service_tier"),
        verbosity,
    )


def _responses_create_with_retries(
    client: Any,
    kwargs: Dict[str, Any],
) -> Any:
    """temperature 剥がしリトライ + レート制限のみ短いバックオフ（quota はリトライしない）."""
    for rate_attempt in range(_RATE_LIMIT_RETRIES + 1):
        kw = dict(kwargs)
        while True:
            _log_responses_kwargs_summary(kw)
            try:
                return client.responses.create(**kw)
            except Exception as e:
                if "temperature" in kw and _is_temperature_unsupported_error(e):
                    logger.info(
                        "openai responses.create: retrying without temperature (model=%s)",
                        kw.get("model"),
                    )
                    kw.pop("temperature", None)
                    continue
                if _is_insufficient_quota_error(e):
                    rid = _request_id_from_error(e)
                    logger.warning(
                        "openai insufficient_quota (no retry): request_id=%s",
                        rid,
                    )
                    raise
                if _is_retryable_rate_limit_error(e) and rate_attempt < _RATE_LIMIT_RETRIES:
                    rid = _request_id_from_error(e)
                    delay = _RATE_LIMIT_BACKOFF_SEC * (2**rate_attempt)
                    logger.warning(
                        "openai rate limit, sleeping %.1fs then retry %s/%s request_id=%s",
                        delay,
                        rate_attempt + 1,
                        _RATE_LIMIT_RETRIES,
                        rid,
                    )
                    time.sleep(delay)
                    break  # next rate_attempt, re-enter inner while with full kwargs
                raise
        # レート制限で break した場合は外側ループで再試行
    raise RuntimeError("openai responses.create: exhausted retries without result")


def _chat_completions_create(
    client: Any,
    *,
    model: str,
    prompt: str,
    timeout: float,
    temperature: Optional[float],
    max_tokens: Optional[int],
) -> str:
    kwargs_chat: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "timeout": timeout,
    }
    if temperature is not None:
        kwargs_chat["temperature"] = temperature
    if max_tokens is not None:
        kwargs_chat["max_tokens"] = max_tokens

    def _call() -> Any:
        return client.chat.completions.create(**kwargs_chat)

    try:
        response = _call()
    except Exception as e:
        if "temperature" in kwargs_chat and _is_temperature_unsupported_error(e):
            logger.info(
                "openai chat.completions: retrying without temperature (model=%s)",
                model,
            )
            kwargs_chat.pop("temperature", None)
            response = _call()
        else:
            raise
    return response.choices[0].message.content if response.choices else ""


def generate_problem_json(prompt: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    OpenAI Responses API を 1 回呼び、返却テキストを JSON パースして dict を返す.
    失敗時は例外を投げる. リトライは呼び出し側で行う.
    """
    from openai import OpenAI

    settings = get_settings()
    # 分離方針:
    # - generation はまず GENERATION_OPENAI_API_KEY
    # - 未設定なら CONTENT_SOURCE_API_KEY（Rails認証用キーと同一運用）
    # - 最終的に OPENAI_API_KEY へフォールバック（後方互換）
    api_key = (
        settings.generation_openai_api_key
        or settings.content_source_api_key
        or settings.openai_api_key
    )
    if not api_key:
        raise RuntimeError(
            "OpenAI API key is not set for generation (GENERATION_OPENAI_API_KEY / CONTENT_SOURCE_API_KEY / OPENAI_API_KEY)"
        )

    cfg = config or _load_api_config()
    client = OpenAI(api_key=api_key)
    timeout = float(cfg.get("timeout_seconds", 900))
    default_model = "gpt-5.2"

    model_name = cfg.get("model", default_model)
    reasoning = cfg.get("reasoning") if isinstance(cfg, dict) else None
    effort = None
    if isinstance(reasoning, dict):
        effort = reasoning.get("effort")

    kwargs: Dict[str, Any] = {
        "model": model_name,
        "input": [{"role": "user", "content": prompt}],
        "timeout": timeout,
    }
    if cfg.get("max_output_tokens") is not None:
        kwargs["max_output_tokens"] = cfg["max_output_tokens"]
    if cfg.get("service_tier"):
        kwargs["service_tier"] = cfg["service_tier"]
    if cfg.get("truncation"):
        kwargs["truncation"] = cfg["truncation"]
    if isinstance(reasoning, dict) and reasoning:
        kwargs["reasoning"] = reasoning
    text_block = cfg.get("text") if isinstance(cfg, dict) else None
    if isinstance(text_block, dict) and text_block:
        kwargs["text"] = text_block

    # GPT-5 系の reasoning モードでは temperature が未対応のことがあるため、
    # reasoning.effort が none でないときは temperature を渡さない（400 時は剥がして再試行もする）.
    temperature = cfg.get("temperature")
    if temperature is not None and (effort in (None, "none")):
        kwargs["temperature"] = temperature

    text: str
    try:
        response = _responses_create_with_retries(client, kwargs)
        text = getattr(response, "output_text", None) or ""
    except AttributeError:
        chat_temperature = kwargs.get("temperature")
        max_tok = kwargs.get("max_output_tokens")
        text = _chat_completions_create(
            client,
            model=kwargs.get("model", default_model),
            prompt=prompt,
            timeout=timeout,
            temperature=chat_temperature,
            max_tokens=max_tok,
        )

    text_stripped = text.strip()
    # モデルがコードフェンス（例: ```json ... ```）や前置説明を付けるケースがあるため、
    # JSON先頭「{」〜末尾「}」を抽出してパースする。
    start = text_stripped.find("{")
    end = text_stripped.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"API が JSON を返しませんでした (先頭: {text_stripped[:80]!r})")
    json_text = text_stripped[start : end + 1]
    return json.loads(json_text)
