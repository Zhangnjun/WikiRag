from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import public_router, router
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.app.log_level)
app = FastAPI(title=settings.app.name)
LOG = logging.getLogger(__name__)
static_dir = Path(__file__).resolve().parent / "static"


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"message": str(exc)})


@app.on_event("startup")
async def startup_event() -> None:
    LOG.info("WikiRag started")
    LOG.info("Workspace Entry: http://%s:%s/rag-debug", settings.app.host, settings.app.port)
    LOG.info("Ops Workbench: http://%s:%s/ops-workbench", settings.app.host, settings.app.port)
    LOG.info("Ops Wiki Ingest: http://%s:%s/ops-wiki-ingest", settings.app.host, settings.app.port)
    LOG.info("Ops RAG Query: http://%s:%s/ops-rag-query", settings.app.host, settings.app.port)
    LOG.info("Ops Skill Profile: http://%s:%s/ops-skill-profile", settings.app.host, settings.app.port)
    LOG.info("Career Workbench: http://%s:%s/career-workbench", settings.app.host, settings.app.port)
    LOG.info("Swagger UI: http://%s:%s/docs", settings.app.host, settings.app.port)
    LOG.info("Health: http://%s:%s/api/health", settings.app.host, settings.app.port)


app.include_router(public_router)
app.include_router(router)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
