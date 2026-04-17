from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sys

# Add project root to sys.path for top-level imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from api_service.core.config import settings
from api_service.api.routes_eox import router as eox_router
from api_service.api.routes_reports import router as reports_router
from api_service.api.routes_devices import router as devices_router
from api_service.api.routes_tools import router as tools_router

# Import root tools for integration
import Alive_Checks
import Log_Capture

app = FastAPI(
    title="Network Automation Platform",
    description="Professional Standalone Automation & Reporting Hub",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Integrated Tool Logic ---
# (Injecting root tools into the app state or dependencies)

# --- Include Modular Routes ---
app.include_router(eox_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(tools_router, prefix="/api")

@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "mock_mode": settings.MOCK_MODE,
        "platform_version": "2.0.0-standalone"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
