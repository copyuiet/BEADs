"""MARD 拼豆图纸生成器 FastAPI 应用入口。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import artworks, auth, chat, export, generate, upload
from backend.core.services import ApplicationServices
from backend.models.schemas import HealthResponse


def create_app(runtime_root: str | Path | None = None) -> FastAPI:
    services = ApplicationServices.create(runtime_root)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services.palettes.get("mard_221")
        services.palettes.get("mard_291")
        services.database.initialise()
        services.tokens.initialise()
        yield

    application = FastAPI(
        title="MARD 拼豆图纸生成器 API",
        version="1.0.0",
        description="基于真实 MARD 色卡生成可制作的拼豆图纸。",
        lifespan=lifespan,
    )
    application.state.services = services

    origins = [
        item.strip()
        for item in os.getenv(
            "BEAD_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    application.include_router(auth.router, prefix="/api")
    application.include_router(upload.router, prefix="/api")
    application.include_router(generate.router, prefix="/api")
    application.include_router(export.router, prefix="/api")
    application.include_router(artworks.router, prefix="/api")
    application.include_router(chat.router, prefix="/api")

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", palettes=len(services.palettes.available()))

    return application


app = create_app()


__all__ = ["app", "create_app"]
