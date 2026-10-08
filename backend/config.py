from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Connection settings can be overridden via environment variables, e.g.
#   VESSEL_TRACKER_DB_HOST=db.internal VESSEL_TRACKER_DB_PASSWORD=secret
DB: Dict[str, Any] = {
    "host": os.environ.get("VESSEL_TRACKER_DB_HOST", "localhost"),
    "port": int(os.environ.get("VESSEL_TRACKER_DB_PORT", "5432")),
    "name": os.environ.get("VESSEL_TRACKER_DB_NAME", "seadb"),
    "user": os.environ.get("VESSEL_TRACKER_DB_USER", "sea_user"),
    "password": os.environ.get("VESSEL_TRACKER_DB_PASSWORD", "resu_aes"),
}

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Defaults to the workbook shipped in this repository; override with
# VESSEL_TRACKER_EXCEL_FILE if your data lives elsewhere.
EXCEL_FILE_PATH: Optional[str] = os.environ.get(
    "VESSEL_TRACKER_EXCEL_FILE",
    os.path.join(_BACKEND_DIR, "S1&S2 fibre mappings2.xlsx"),
)
GPX_FILE_PATH: Optional[str] = os.environ.get("VESSEL_TRACKER_GPX_FILE") or None

CABLE_OFFSET_KM = {
    "s1": 18.0,
    "s2": 8.0,
}

_DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://192.168.1.136:5173",
]


def _parse_origins(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# CORS allowlist for the frontend dev server / deployed dashboard.
# Set VESSEL_TRACKER_ALLOWED_ORIGINS to a comma-separated list to override, e.g.
#   VESSEL_TRACKER_ALLOWED_ORIGINS="http://localhost:5173,https://tracker.example.com"
ALLOWED_ORIGINS = (
    _parse_origins(os.environ.get("VESSEL_TRACKER_ALLOWED_ORIGINS"))
    or _DEFAULT_ALLOWED_ORIGINS
)
