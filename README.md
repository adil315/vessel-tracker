# Vessel Tracker

A full-stack tracking dashboard wrapping the Python detection pipeline in a FastAPI + React UI.

## Prerequisites

- Python 3.10+, Node.js 20+, npm
- A PostgreSQL database with the detections table used by `backend/vendor/db_track_compare.py` (`id`, `odMeter`, `starttime`, `eventConfidence`, `locationDetails`, `chain`)
- A Google Maps JavaScript API key to display the map (the plots and API work without one)

The vendor scripts and cable workbook are already included in `backend/`. The committed `backend/vessel/` virtual environment is machine-specific; **create a fresh `.venv`** instead.

## Start the backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Set these as needed for your PostgreSQL server:
# export VESSEL_TRACKER_DB_HOST=localhost
# export VESSEL_TRACKER_DB_PORT=5432
# export VESSEL_TRACKER_DB_NAME=seadb
# export VESSEL_TRACKER_DB_USER=sea_user
# export VESSEL_TRACKER_DB_PASSWORD=your-password
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The API is at `http://localhost:8000`, with `/api/health` and `/api/track`. Health reports `db_reachable: false` when no database is available; tracking requires the database and matching data. The default cable workbook is `backend/S1&S2 fibre mappings2.xlsx`; override its path with `VESSEL_TRACKER_EXCEL_FILE` if needed. For an optional AIS/GPX overlay set `VESSEL_TRACKER_GPX_FILE` to a GPX file.

## Start the frontend

```bash
cd frontend
npm ci
cp .env.example .env
# Set VITE_GOOGLE_MAPS_KEY in .env to enable the Google map.
npm run dev
```

Open `http://localhost:5173`. By default the frontend requests relative `/api/track` and Vite proxies `/api` to `http://localhost:8000`, so there is **no cross-origin browser request**. The proxy also works when the dashboard is opened from a remote preview URL. If the backend is elsewhere, set `VITE_API_URL` to its URL **before** starting Vite; this controls both the proxy target and (if specified) the browser's direct API URL. For a cross-origin direct request, configure the backend allowlist as well:

```bash
export VESSEL_TRACKER_ALLOWED_ORIGINS="http://localhost:5173,https://tracker.example.com"
```

The default CORS allowlist includes `http://localhost:5173` and `http://127.0.0.1:5173` (distinct origins). Do not use `localhost` as a browser-facing API URL when the site is viewed on another machine. For production, configure your web server to reverse-proxy `/api` to FastAPI if you want to keep requests same-origin.

## Checks

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
cd ../frontend
npm run build
```

The regression tests cover the CORS preflight, request validation, vendor dataframe/config integration, cable workbook, and response normalization without requiring a live database. Actual tracking still depends on your database and detection data; missing rows produce an empty result.
