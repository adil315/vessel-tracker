from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    from .config import CABLE_OFFSET_KM, DB, EXCEL_FILE_PATH, GPX_FILE_PATH
except ImportError:
    from config import CABLE_OFFSET_KM, DB, EXCEL_FILE_PATH, GPX_FILE_PATH

# The vendor scripts import each other by top-level module name
# (e.g. `from cluster_track_compare import ...`), so the vendor directory
# itself must be importable.
_VENDOR_DIR = str(Path(__file__).resolve().parent / "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

cluster_mod = None
db_mod = None
plot_mod = None
try:
    try:
        from .vendor import cluster_track_compare as cluster_mod, db_track_compare as db_mod, plot_2d_with_ais as plot_mod
    except ImportError:
        # Running as plain scripts (uvicorn main:app from backend/): the vendor
        # directory is a top-level package next to this file.
        from vendor import cluster_track_compare as cluster_mod, db_track_compare as db_mod, plot_2d_with_ais as plot_mod
except Exception:
    logger.exception("Failed to import vendor tracking modules from backend/vendor/")

ALGO_MAP: Dict[str, Callable[..., Any]] = {
    "ST-DBSCAN": None,
    "RANSAC-CV": None,
    "VGRAPH": None,
    "SEED-GROW": None,
    "SEED-GROW-KINEMATIC": None,
    "VITERBI-BEAM": None,
}

if cluster_mod is not None:
    for key, fn_name in {
        "ST-DBSCAN": "track_stdbscan",
        "RANSAC-CV": "track_ransac_cv",
        "VGRAPH": "track_vgraph",
        "SEED-GROW": "track_seed_grow",
        "SEED-GROW-KINEMATIC": "track_seed_grow_kinematic",
        "VITERBI-BEAM": "track_viterbi_beam",
    }.items():
        fn = getattr(cluster_mod, fn_name, None)
        if fn is not None:
            ALGO_MAP[key] = fn

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _as_dataframe(payload: Any) -> pd.DataFrame:
    if isinstance(payload, pd.DataFrame):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("points") or payload.get("data") or payload.get("track") or []
        if isinstance(rows, list):
            return pd.DataFrame(rows)
        return pd.DataFrame([payload])
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return pd.DataFrame()

def _time_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).isoformat()


def _build_empty_response(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fibre_detections": [],
        "tracks": [],
        "fiber_latlon": [],
        "ais_latlon": None,
        "ais_available": False,
        "metadata": {
            "total_detections": 0,
            "cable": request.get("cable", "s1"),
            "duration_min": 0,
            "algorithm": request.get("algorithm", "VITERBI-BEAM"),
            "message": "No detections matched the supplied window.",
        },
    }

def _score_track(track_df: pd.DataFrame, gpx_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    if track_df.empty:
        return {"n": 0, "mae_km": 0.0, "coverage": 0.0, "v_mean": 0.0, "v_std": 0.0}
    n = len(track_df)
    if gpx_df is not None and not gpx_df.empty:
        try:
            pos = track_df["pos_km"].astype(float) if "pos_km" in track_df.columns else pd.Series([0.0] * n)
            mae = float(abs(pos - gpx_df["pos_km"]).mean()) if "pos_km" in gpx_df.columns and len(gpx_df) > 0 else 0.0
            coverage = float(min(1.0, n / max(1, len(gpx_df))))
        except Exception:
            mae = 0.0
            coverage = 0.0
    else:
        mae = 0.0
        coverage = 1.0 if n else 0.0
    try:
        if "t" in track_df.columns or "time" in track_df.columns:
            time_col = "t" if "t" in track_df.columns else "time"
            ordered = track_df.assign(_time=pd.to_datetime(track_df[time_col], errors="coerce"))
            ordered = ordered.sort_values("_time")
            dt = ordered["_time"].diff().dt.total_seconds()
            distance = ordered["pos_km"].astype(float).diff() * 1000.0
            speeds = (distance / dt).where(dt > 0).dropna()
            v_mean = float(speeds.mean()) if not speeds.empty else 0.0
            v_std = float(speeds.std()) if len(speeds) > 1 else 0.0
        else:
            v_mean = 0.0
            v_std = 0.0
    except Exception:
        v_mean = 0.0
        v_std = 0.0
    return {
        "n": int(n),
        "mae_km": float(mae),
        "coverage": float(coverage),
        "v_mean": float(v_mean),
        "v_std": float(v_std),
    }

def _normalize_point_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "time": _time_str(row.get("t", row.get("time", row.get("timestamp")))),
        "pos_km": _safe_float(row.get("pos_km", row.get("distance_km", 0.0)), 0.0),
        "z": _safe_float(row.get("z", row.get("zScore", 0.0)), 0.0),
        "confidence": _safe_float(row.get("confidence", row.get("conf", 0.0)), 0.0),
        "on_lat": _safe_float(row.get("on_lat", row.get("lat_on_cable", 0.0)), 0.0),
        "on_lon": _safe_float(row.get("on_lon", row.get("lon_on_cable", 0.0)), 0.0),
        "boat_lat": _safe_float(row.get("boat_lat", row.get("lat", 0.0)), 0.0),
        "boat_lon": _safe_float(row.get("boat_lon", row.get("lon", 0.0)), 0.0),
        "h_smooth": _safe_float(row.get("h_smooth", row.get("source_distance", 0.0)), 0.0),
    }

def _normalize_track_result(name: str, payload: Any, color: str) -> Dict[str, Any]:
    df = _as_dataframe(payload)
    records = []
    for _, row in df.iterrows():
        records.append(_normalize_point_row(row.to_dict()))
    return {
        "name": name,
        "color": color,
        "points": records,
        "score": _score_track(df),
    }

