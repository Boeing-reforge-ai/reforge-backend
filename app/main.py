from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db import init_db
from app.routers import health, proposals, reference, scans, scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Reforge AI Pipeline API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["공통"])
def root():
    return {"message": "Reforge AI Pipeline API is running"}


app.include_router(health.router)
app.include_router(scans.router)
app.include_router(scenarios.router)
app.include_router(proposals.router)
app.include_router(reference.router)

# 스캔 캡처 이미지 (/static/scans/{scan_id}.jpg)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.upload_dir), name="static")
