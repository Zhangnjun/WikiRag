from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import public_router, router
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.app.log_level)
app = FastAPI(title=settings.app.name)
LOG = logging.getLogger(__name__)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"message": str(exc)})


@app.on_event("startup")
async def startup_event() -> None:
    LOG.info("WikiRag started")
    LOG.info("RAG Debug UI: http://%s:%s/rag-debug", settings.app.host, settings.app.port)
    LOG.info("Swagger UI: http://%s:%s/docs", settings.app.host, settings.app.port)
    LOG.info("Health: http://%s:%s/api/health", settings.app.host, settings.app.port)


app.include_router(public_router)
app.include_router(router)
