"""
db_track_compare.py

Database-integrated wrapper for cluster_track_compare.py.
Imports tracking algorithms, metrics, and visualization utilities 
from the original script to eliminate code duplication.
"""

import os
import json
import numpy as np
import pandas as pd

# Import all tracking algorithms, configurations, and utilities from your original script
from cluster_track_compare import (
    _local_naive,
    load_gpx_continuous,
    track_stdbscan,
    track_ransac_cv,
    track_vgraph,
    track_seed_grow,
    track_seed_grow_kinematic,
    track_viterbi_beam,
    score_vs_gpx,
    plot_all,
    GPX_FILE,
    EXCEL_FILE,
    OUT_PLOT,
    OUT_CSV_DIR,
)

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("[warn] psycopg2 not found. Install via: pip install psycopg2-binary")


# =====================================================================
# CONFIGURATION
# =====================================================================
CONFIG = {
    # Database connection
    "db_host":    "localhost",
    "db_port":    5432,
    "db_name":    "seadb",
    "db_user":    "sea_user",
    "db_pass":    "resu_aes",

    # Query parameters
    "table":      "subsea1_pids1predictedevents_2026_09_29",
    "chain":      'Frequency tonality chain',
    "min_od":     22000.0,
    "max_od":     75000.0,
    "start_time":'2026-09-29 03:00:00.768875+00',
    "end_time":   '2026-09-29 05:00:00.768875+00',

    # Detection filter
    "conf_min":   0,
}


# =====================================================================
# DATABASE LOADER
# =====================================================================
def load_detections_from_db(cfg):
    """Queries PostgreSQL table and formats records for the imported trackers."""
    if not HAS_PSYCOPG2:
        raise ImportError("psycopg2 is required. Run: pip install psycopg2-binary")

    print(f"Connecting to database '{cfg['db_name']}' on {cfg['db_host']}...")
    conn = psycopg2.connect(
        host=cfg["db_host"],
        port=cfg["db_port"],
        database=cfg["db_name"],
        user=cfg["db_user"],
        password=cfg["db_pass"],
    )

    query = f"""
    SELECT id, "odMeter", starttime, "eventConfidence", "locationDetails"
    FROM {cfg['table']}
    WHERE chain = %s
      AND "odMeter" BETWEEN %s AND %s
      AND starttime BETWEEN %s AND %s
    ORDER BY id ASC;
    """

    try:
        df_raw = pd.read_sql_query(
            query, conn,
            params=(cfg["chain"], cfg["min_od"], cfg["max_od"],
                    cfg["start_time"], cfg["end_time"])
        )
    finally:
        conn.close()

    if df_raw.empty:
        print(f"[warn] Query returned 0 rows for table {cfg['table']}.")
        return pd.DataFrame()

    rows = []
    for _, row in df_raw.iterrows():
        conf = float(row["eventConfidence"]) if pd.notna(row["eventConfidence"]) else 0.0
        if conf < cfg["conf_min"]:
            continue

        # Parse latitude and longitude from locationDetails JSON
        lat, lon = np.nan, np.nan
        loc_details = row["locationDetails"]
        if loc_details:
            try:
                loc_dict = json.loads(loc_details) if isinstance(loc_details, str) else loc_details
                lat = float(loc_dict.get("Lat", loc_dict.get("lat", np.nan)))
                lon = float(loc_dict.get("Long", loc_dict.get("long", np.nan)))
            except Exception:
                pass

        t_parsed = _local_naive(row["starttime"])

        # Scale eventConfidence (0.0-1.0) to zScore magnitude (0.0-30.0) 
        # so default thresholds inside imported trackers work out of the box.
        z_scaled = conf * 30.0

        rows.append(dict(
            id      = int(row["id"]),
            t_epoch = t_parsed.timestamp(),
            t       = t_parsed,
            pos_km  = float(row["odMeter"]) / 1000.0,
            z       = z_scaled,
            lat     = lat,
            lon     = lon,
            v_meas  = 0.0,
        ))

    df = pd.DataFrame(rows).sort_values("t_epoch").reset_index(drop=True)
    print(f"Loaded {len(df)} detections with eventConfidence >= {cfg['conf_min']}")
    return df


# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================
def main():
    os.makedirs(OUT_CSV_DIR, exist_ok=True)
    df = load_detections_from_db(CONFIG)

    if df.empty:
        print("No detections loaded. Execution terminated.")
        return

    # Load validation GPX route if present
    try:
        gpx_all = load_gpx_continuous(GPX_FILE, EXCEL_FILE)
        gpx = gpx_all[(gpx_all.time >= df.t.min()) & (gpx_all.time <= df.t.max())].copy()
        print(f"Loaded validation GPX points in window: {len(gpx)}")
    except Exception as e:
        print(f"[warn] GPX route load skipped: {e}")
        gpx = pd.DataFrame()

    # Run all imported trackers
    print("\nExecuting trackers...")
    tracks = {
        "ST-DBSCAN":            track_stdbscan(df),
        "RANSAC-CV":            track_ransac_cv(df),
        "VGRAPH":               track_vgraph(df),
        "SEED-GROW":            track_seed_grow(df),
        "SEED-GROW-KINEMATIC":  track_seed_grow_kinematic(df),
        "VITERBI-BEAM":         track_viterbi_beam(df),
    }

    # Benchmark results
    print("\n" + "=" * 80)
    print(f"{'METHOD':<20}{'N':>6}{'MAE_km':>10}{'COVER':>10}{'V_mean':>10}{'V_std':>10}")
    print("=" * 80)
    for name, tr in tracks.items():
        s = score_vs_gpx(tr, gpx)
        print(f"{name:<20}{s['n']:>6}{s['mae_km']:>10.2f}"
              f"{s['coverage']:>10.2f}{s['v_mean']:>10.2f}{s['v_std']:>10.2f}")

        if tr is not None and not tr.empty:
            out_cols = ["id", "t_epoch", "t", "pos_km", "lat", "lon"]
            out_df = tr[[c for c in out_cols if c in tr.columns]].copy()
            out_df["confidence"] = tr["z"] / 30.0  # Revert scaled z back to confidence
            out_df.to_csv(os.path.join(OUT_CSV_DIR, f"track_{name}.csv"), index=False)

    print("=" * 80)
    print(f"Track details exported to: {OUT_CSV_DIR}")

    plot_all(df, tracks, gpx, OUT_PLOT)


if __name__ == "__main__":
    main()