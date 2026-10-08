from typing import Any, Dict, Optional

DB: Dict[str, Any] = {
    "host": "localhost",
    "port": 5432,
    "name": "seadb",
    "user": "sea_user",
    "password": "resu_aes",
}

EXCEL_FILE_PATH: Optional[str] = "/home/tranzmeo/DAS/vessel-tracker/backend/S1&S2 fibre mappings2.xlsx"
GPX_FILE_PATH: Optional[str] = None

CABLE_OFFSET_KM = {
    "s1": 18.0,
    "s2": 8.0,
}

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://192.168.1.136:5173",
]