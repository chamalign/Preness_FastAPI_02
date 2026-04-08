from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1 import analysis, exercises, generation, import_content, mocks
from app.db import init_db


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
        content={"status": "error", "errors": errors or ["Validation failed"]},
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Preness Content Ingestion API",
        version="1.0.0",
    )
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # DB: analysis_jobs テーブルを作成
    init_db()

    # v1 routers
    app.include_router(mocks.router, prefix="/api/v1", tags=["mocks"])
    app.include_router(exercises.router, prefix="/api/v1", tags=["exercises"])
    app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
    app.include_router(generation.router, prefix="/api/v1")
    app.include_router(import_content.router, prefix="/api/v1")

    return app


app = create_app()
