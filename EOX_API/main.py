from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from EOX_API.api.routes_eox import router as eox_router
from EOX_API.models.eox import HealthResponse

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "front_end" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

app = FastAPI(
    title="Cisco EOX API",
    description="Cisco EOX/EOL lookup API with Cisco API and scraper-backed endpoints.",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def api_health() -> HealthResponse:
    return HealthResponse()


app.include_router(eox_router)

if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="frontend-assets")


@app.get("/", include_in_schema=False)
def serve_frontend_or_health():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return {
        "status": "ok",
        "service": "Cisco EOX API",
        "frontend": "React build not found. Run: cd front_end && npm install && npm run build",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_spa(full_path: str):
    reserved_prefixes = ("eox", "api", "docs", "redoc", "openapi.json", "assets")
    if full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    raise HTTPException(
        status_code=404,
        detail="React frontend build not found. Run: cd front_end && npm install && npm run build",
    )
