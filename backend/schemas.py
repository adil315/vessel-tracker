from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

class TrackRequest(BaseModel):
    cable: Literal["s1", "s2"] = "s1"
    algorithm: Literal[
        "ST-DBSCAN",
        "RANSAC-CV",
        "VGRAPH",
        "SEED-GROW",
        "SEED-GROW-KINEMATIC",
        "VITERBI-BEAM",
        "ALL",
    ] = "VITERBI-BEAM"
    chain: str = "Frequency tonality chain"
    # Vendor SQL interpolates this name into a query; only allow plain identifiers.
    table: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    min_od: float = 22000.0
    max_od: float = 75000.0
    start_time: str
    end_time: str
    conf_min: float = 0.0
    overlay_ais: bool = False

class FibrePoint(BaseModel):
    time: str
    pos_km: float
    z: float
    confidence: float

class TrackPoint(BaseModel):
    time: str
    pos_km: float
    z: float
    on_lat: float
    on_lon: float
    boat_lat: float
    boat_lon: float
    h_smooth: float

class LatLon(BaseModel):
    lat: float
    lon: float
    km: Optional[float] = None
    time: Optional[str] = None

class TrackScore(BaseModel):
    n: int
    mae_km: float
    coverage: float
    v_mean: float
    v_std: float

class TrackResult(BaseModel):
    name: str
    color: str
    points: List[TrackPoint] = Field(default_factory=list)
    score: Dict[str, Any]

class TrackResponse(BaseModel):
    fibre_detections: List[FibrePoint] = Field(default_factory=list)
    tracks: List[TrackResult] = Field(default_factory=list)
    fiber_latlon: List[LatLon] = Field(default_factory=list)
    ais_latlon: Optional[List[LatLon]] = None
    ais_available: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
