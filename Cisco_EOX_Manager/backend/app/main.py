from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_autopop import router as autopop_router
from app.api.routes_eox import router as eox_router
from app.api.routes_export import router as export_router
from app.api.routes_logs import router as logs_router
from app.api.routes_setup import router as setup_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, get_logger
from app.db.session import check_db_connection, init_db
from app.services.autopop_jobs import mark_stale_jobs
from app.schemas import HealthResponse

settings = get_settings()
logger = get_logger("eox_manager.main")
PRODUCT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PRODUCT_ROOT / "front_end" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

app = FastAPI(
    title=settings.app_name,
    description="Standalone Cisco EOX product with PostgreSQL/SQLite DB-first persistence, controlled scraper flow, React UI, and GraphQL DB retrieval.",
    version="1.0.0",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if not settings.auto_create_tables:
        return
    try:
        init_db()
        mark_stale_jobs()
        logger.info("Database tables are ready")
    except Exception as exc:
        # Keep the API process alive so /api/setup/status can show the DB error.
        logger.warning("Database initialization failed: %s", exc)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    ready, error = check_db_connection()
    return HealthResponse(database_ready=ready, database_error=error)


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def api_health() -> HealthResponse:
    ready, error = check_db_connection()
    return HealthResponse(database_ready=ready, database_error=error)


app.include_router(autopop_router, prefix=settings.api_prefix)
app.include_router(setup_router, prefix=settings.api_prefix)
app.include_router(eox_router, prefix=settings.api_prefix)
app.include_router(export_router, prefix=settings.api_prefix)
app.include_router(logs_router, prefix=settings.api_prefix)

try:
    from strawberry.fastapi import GraphQLRouter
    from app.graphql.schema import schema as graphql_schema

    app.include_router(GraphQLRouter(graphql_schema), prefix="/graphql", tags=["GraphQL"])
except Exception as exc:  # pragma: no cover - optional dependency guard
    logger.warning("GraphQL route disabled: %s", exc)

if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="frontend-assets")


@app.get("/", include_in_schema=False)
def serve_frontend_or_status():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return {
        "status": "ok",
        "service": settings.app_name,
        "frontend": "React build not found. Run: cd front_end && npm install && npm run build",
        "api_docs": "/docs",
        "setup_status": "/api/setup/status",
        "graphql": "/graphql",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_spa(full_path: str):
    reserved_prefixes = ("api", "docs", "redoc", "openapi.json", "graphql", "assets", "health")
    if full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    raise HTTPException(status_code=404, detail="React frontend build not found")
