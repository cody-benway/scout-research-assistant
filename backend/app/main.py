from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Scout backend starting up")
    # Eagerly import the graph so the LangGraph StateGraph is compiled on startup
    from app.agent.graph import get_graph  # noqa: F401
    yield
    logger.info("Scout backend shutting down")


app = FastAPI(
    title="Scout Research Assistant API",
    description="AI-powered research assistant that autonomously investigates topics and delivers structured reports.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and any deployed frontend origin
_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.research import router as research_router  # noqa: E402

app.include_router(research_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
