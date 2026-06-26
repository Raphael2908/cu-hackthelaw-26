from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import cases, corpus, health, plans, tasks
from app.config import settings
from app.db.repo import get_repo
from app.services.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed(get_repo())  # idempotently load the corpus + associate registry on boot
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Supervision Cockpit", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Liveness mounted at both / and /api so either base works.
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api")
    app.include_router(corpus.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(plans.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    return app


app = create_app()
