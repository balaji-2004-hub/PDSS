from __future__ import annotations

import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.ml_pipeline import SupplyChainMLPipeline
from app.models_loader import ModelRegistry
from app.routes.api import router

MODELS_DIR = BACKEND_DIR / "models"

logger = logging.getLogger("pdss.main")
logger.setLevel(logging.INFO)
if not logger.handlers:
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
    logger.addHandler(stream_handler)

app = FastAPI(
    title="Predictive Decision Support System API",
    description="Vendor Management and Supply Chain Continuity Decision Support",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup_event() -> None:
    if getattr(app.state, "initialized", False):
        return

    logger.info("Creating database tables")
    create_tables()

    logger.info("Running full ML pipeline before API serving")
    pipeline = SupplyChainMLPipeline(BACKEND_DIR)
    pipeline.run_full_pipeline()

    logger.info("Loading trained models")
    registry = ModelRegistry(MODELS_DIR)
    registry.load()
    app.state.model_registry = registry
    app.state.initialized = True

    logger.info("API startup complete")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
