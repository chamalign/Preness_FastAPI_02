import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import analysis, exercises, generation, import_content, mocks
from app.db import init_db

logger = logging.getLogger(__name__)

# 既知の例外クラス名 → 日本語ラベル対応表
_KNOWN_ERROR_LABELS: dict[str, str] = {
    "APIConnectionError": "OpenAI APIへの接続に失敗しました",
    "APITimeoutError": "OpenAI APIがタイムアウトしました",
    "RateLimitError": "OpenAI APIのレート制限に達しました",
    "InternalServerError": "OpenAI サーバーでエラーが発生しました",
    "ValidationError": "レスポンスの型変換に失敗しました",
    "OperationalError": "データベース接続エラー",
    "IntegrityError": "データベースの制約違反が発生しました",
    "ClientError": "外部ストレージへの接続に失敗しました",
}


def _format_exc(exc: Exception) -> str:
    """例外を「日本語ラベル: 英語詳細」または「[クラス名] メッセージ」にフォーマットする."""
    class_name = type(exc).__name__
    label = _KNOWN_ERROR_LABELS.get(class_name)
    detail = str(exc)
    if label:
        return f"{label}: {detail}" if detail else label
    return f"[{class_name}] {detail}"


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """API 仕様に合わせて 422 を { status: 'error', errors: [...] } で返す."""
    errors = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x != "body")
        msg = e.get("msg", "")
        errors.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={"status": "error", "errors": errors or ["バリデーションに失敗しました"]},
    )


async def internal_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """未捕捉の例外をすべて受け取り、構造化された 500 レスポンスを返す."""
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    logger.exception("未捕捉の例外が発生しました: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "errors": [_format_exc(exc)]},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Preness Content Ingestion API",
        version="1.0.0",
    )
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, internal_exception_handler)

    # DB: analysis_jobs テーブルを作成
    init_db()

    app.include_router(mocks.router, prefix="/api/v1", tags=["mocks"])
    app.include_router(exercises.router, prefix="/api/v1", tags=["exercises"])
    app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
    app.include_router(generation.router, prefix="/api/v1")
    app.include_router(import_content.router, prefix="/api/v1")

    return app


app = create_app()
