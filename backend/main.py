from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

try:
    from .config import ALLOWED_ORIGINS, DB
    from .pipeline import run_tracking
    from .schemas import TrackRequest, TrackResponse
except ImportError:
    from config import ALLOWED_ORIGINS, DB
    from pipeline import run_tracking
    from schemas import TrackRequest, TrackResponse

import psycopg2

logger = logging.getLogger(__name__)

app = FastAPI(title="Vessel Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, Any]:
    db_reachable = False
    try:
        connection = psycopg2.connect(
            host=DB["host"],
            port=DB["port"],
            dbname=DB["name"],
            user=DB["user"],
            password=DB["password"],
        )
        connection.close()
        db_reachable = True
    except psycopg2.Error:
        logger.exception("Database health check failed")
    return {"status": "ok", "db_reachable": db_reachable}

@app.post("/api/track", response_model=TrackResponse)
def process_track(request: TrackRequest):
    try:
        return run_tracking(request.model_dump())
    except HTTPException:
        raise
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
