"""FastAPI application factory.

- create_app() builds the app: CORS, startup table creation, /api/v1 routers.
- The AI control plane router is mounted best-effort: a separate track will
  drop backend/app/ai/ in place; the API must boot with or without it.
"""

import warnings

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import automation  # noqa: F401  (registers the automation rule subscriber)
from . import models  # noqa: F401  (register models for create_all)
from .config import settings
from .database import Base, engine
from .routers import (
    agents,
    analytics,
    approvals,
    audit,
    auth,
    carriers,
    communications,
    customers,
    dispatch,
    documents,
    drivers,
    exceptions,
    feature_flags,
    integrations,
    invoices,
    lanes,
    loads,
    notifications,
    organizations,
    policies,
    rates,
    settings as settings_router,
    shipments,
    stops,
    tracking,
    users,
    vehicles,
)


def create_app() -> FastAPI:
    if settings.is_default_jwt_secret:
        warnings.warn(
            "JWT_SECRET is the default dev value 'dev-secret-change-me'. "
            "Set JWT_SECRET in the environment for any non-local deployment.",
            RuntimeWarning,
            stacklevel=2,
        )

    app = FastAPI(title="AI-Native TMS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        Base.metadata.create_all(bind=engine)
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    api_routers = [
        auth.router,
        organizations.router,
        users.router,
        customers.router,
        carriers.router,
        drivers.router,
        vehicles.router,
        loads.router,
        shipments.router,
        stops.router,
        dispatch.router,
        tracking.router,
        rates.router,
        invoices.router,
        documents.router,
        communications.router,
        exceptions.router,
        notifications.router,
        analytics.router,
        lanes.router,
        audit.router,
        policies.router,
        agents.router,
        approvals.router,
        feature_flags.router,
        integrations.router,
        settings_router.router,
    ]
    for r in api_routers:
        app.include_router(r, prefix="/api/v1")

    # AI control plane (separate track). Best-effort mount: the API must boot
    # with or without backend/app/ai/. find_spec avoids masking genuine
    # ImportErrors raised from inside the ai package itself.
    import importlib.util

    try:
        ai_spec = importlib.util.find_spec("app.ai.routes")
    except ImportError:  # parent package app.ai does not exist
        ai_spec = None
    if ai_spec is not None:
        from .ai.routes import router as ai_router

        app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
