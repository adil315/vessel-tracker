# Vessel Tracker

A full-stack tracking dashboard that wraps an existing Python detection pipeline in a FastAPI + React UI.

## Place the vendor scripts

Place the following files into `backend/vendor/` before running the backend:

- `cluster_track_compare.py`
- `db_track_compare.py`
- `plot_2d_with_ais.py`

The app imports those modules and keeps the tracking logic intact while replacing matplotlib/folium output with Plotly and Google Maps.

## Database setup

Update the PostgreSQL connection settings in `backend/config.py`:

```python
DB = {
    "host": "localhost",
    "port": 5432,
    "name": "seadb",
    "user": "sea_user",
    "password": "YOUR_PASSWORD",
}
```

Ensure the PostgreSQL table referenced by the dashboard exists and contains the expected detections schema used by `db_track_compare.py`.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Frontend

```bash
cd frontend
npm install
cp .env.example .env
# replace VITE_GOOGLE_MAPS_KEY=YOUR_KEY with your Google Maps API key
npm run dev
```

The frontend runs on http://localhost:5173 by default and posts to the FastAPI backend at `http://localhost:8000` unless you override `VITE_API_URL`.

## Notes

- `VITE_GOOGLE_MAPS_KEY` should be replaced in the frontend `.env` file before opening the dashboard.
- The dashboard expects the same date-time and cable parameters used by the tracking scripts.
- If `overlay_ais=true` but no GPX file is found, the UI shows the fallback AIS unavailable state.