def _load_fiber_latlon(cable: str) -> list[dict[str, Any]]:
    if not EXCEL_FILE_PATH or cluster_mod is None:
        return []
    try:
        raw = pd.read_excel(EXCEL_FILE_PATH, sheet_name=cable)
        raw.columns = [str(col).strip().lower() for col in raw.columns]
        lat_col = next(col for col in raw if "lat" in col)
        lon_col = next(col for col in raw if "lon" in col)
        dist_col = next(col for col in raw if "dist" in col or "cable" in col)
        fiber = pd.DataFrame({
            "lat": raw[lat_col].apply(cluster_mod.parse_ddm_to_dd),
            "lon": raw[lon_col].apply(cluster_mod.parse_ddm_to_dd),
            "km": pd.to_numeric(raw[dist_col], errors="coerce") + CABLE_OFFSET_KM[cable],
        }).dropna().sort_values("km")
        return fiber.to_dict("records")
    except (FileNotFoundError, KeyError, StopIteration, ValueError):
        logger.exception("Could not load fibre coordinates from %s", EXCEL_FILE_PATH)
        return []

def _load_gpx_latlon(cable: str) -> list[dict[str, Any]]:
    if not GPX_FILE_PATH or not Path(GPX_FILE_PATH).is_file() or cluster_mod is None:
        return []
    try:
        gpx_data = cluster_mod.load_gpx_continuous(
            GPX_FILE_PATH, EXCEL_FILE_PATH, sheet=cable
        )
        df = _as_dataframe(gpx_data)
        # Vendor loader uses the s1 offset (18 km) regardless of the sheet.
        return [{"lat": float(row["lat"]), "lon": float(row["lon"]),
                 "km": float(row["das_km"]) + CABLE_OFFSET_KM[cable] - CABLE_OFFSET_KM["s1"],
                 "time": _time_str(row["time"])} for _, row in df.iterrows()]
    except Exception:
        logger.exception("Could not load AIS/GPX overlay from %s", GPX_FILE_PATH)
        return []

def run_tracking(request: Dict[str, Any]) -> Dict[str, Any]:
    if not request.get("table"):
        raise ValueError("table is required")

    if db_mod is None:
        raise RuntimeError("backend/vendor/db_track_compare.py is missing. Place your script in backend/vendor/ first.")

    cfg = {
        "cable": request.get("cable", "s1"),
        "algorithm": request.get("algorithm", "VITERBI-BEAM"),
        "chain": request.get("chain", "Frequency tonality chain"),
        "table": request.get("table"),
        "min_od": float(request.get("min_od", 22000.0)),
        "max_od": float(request.get("max_od", 75000.0)),
        "start_time": request.get("start_time"),
        "end_time": request.get("end_time"),
        "conf_min": float(request.get("conf_min", 0.0)),
        "overlay_ais": bool(request.get("overlay_ais", False)),
        # Connection settings expected by db_track_compare.load_detections_from_db
        "db_host": DB["host"],
        "db_port": DB["port"],
        "db_name": DB["name"],
        "db_user": DB["user"],
        "db_pass": DB["password"],
    }

    load_fn = getattr(db_mod, "load_detections_from_db", None)
    if load_fn is None:
        raise RuntimeError("load_detections_from_db is missing from backend/vendor/db_track_compare.py")

    detection_df = load_fn(cfg)
    df = _as_dataframe(detection_df)
    if df.empty:
        return _build_empty_response(request)

    algorithms = [request.get("algorithm", "VITERBI-BEAM")]
    if request.get("algorithm") == "ALL":
        algorithms = [
            "ST-DBSCAN",
            "RANSAC-CV",
            "VGRAPH",
            "SEED-GROW",
            "SEED-GROW-KINEMATIC",
            "VITERBI-BEAM",
        ]

    color_map = {
        "ST-DBSCAN": "#c026d3",
        "RANSAC-CV": "#ef4444",
        "VGRAPH": "#f59e0b",
        "SEED-GROW": "#a3e635",
        "SEED-GROW-KINEMATIC": "#22c55e",
        "VITERBI-BEAM": "#3b82f6",
    }

    track_results = []
    for alg in algorithms:
        fn = ALGO_MAP.get(alg)
        if fn is None:
            continue
        raw = fn(df)
        result = _normalize_track_result(alg, raw, color_map.get(alg, "#3b82f6"))
        if result["points"]:
            track_results.append(result)

    fibre_rows = []
    if not df.empty:
        for _, row in df.iterrows():
            fibre_rows.append({
                "time": _time_str(row.get("t", row.get("time", row.get("timestamp")))),
                "pos_km": _safe_float(row.get("pos_km", row.get("distance_km", 0.0)), 0.0),
                "z": _safe_float(row.get("z", row.get("zScore", 0.0)), 0.0),
                "confidence": _safe_float(row.get("confidence", row.get("conf", row.get("z", 0.0) / 30.0)), 0.0),
            })

    gpx_rows = _load_gpx_latlon(request.get("cable", "s1")) if request.get("overlay_ais", False) else []
    ais_available = bool(gpx_rows)

    answer = {
        "fibre_detections": fibre_rows,
        "tracks": track_results,
        "fiber_latlon": _load_fiber_latlon(request.get("cable", "s1")),
        "ais_latlon": gpx_rows if ais_available else None,
        "ais_available": ais_available,
        "metadata": {
            "total_detections": int(len(fibre_rows)),
            "cable": request.get("cable", "s1"),
            "duration_min": max(0, int((pd.to_datetime(request.get("end_time")) - pd.to_datetime(request.get("start_time"))).total_seconds() // 60)) if request.get("start_time") and request.get("end_time") else 0,
            "algorithm": request.get("algorithm", "VITERBI-BEAM"),
            "message": "Track pipeline completed successfully.",
        },
    }
    return answer
