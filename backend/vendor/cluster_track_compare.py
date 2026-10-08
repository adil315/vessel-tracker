"""
cluster_track_compare.py

Alternative trackers that enforce boat-like constant-speed motion.
Uses existing Top-50 detection cache (no rebuild required unless missing).

Methods
-------
  1. ST-DBSCAN        - anisotropic DBSCAN in (time, position)
  2. RANSAC-CV        - RANSAC constant-velocity line in (t, x)
  3. VGRAPH           - velocity-gated graph, max sum-z path
  4. SEED-GROW        - seed on early dense ridge, grow with tight v-gate

Run
---
  python cluster_track_compare.py
  python cluster_track_compare.py --cache ./diagnostic_cache/all_detections_top50.pkl
"""

import os
import math
import pickle
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.interpolate import interp1d

try:
    from sklearn.cluster import DBSCAN
    HAS_SK = True
except ImportError:
    HAS_SK = False
    print("[warn] scikit-learn not found — ST-DBSCAN disabled. pip install scikit-learn")

# =====================================================================
# PATHS / GEOMETRY
# =====================================================================
CACHE_CANDIDATES = [
    "/home/tensortitan/ASNSubsea/boat_tracking_algos/detections_cache/semblance_detections_06102026_trial_return.pkl"
    #"/home/oneviewprosubsea/ASNSubsea/diagnostic_cache/all_detections.pkl",
    #"/home/oneviewprosubsea/ASNSubsea/diagnostic_cache2/all_detections.pkl",
    #"/home/oneviewprosubsea/ASNSubsea/diagnostic_cache10/all_detections.pkl",
]
GPX_FILE    = None
EXCEL_FILE  = "/home/tensortitan/ASNSubsea/boat_tracking_algos/S1&S2 fibre mappings2.xlsx"
EXCEL_SHEET = "s1"
OUT_PLOT    = "cluster_track_compare.png"
OUT_CSV_DIR = "/home/tensortitan/ASNSubsea/boat_tracking_algos/tracker_output"

TRUE_DX         = 1.024    # Header spatial sampling (m)
CABLE_OFFSET_KM = 18.0          # DAS_km = Excel_km + 8
V_MIN, V_MAX    = 3.0, 25.0    # plausible boat speed along fibre (m/s)
Z_MIN           = 12.0         # drop weak noise before clustering

# =====================================================================
# BASIC HELPERS
# =====================================================================
def _local_naive(ts):
    t = pd.to_datetime(ts)
    if getattr(t, "tzinfo", None) is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dlmb/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def parse_ddm_to_dd(coord):
    if pd.isna(coord): return np.nan
    if isinstance(coord, (int, float, np.floating)): return float(coord)
    s = str(coord).replace("°"," ").replace("'"," ").replace('"'," ").strip()
    parts = s.split()
    try:
        if len(parts) == 1: return float(parts[0])
        deg, mins = float(parts[0]), float(parts[1])
        hemi = parts[-1].upper() if parts[-1].upper() in "NSEW" else ""
        dd = deg + mins/60.0
        return -dd if hemi in ("S","W") else dd
    except Exception:
        return np.nan

# =====================================================================
# LOAD DETECTIONS
# =====================================================================
def load_detections(cache_path=None):
    path = cache_path
    if path is None:
        for c in CACHE_CANDIDATES:
            if os.path.exists(c):
                path = c; break
    if path is None or not os.path.exists(path):
        raise FileNotFoundError(
            "No detection cache found. Run rebuild_and_track.py --force-rebuild first.")
    with open(path, "rb") as f:
        cache = pickle.load(f)
    dets = cache["detections"]
    dx = float(cache.get("dx", 1.024))
    rows = []
    for d in dets:
        z = float(d.get("zScore", 0.0))
        if z < Z_MIN:
            continue
        rows.append(dict(
            t_epoch = float(d["_t_epoch"]) if "_t_epoch" in d else float(pd.Timestamp(d["timeStart"]).timestamp()),
            t       = _local_naive(d["timeStart"]),
            pos_km  = float(d["eventPosition"]) * dx / 1000.0,
            z       = z,
            v_meas  = float(d.get("vesselSpeed_mps", 0.0)),
            raw     = d,
        ))
    df = pd.DataFrame(rows).sort_values("t_epoch").reset_index(drop=True)
    print(f"Loaded {len(df)} detections with z>={Z_MIN}  (dx={dx} m) from {path}")
    return df, dx

