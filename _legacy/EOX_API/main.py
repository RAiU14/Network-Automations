from fastapi import FastAPI
from EOX_API.api.routes_eox import router as eox_router

app = FastAPI(title="Cisco EOX Scraper API")
app.include_router(eox_router)
