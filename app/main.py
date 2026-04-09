from __future__ import annotations

from fastapi import FastAPI

from app.api.webhook import router as webhook_router
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="WhatsApp AI Assistant", version="0.1.0")
    app.include_router(webhook_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