# =====================================================================
# GPX (continuous, +8 km) — validation only
# =====================================================================
def load_gpx_continuous(gpx_path, excel_path, sheet=EXCEL_SHEET):
    raw = pd.read_excel(excel_path, sheet_name=sheet)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    lat_c = next(c for c in raw.columns if "lat" in c)
    lon_c = next(c for c in raw.columns if "lon" in c)
    dist_c = next(c for c in raw.columns if "dist" in c or "cable" in c)

    f_lat = raw[lat_c].apply(parse_ddm_to_dd).to_numpy()
    f_lon = raw[lon_c].apply(parse_ddm_to_dd).to_numpy()
    f_km  = pd.to_numeric(raw[dist_c], errors="coerce").to_numpy() + CABLE_OFFSET_KM
    m = np.isfinite(f_lat) & np.isfinite(f_lon) & np.isfinite(f_km)
    f_lat, f_lon, f_km = f_lat[m], f_lon[m], f_km[m]

    # densify fibre polyline (every ~50 m along haversine)
    dens_lat, dens_lon, dens_km = [f_lat[0]], [f_lon[0]], [f_km[0]]
    for i in range(1, len(f_lat)):
        seg = haversine_km(f_lat[i-1], f_lon[i-1], f_lat[i], f_lon[i])
        n = max(1, int(seg / 0.05))
        for k in range(1, n+1):
            a = k / n
            dens_lat.append(f_lat[i-1]*(1-a) + f_lat[i]*a)
            dens_lon.append(f_lon[i-1]*(1-a) + f_lon[i]*a)
            dens_km.append(f_km[i-1]*(1-a) + f_km[i]*a)
    dens_lat, dens_lon, dens_km = map(np.asarray, (dens_lat, dens_lon, dens_km))

    tree = ET.parse(gpx_path); root = tree.getroot()
    pts = []
    for n in root.findall(".//{http://www.topografix.com/GPX/1/0}trkpt"):
        tnode = n.find("{http://www.topografix.com/GPX/1/0}time")
        if tnode is None or not tnode.text: continue
        pts.append(dict(time=_local_naive(tnode.text),
                        lat=float(n.attrib["lat"]), lon=float(n.attrib["lon"])))
    gpx = pd.DataFrame(pts)
    mapped = []
    for lat, lon in zip(gpx.lat, gpx.lon):
        d = haversine_km(lat, lon, dens_lat, dens_lon)
        mapped.append(dens_km[int(np.argmin(d))])
    gpx["das_km"] = mapped
    return gpx

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class BeamHypothesis:
    score: float
    points: List[int] = field(default_factory=list)
    last_t: Optional[float] = None
    last_x: Optional[float] = None       # km
    velocity: Optional[float] = None     # m/s
    direction: int = 0                  # -1, 0 unknown, +1
    missed: int = 0


def track_viterbi_beam(
    df,
    frame_sec=10.0,
    beam_width=300,
    max_gap_sec=420.0,
    max_speed_mps=20.0,
    min_speed_mps=0.5,
    base_gate_km=0.30,
    gate_growth_km_per_sec=0.0025,
    max_gate_km=1.50,
    z_reference=10.0,
    z_weight=0.65,
    residual_weight=4.0,
    acceleration_weight=2.5,
    reversal_penalty=20.0,
    missed_penalty=0.35,
    velocity_alpha=0.25,
    min_track_points=8,
):
    """
    Global beam-search/Viterbi tracker.

    Input
    -----
    df columns:
        t_epoch, t, pos_km, z, ...

    Important
    ---------
    This function does not use AIS/GPX coordinates, AIS speed, or true labels.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    work = df.copy()
    work = work.sort_values(["t_epoch", "z"], ascending=[True, False]).reset_index(drop=True)
    work["_original_index"] = np.arange(len(work))

    t_origin = float(work["t_epoch"].min())
    work["_frame"] = np.floor(
        (work["t_epoch"] - t_origin) / frame_sec
    ).astype(int)

    frame_ids = range(int(work["_frame"].min()), int(work["_frame"].max()) + 1)

    # Empty hypothesis allows automatic track initiation at any time.
    beams = [BeamHypothesis(score=0.0)]

    for frame_id in frame_ids:
        frame = work[work["_frame"] == frame_id]

        # Limit clutter but retain several spatial alternatives.
        if not frame.empty:
            frame = frame.nlargest(min(50, len(frame)), "z")

        frame_time = t_origin + (frame_id + 0.5) * frame_sec
        proposals = []

        for hyp in beams:

            # ---------------------------------------------------------
            # Option 1: miss/coast through this frame
            # ---------------------------------------------------------
            if hyp.last_t is not None:
                gap = frame_time - hyp.last_t

                if gap <= max_gap_sec:
                    proposals.append(
                        BeamHypothesis(
                            score=hyp.score - missed_penalty,
                            points=hyp.points.copy(),
                            last_t=hyp.last_t,
                            last_x=hyp.last_x,
                            velocity=hyp.velocity,
                            direction=hyp.direction,
                            missed=hyp.missed + 1,
                        )
                    )
            else:
                # Preserve empty hypothesis to permit later initialization.
                proposals.append(hyp)

            # ---------------------------------------------------------
            # Option 2: associate one candidate from this frame
            # ---------------------------------------------------------
            for idx, row in frame.iterrows():
                t_new = float(row["t_epoch"])
                x_new = float(row["pos_km"])
                z_new = float(row["z"])

                z_reward = z_weight * max(0.0, z_new - z_reference)

                # Start a new track from this detection.
                if hyp.last_t is None:
                    proposals.append(
                        BeamHypothesis(
                            score=z_reward,
                            points=[idx],
                            last_t=t_new,
                            last_x=x_new,
                            velocity=None,
                            direction=0,
                            missed=0,
                        )
                    )
                    continue

                dt = t_new - hyp.last_t
                if dt < 0.5 or dt > max_gap_sec:
                    continue

                displacement_m = (x_new - hyp.last_x) * 1000.0
                observed_velocity = displacement_m / dt

                # First transition: estimate direction and velocity.
                if hyp.velocity is None:
                    speed = abs(observed_velocity)

                    if speed < min_speed_mps or speed > max_speed_mps:
                        continue

                    direction = 1 if observed_velocity > 0 else -1

                    proposals.append(
                        BeamHypothesis(
                            score=hyp.score + z_reward,
                            points=hyp.points + [idx],
                            last_t=t_new,
                            last_x=x_new,
                            velocity=observed_velocity,
                            direction=direction,
                            missed=0,
                        )
                    )
                    continue

                # Predict the next cable position.
                predicted_x = hyp.last_x + hyp.velocity * dt / 1000.0
                residual_km = abs(x_new - predicted_x)

                gate_km = min(
                    max_gate_km,
                    base_gate_km
                    + gate_growth_km_per_sec * max(0.0, dt - frame_sec),
                )

                if residual_km > gate_km:
                    continue

                # Prevent direction reversal after direction is established.
                new_direction = (
                    1 if observed_velocity > 0
                    else -1 if observed_velocity < 0
                    else hyp.direction
                )

                reversal_cost = 0.0
                if (
                    hyp.direction != 0
                    and new_direction != hyp.direction
                    and abs(displacement_m) > 150.0
                ):
                    reversal_cost = reversal_penalty

                if abs(observed_velocity) > max_speed_mps:
                    continue

                # Velocity-change penalty. This suppresses congested-area spikes.
                velocity_change = observed_velocity - hyp.velocity
                acceleration = abs(velocity_change) / max(dt, 1.0)

                residual_cost = residual_weight * (residual_km / gate_km) ** 2
                acceleration_cost = acceleration_weight * acceleration

                score_new = (
                    hyp.score
                    + z_reward
                    - residual_cost
                    - acceleration_cost
                    - reversal_cost
                )

                # Robust velocity update.
                if abs(observed_velocity) >= min_speed_mps:
                    velocity_new = (
                        (1.0 - velocity_alpha) * hyp.velocity
                        + velocity_alpha * observed_velocity
                    )
                else:
                    velocity_new = hyp.velocity

                proposals.append(
                    BeamHypothesis(
                        score=score_new,
                        points=hyp.points + [idx],
                        last_t=t_new,
                        last_x=x_new,
                        velocity=velocity_new,
                        direction=hyp.direction or new_direction,
                        missed=0,
                    )
                )

        # -------------------------------------------------------------
        # Deduplicate similar hypotheses
        # -------------------------------------------------------------
        best_by_state = {}

        for hyp in proposals:
            if hyp.last_t is None:
                key = ("empty",)
            else:
                # State quantization prevents the beam filling with nearly
                # identical paths.
                pos_bin = round(hyp.last_x / 0.20)
                vel = hyp.velocity if hyp.velocity is not None else 0.0
                vel_bin = round(vel / 1.0)
                key = (frame_id, pos_bin, vel_bin, hyp.direction, hyp.missed)

            old = best_by_state.get(key)
            if old is None or hyp.score > old.score:
                best_by_state[key] = hyp

        proposals = list(best_by_state.values())

        # Prefer score, track duration and number of accepted observations.
        proposals.sort(
            key=lambda h: (
                h.score + 0.20 * len(h.points),
                len(h.points),
            ),
            reverse=True,
        )

        beams = proposals[:beam_width]

        if not beams:
            beams = [BeamHypothesis(score=0.0)]

    valid = [h for h in beams if len(h.points) >= min_track_points]

    if not valid:
        return pd.DataFrame()

    def final_utility(h):
        selected = work.loc[h.points].sort_values("t_epoch")
        duration = (
            float(selected["t_epoch"].iloc[-1] - selected["t_epoch"].iloc[0])
            if len(selected) > 1 else 0.0
        )

        return (
            h.score
            + 0.30 * len(h.points)
            + 0.002 * duration
        )

    best = max(valid, key=final_utility)

    result = work.loc[best.points].copy()
    result = result.sort_values("t_epoch").reset_index(drop=True)
    result.drop(columns=["_frame", "_original_index"], inplace=True, errors="ignore")

    return result
# =====================================================================
# METHOD 1 — Space-Time DBSCAN
# =====================================================================
def track_stdbscan(df, v_typ=10.0, eps_km=0.8, min_samples=8):
    """
    Feature space: [t_scaled_to_km, pos_km]
    t_scaled = t_epoch * v_typ / 1000  so eps is roughly 'km-equivalent'.
    """
    if not HAS_SK or len(df) < min_samples:
        return pd.DataFrame()
    t0 = df.t_epoch.min()
    X = np.column_stack([
        (df.t_epoch - t0) * v_typ / 1000.0,   # time → km units
        df.pos_km.values,
    ])
    # weight by z: replicate high-z points (cheap density prior)
    w_idx = []
    for i, z in enumerate(df.z.values):
        reps = 1 + int(min(z, 30) // 8)
        w_idx.extend([i] * reps)
    Xw = X[w_idx]
    labels_w = DBSCAN(eps=eps_km, min_samples=min_samples).fit_predict(Xw)
    # majority label per original point
    from collections import Counter
    lab = np.full(len(df), -1, dtype=int)
    buckets = defaultdict(list)
    for wi, lw in zip(w_idx, labels_w):
        buckets[wi].append(lw)
    for i, votes in buckets.items():
        lab[i] = Counter(votes).most_common(1)[0][0]

    df = df.copy(); df["_lab"] = lab
    clusters = [g for l, g in df.groupby("_lab") if l >= 0 and len(g) >= min_samples]
    if not clusters:
        return pd.DataFrame()

    # score: length * mean_z * speed_plausibility * early_presence
    def score(g):
        g = g.sort_values("t_epoch")
        dt = g.t_epoch.iloc[-1] - g.t_epoch.iloc[0]
        dp = g.pos_km.iloc[-1] - g.pos_km.iloc[0]
        v = (dp * 1000.0) / max(dt, 1.0)
        v_ok = 1.0 if V_MIN <= abs(v) <= V_MAX else 0.2
        early = 1.5 if g.pos_km.iloc[0] < 36 else 1.0   # prefer the known early ridge
        mono = 1.0 if dp > -0.5 else 0.3                 # mostly forward
        return len(g) * g.z.mean() * v_ok * early * mono

    best = max(clusters, key=score)
    return best.sort_values("t_epoch").reset_index(drop=True)

# =====================================================================
# METHOD 2 — RANSAC constant velocity
# =====================================================================
def track_ransac_cv(df, n_iter=800, inlier_km=0.6, min_inliers=10, rng=None):
    rng = np.random.default_rng(rng)
    t = df.t_epoch.values
    x = df.pos_km.values
    z = df.z.values
    t0 = t.min()
    tt = t - t0
    best_mask, best_score = None, -1
    n = len(df)
    if n < 2:
        return pd.DataFrame()

    for _ in range(n_iter):
        i, j = rng.choice(n, size=2, replace=False)
        dt = tt[j] - tt[i]
        if abs(dt) < 5.0:
            continue
        v = (x[j] - x[i]) * 1000.0 / dt          # m/s
        if not (V_MIN <= abs(v) <= V_MAX):
            continue
        x0 = x[i] - (v/1000.0) * tt[i]
        pred = x0 + (v/1000.0) * tt
        resid = np.abs(x - pred)
        mask = resid <= inlier_km
        n_in = int(mask.sum())
        if n_in < min_inliers:
            continue
        # score: inliers * mean_z / (1 + mean residual)
        sc = n_in * z[mask].mean() / (1.0 + resid[mask].mean())
        # prefer tracks that start near 30-34 km (the observed ridge)
        if x[mask][np.argmin(t[mask])] < 36:
            sc *= 1.4
        if sc > best_score:
            best_score, best_mask = sc, mask

    if best_mask is None:
        return pd.DataFrame()
    out = df.loc[best_mask].sort_values("t_epoch").reset_index(drop=True)
    # thin: keep highest-z per 15 s bin to avoid clumps
    out["_bin"] = ((out.t_epoch - out.t_epoch.iloc[0]) // 15).astype(int)
    out = out.sort_values("z", ascending=False).groupby("_bin", as_index=False).first()
    return out.sort_values("t_epoch").reset_index(drop=True)

# =====================================================================
# METHOD 3 — Velocity-gated graph (max sum-z path)
# =====================================================================
def track_vgraph(df, max_dt=120.0, max_nodes=2500):
    """
    Nodes = top detections (by z). Edge i→j if time-ordered and
    v = dx/dt in [V_MIN, V_MAX] and spatial jump not insane.
    DP: best path score ending at each node.
    """
    d = df.sort_values(["z"], ascending=False).head(max_nodes)
    d = d.sort_values("t_epoch").reset_index(drop=True)
    n = len(d)
    t = d.t_epoch.values
    x = d.pos_km.values
    z = d.z.values

    # adjacency: list of (j, edge_bonus)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            dt = t[j] - t[i]
            if dt <= 0: continue
            if dt > max_dt: break
            dp = (x[j] - x[i]) * 1000.0          # metres
            v = dp / dt
            if not (V_MIN <= abs(v) <= V_MAX): continue
            # soft preference for forward motion
            if dp < -400: continue
            adj[i].append(j)

    # DP
    best_score = z.copy()          # path score ending at i
    parent = np.full(n, -1, dtype=int)
    for i in range(n):
        for j in adj[i]:
            sc = best_score[i] + z[j]
            if sc > best_score[j]:
                best_score[j] = sc
                parent[j] = i

    # reconstruct from best end; prefer ends that also started early/low-km
    end = int(np.argmax(best_score))
    path_idx = []
    k = end
    while k >= 0:
        path_idx.append(k)
        k = parent[k]
    path_idx.reverse()
    out = d.iloc[path_idx].sort_values("t_epoch").reset_index(drop=True)
    return out

# =====================================================================
# METHOD 4 — Seeded constant-speed grower
# =====================================================================
def track_seed_grow(df, seed_t_end="06:53:30", seed_km=(55.0, 65.0),
                    coast_s=180.0, gate_km=0.9):
    """
    1. Seed = high-z detections in early ridge window.
    2. Estimate v from seed.
    3. Walk forward in time: predict position, take best z inside gate.
    4. Slowly update v (exponential smoothing).
    """
    t_end_seed = None
    # build seed time from first detection date + clock
    t0_day = df.t.iloc[0].normalize()
    hh, mm, ss = map(int, seed_t_end.split(":"))
    t_end_seed = t0_day + pd.Timedelta(hours=hh, minutes=mm, seconds=ss)
    # if DAS starts after that clock, use first 8 minutes instead
    if t_end_seed <= df.t.iloc[0]:
        t_end_seed = df.t.iloc[0] + pd.Timedelta(minutes=8)

    seed = df[(df.t <= t_end_seed) &
              (df.pos_km >= seed_km[0]) & (df.pos_km <= seed_km[1])]
    if len(seed) < 3:
        # fallback: densest 3 km band in first 10 min
        early = df[df.t <= df.t.iloc[0] + pd.Timedelta(minutes=10)]
        if early.empty: return pd.DataFrame()
        bins = np.arange(early.pos_km.min(), early.pos_km.max()+0.5, 0.5)
        hist, edges = np.histogram(early.pos_km, bins=bins)
        b = int(np.argmax(hist))
        lo, hi = edges[b]-0.5, edges[b]+3.0
        seed = early[(early.pos_km>=lo)&(early.pos_km<=hi)]
    seed = seed.sort_values("t_epoch")
    if len(seed) < 2:
        return seed

    # initial velocity from robust slope
    ts = seed.t_epoch.values
    xs = seed.pos_km.values
    v = np.polyfit(ts - ts[0], xs, 1)[0] * 1000.0   # m/s
    v = float(np.clip(v, V_MIN, V_MAX))

    track = [seed.iloc[i] for i in range(len(seed))]
    t_last = float(seed.t_epoch.iloc[-1])
    x_last = float(seed.pos_km.iloc[-1])

    rest = df[df.t_epoch > t_last].sort_values("t_epoch")
    #used = set()
    for _, row in rest.iterrows():
        dt = float(row.t_epoch) - t_last
        if dt <= 0: continue
        x_pred = x_last + (v * dt) / 1000.0
        
        # --- NEW SANITY CHECKS ---
        v_required = abs((row.pos_km - x_last) * 1000.0 / dt)
        
        # 1. Gate check + Speed limit (ignore jumps > 25 m/s)
        if abs(row.pos_km - x_pred) <= (gate_km + 0.002*max(dt-30, 0)) and v_required < 25.0:
            track.append(row)
            v_obs = (row.pos_km - x_last) * 1000.0 / max(dt, 1e-3)
            v = 0.8*v + 0.2*float(np.clip(abs(v_obs), V_MIN, V_MAX))
            t_last = float(row.t_epoch)
            x_last = float(row.pos_km)

    out = pd.DataFrame(track).sort_values("t_epoch").reset_index(drop=True)
    
    # 2. Median filter post-processing to kill any remaining spikes
    if len(out) > 5:
        out["pos_km"] = out["pos_km"].rolling(3, center=True, min_periods=1).median()
    return out
def track_seed_grow_kinematic(df, seed_t_end="06:53:00", coast_s=300.0, 
                              gate_km=0.8, a_max_m_s2=0.35, v_min_mps=1.0, v_max_mps=25.0):
    """
    Kinematically Bounded Seed-Grow Tracker:
    - Enforces maximum physical acceleration (a_max_m_s2).
    - Prevents retrograde (backward) jumps.
    - Smoothly adapts to velocity changes (speeding up or slowing down).
    """
    # 1. Identify early seed detections on the dense ridge
    t0_day = df.t.iloc[0].normalize()
    hh, mm, ss = map(int, seed_t_end.split(":"))
    t_end_seed = t0_day + pd.Timedelta(hours=hh, minutes=mm, seconds=ss)
    if t_end_seed <= df.t.iloc[0]:
        t_end_seed = df.t.iloc[0] + pd.Timedelta(minutes=8)

    seed = df[(df.t <= t_end_seed) & (df.pos_km >= 55.0) & (df.pos_km <= 65.5)].sort_values("t_epoch")
    if len(seed) < 2:
        return df.head(0)

    # 2. Estimate initial state [position, velocity]
    ts = seed.t_epoch.values
    xs = seed.pos_km.values
    v_current = float(np.clip(np.polyfit(ts - ts[0], xs, 1)[0] * 1000.0, v_min_mps, v_max_mps)) # m/s

    track = [seed.iloc[i] for i in range(len(seed))]
    t_last = float(seed.t_epoch.iloc[-1])
    x_last = float(seed.pos_km.iloc[-1])

    rest = df[df.t_epoch > t_last].sort_values("t_epoch")

    # 3. Sequential association with kinematic gating
    for _, row in rest.iterrows():
        dt = float(row.t_epoch) - t_last
        if dt <= 0: 
            continue

        # Expected position based on current velocity
        x_pred = x_last + (v_current * dt) / 1000.0 # km
        spatial_diff_km = row.pos_km - x_last
        
        # Calculate required velocity and acceleration to reach this candidate
        v_required = (spatial_diff_km * 1000.0) / dt # m/s
        a_required = abs(v_required - v_current) / dt # m/s^2

        # --- KINEMATIC CHECKS ---
        # A. Must move forward (or be nearly stationary): v_required >= -0.5 m/s
        # B. Must not exceed max acceleration: a_required <= a_max_m_s2
        # C. Must be within localized spatial gate
        is_spatial_ok = abs(row.pos_km - x_pred) <= (gate_km + 0.0015 * max(dt - 30, 0))
        is_kinematic_ok = (v_required >= -0.5) and (a_required <= a_max_m_s2) and (v_required <= v_max_mps)

        if is_spatial_ok and is_kinematic_ok:
            track.append(row)
            # Smoothly update velocity (allows boat to speed up or slow down)
            v_current = 0.85 * v_current + 0.15 * float(np.clip(v_required, v_min_mps, v_max_mps))
            t_last = float(row.t_epoch)
            x_last = float(row.pos_km)

    out = pd.DataFrame(track).sort_values("t_epoch").reset_index(drop=True)

    # 4. Post-processing: 3-point running median to remove single-frame jitter
    if len(out) > 5:
        out["pos_km"] = out["pos_km"].rolling(window=3, center=True, min_periods=1).median()

    return out
# =====================================================================
# SCORING vs GPX
# =====================================================================
def score_vs_gpx(track_df, gpx_df):
    if track_df is None or track_df.empty or gpx_df is None or gpx_df.empty:
        return dict(n=0, mae_km=np.nan, coverage=0.0, v_mean=np.nan, v_std=np.nan)
    g = gpx_df.set_index("time").sort_index()
    errs, vs = [], []
    for i, r in track_df.iterrows():
        # nearest GPX sample
        idx = np.argmin(np.abs((g.index - r.t).total_seconds()))
        errs.append(abs(r.pos_km - g.das_km.iloc[idx]))
    t = track_df.t_epoch.values
    x = track_df.pos_km.values
    if len(t) >= 2:
        vv = np.diff(x)*1000.0 / np.maximum(np.diff(t), 1e-3)
        v_mean, v_std = float(np.mean(vv)), float(np.std(vv))
    else:
        v_mean, v_std = np.nan, np.nan
    mae = float(np.mean(errs)) if errs else np.nan
    # coverage = fraction of GPX time span touched
    if len(track_df) >= 2:
        cov = (track_df.t.iloc[-1] - track_df.t.iloc[0]) / max(
            (gpx_df.time.max()-gpx_df.time.min()), pd.Timedelta(seconds=1))
        cov = float(min(cov, 1.0))
    else:
        cov = 0.0
    return dict(n=len(track_df), mae_km=mae, coverage=cov, v_mean=v_mean, v_std=v_std)

# =====================================================================
# PLOT
# =====================================================================
def plot_all(df, tracks, gpx, out_path):
    fig, ax = plt.subplots(figsize=(16, 8))
    sc = ax.scatter(df.t, df.pos_km, c=df.z, s=14, cmap="viridis",
                    alpha=0.45, linewidths=0, label="DAS detections", zorder=1)
    fig.colorbar(sc, ax=ax, pad=0.01).set_label("zScore")

    if gpx is not None and not gpx.empty:
        ax.plot(gpx.time, gpx.das_km, color="cyan", lw=3.0, zorder=3,
                label="AIS/GPX (continuous, +8 km)")

    styles = {
        "ST-DBSCAN":  dict(color="magenta", ls="-",  marker="o", lw=2.0),
        "RANSAC-CV":  dict(color="red",     ls="-",  marker="s", lw=2.2),
        "VGRAPH":     dict(color="orange",  ls="--", marker="^", lw=2.0),
        "SEED-GROW":  dict(color="lime",    ls="-",  marker="D", lw=2.4),
        "SEED-GROW-KINEMATIC": dict(color="green", ls="-", marker="D", lw=2.6),
        "VITERBI-BEAM": dict(color="blue",  ls="-",    marker="o",     lw=3.0,
)
    }
    for name, tr in tracks.items():
        if tr is None or tr.empty: continue
        st = styles.get(name, dict(lw=2))
        ax.plot(tr.t, tr.pos_km, label=f"{name} ({len(tr)} pts)", zorder=4, **st)

    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Position along fibre (km)")
    ax.set_title("Constant-speed / cluster trackers vs AIS/GPX ground truth")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")

# =====================================================================
# MAIN
# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None)
    args = ap.parse_args()

    os.makedirs(OUT_CSV_DIR, exist_ok=True)
    df, dx = load_detections(args.cache)

    # GPX window = DAS window only
    try:
        gpx_all = load_gpx_continuous(GPX_FILE, EXCEL_FILE)
        gpx = gpx_all[(gpx_all.time >= df.t.min()) & (gpx_all.time <= df.t.max())].copy()
        print(f"GPX points in DAS window: {len(gpx)}")
    except Exception as e:
        print(f"[warn] GPX load failed: {e}")
        gpx = pd.DataFrame()

    print("\nRunning trackers...")
    tracks = {}
    tracks["ST-DBSCAN"] = track_stdbscan(df)
    print(f"  ST-DBSCAN: {len(tracks['ST-DBSCAN'])} pts")
    tracks["RANSAC-CV"] = track_ransac_cv(df)
    print(f"  RANSAC-CV: {len(tracks['RANSAC-CV'])} pts")
    tracks["VGRAPH"]    = track_vgraph(df)
    print(f"  VGRAPH:    {len(tracks['VGRAPH'])} pts")
    tracks["SEED-GROW"] = track_seed_grow(df)
    print(f"  SEED-GROW: {len(tracks['SEED-GROW'])} pts")
    tracks["SEED-GROW-KINEMATIC"] = track_seed_grow_kinematic(df)
    print(f"  SEED-GROW-KINEMATIC: {len(tracks['SEED-GROW-KINEMATIC'])} pts")
    tracks["VITERBI-BEAM"] = track_viterbi_beam(df)
    print(f"  VITERBI-BEAM: {len(tracks['VITERBI-BEAM'])} pts")

    # scores
    print("\n" + "="*72)
    print(f"{'METHOD':<12}{'N':>6}{'MAE_km':>10}{'COVER':>10}{'V_mean':>10}{'V_std':>10}")
    print("="*72)
    for name, tr in tracks.items():
        s = score_vs_gpx(tr, gpx)
        print(f"{name:<12}{s['n']:>6}"
              f"{s['mae_km']:>10.2f}{s['coverage']:>10.2f}"
              f"{s['v_mean']:>10.2f}{s['v_std']:>10.2f}")
        if tr is not None and not tr.empty:
            tr.to_csv(os.path.join(OUT_CSV_DIR, f"track_{name}.csv"), index=False)
    print("="*72)
    print("Pick lowest MAE_km with decent N and V_std (smooth speed).")

    plot_all(df, tracks, gpx, OUT_PLOT)

if __name__ == "__main__":
    main()