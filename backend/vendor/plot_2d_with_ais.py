"""
plot_2d_with_ais.py

Layers:
  1. Subsea fibre (Excel s2, DAS_km = Excel_km + 8)
  2. AIS/GPX true boat path (cropped to DAS time window)
  3. DAS 2D track = on-cable (pos_km) + perpendicular smoothed sourceDistance h(t)
"""

import os
import ast
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

EXCEL_FILE   = "/home/oneviewprosubsea/ASNSubsea/S1&S2 fibre mappings2.xlsx"
EXCEL_SHEET  = "s2"
GPX_FILE     = "/home/oneviewprosubsea/ASNSubsea/20260928-112443 - 28 Sept 26 (1).gpx"
TRACK_CSV    = "/home/oneviewprosubsea/ASNSubsea/tracker_output/track_VITERBI-BEAM.csv"

OUT_HTML     = "vessel_2d_fibre_ais.html"
OUT_PNG      = "vessel_2d_fibre_ais.png" 

CABLE_OFFSET_KM = 8.0   # DAS_km = Excel_km + 8.0


def parse_ddm_to_dd(coord):
    if pd.isna(coord):
        return np.nan
    if isinstance(coord, (int, float, np.floating)):
        return float(coord)
    s = str(coord).replace("°", " ").replace("'", " ").replace('"', " ").strip()
    parts = s.split()
    try:
        if len(parts) == 1:
            return float(parts[0])
        deg, mins = float(parts[0]), float(parts[1])
        hemi = parts[-1].upper() if parts[-1].upper() in ("N", "S", "E", "W") else ""
        dd = deg + mins / 60.0
        return -dd if hemi in ("S", "W") else dd
    except Exception:
        return np.nan


def _naive(ts):
    t = pd.to_datetime(ts)
    if getattr(t, "tzinfo", None) is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t


def extract_h(row):
    if "sourceDistance" in row and pd.notna(row["sourceDistance"]):
        try:
            return float(row["sourceDistance"])
        except Exception:
            pass
    if "raw" in row and pd.notna(row["raw"]):
        try:
            d = ast.literal_eval(str(row["raw"]))
            if d.get("sourceDistance") is not None:
                return float(d["sourceDistance"])
        except Exception:
            pass
    return np.nan


def load_fiber():
    if not os.path.exists(EXCEL_FILE):
        raise FileNotFoundError(f"Excel file '{EXCEL_FILE}' not found.")
    raw = pd.read_excel(EXCEL_FILE, sheet_name=EXCEL_SHEET)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    lat_c = next(c for c in raw.columns if "lat" in c)
    lon_c = next(c for c in raw.columns if "lon" in c)
    dist_c = next(c for c in raw.columns if "dist" in c or "cable" in c)
    df = pd.DataFrame({
        "lat": raw[lat_c].apply(parse_ddm_to_dd),
        "lon": raw[lon_c].apply(parse_ddm_to_dd),
        "excel_km": pd.to_numeric(raw[dist_c], errors="coerce"),
    }).dropna()
    df["das_km"] = df["excel_km"] + CABLE_OFFSET_KM
    return df.sort_values("das_km").reset_index(drop=True)


def load_gpx(path):
    """Robust GPX parser using tag string matching (ignores namespace differences)."""
    if not os.path.exists(path):
        print(f"[WARN] GPX file '{path}' not found.")
        return pd.DataFrame(columns=["t", "lat", "lon"])

    tree = ET.parse(path)
    root = tree.getroot()
    pts = []

    for elem in root.iter():
        if elem.tag.endswith("trkpt"):
            lat = elem.attrib.get("lat")
            lon = elem.attrib.get("lon")
            if lat is None or lon is None:
                continue

            time_val = None
            for child in elem:
                if child.tag.endswith("time") and child.text:
                    time_val = child.text
                    break

            if time_val:
                pts.append({
                    "t": _naive(time_val),
                    "lat": float(lat),
                    "lon": float(lon)
                })

    if not pts:
        print(f"[WARN] No track points parsed from '{path}'.")
        return pd.DataFrame(columns=["t", "lat", "lon"])

    return pd.DataFrame(pts)


def smooth_h(h):
    h = np.asarray(h, dtype=float)
    h = np.where(np.isfinite(h), h, np.nan)
    s = pd.Series(h).interpolate(limit_direction="both").values
    if len(s) >= 7:
        s = gaussian_filter1d(s, sigma=1.2)
        w = min(11, len(s) if len(s) % 2 else len(s) - 1)
        if w >= 5:
            s = savgol_filter(s, window_length=w, polyorder=2)
    return np.clip(s, 1.0, 120.0)


def choose_side(track, fiber, gpx_win):
    if gpx_win.empty:
        return 1.0
    f_km, f_lat, f_lon = fiber["das_km"].values, fiber["lat"].values, fiber["lon"].values
    i_lat = interp1d(f_km, f_lat, bounds_error=False, fill_value="extrapolate")
    i_lon = interp1d(f_km, f_lon, bounds_error=False, fill_value="extrapolate")
    d = 0.05
    lat0 = i_lat(track["pos_km"].values)
    lon0 = i_lon(track["pos_km"].values)
    heading = np.arctan2(
        (i_lat(track["pos_km"].values + d) - lat0) * 111139.0,
        (i_lon(track["pos_km"].values + d) - lon0) * 111139.0 * np.cos(np.radians(lat0)),
    )
    h = track["h_smooth"].values
    g_lat = interp1d(gpx_win["t"].astype("int64"), gpx_win["lat"],
                     bounds_error=False, fill_value="extrapolate")
    g_lon = interp1d(gpx_win["t"].astype("int64"), gpx_win["lon"],
                     bounds_error=False, fill_value="extrapolate")
    t_ns = track["t"].astype("int64").values
    gl, go = g_lat(t_ns), g_lon(t_ns)

    def err(sign):
        n = heading + sign * np.pi / 2
        blat = lat0 + (h * np.sin(n)) / 111139.0
        blon = lon0 + (h * np.cos(n)) / (111139.0 * np.cos(np.radians(lat0)))
        return np.nanmean((blat - gl) ** 2 + (blon - go) ** 2)

    e_plus, e_minus = err(+1.0), err(-1.0)
    side = +1.0 if e_plus <= e_minus else -1.0
    print(f"Offset side: {'+90 deg' if side > 0 else '-90 deg'}  "
          f"(AIS MSE +90={e_plus:.2e}, -90={e_minus:.2e})")
    return side


def project(track, fiber, side):
    f_km, f_lat, f_lon = fiber["das_km"].values, fiber["lat"].values, fiber["lon"].values
    i_lat = interp1d(f_km, f_lat, bounds_error=False, fill_value="extrapolate")
    i_lon = interp1d(f_km, f_lon, bounds_error=False, fill_value="extrapolate")
    d = 0.05
    lat0 = i_lat(track["pos_km"].values)
    lon0 = i_lon(track["pos_km"].values)
    heading = np.arctan2(
        (i_lat(track["pos_km"].values + d) - lat0) * 111139.0,
        (i_lon(track["pos_km"].values + d) - lon0) * 111139.0 * np.cos(np.radians(lat0)),
    )
    n = heading + side * np.pi / 2
    h = track["h_smooth"].values
    track = track.copy()
    track["on_lat"] = lat0
    track["on_lon"] = lon0
    track["boat_lat"] = lat0 + (h * np.sin(n)) / 111139.0
    track["boat_lon"] = lon0 + (h * np.cos(n)) / (111139.0 * np.cos(np.radians(lat0)))
    return track


def main():
    if not os.path.exists(TRACK_CSV):
        raise FileNotFoundError(f"Track CSV '{TRACK_CSV}' not found. Run tracker first.")

    track = pd.read_csv(TRACK_CSV)
    if "t" in track.columns:
        track["t"] = track["t"].map(_naive)
    elif "timeStart" in track.columns:
        track["t"] = track["timeStart"].map(_naive)
    else:
        raise KeyError("Neither 't' nor 'timeStart' column found in TRACK_CSV.")

    if "pos_km" not in track.columns:
        if "eventPosition" in track.columns:
            track["pos_km"] = (track["eventPosition"] * 1.024) / 1000.0
        else:
            raise KeyError("Neither 'pos_km' nor 'eventPosition' column found in TRACK_CSV.")

    track["h_raw"] = track.apply(extract_h, axis=1)
    track["h_smooth"] = smooth_h(track["h_raw"])
    track = track.sort_values("t").reset_index(drop=True)

    fiber = load_fiber()
    gpx = load_gpx(GPX_FILE)

    if not gpx.empty and "t" in gpx.columns:
        gpx_win = gpx[(gpx["t"] >= track["t"].min()) & (gpx["t"] <= track["t"].max())].copy()
    else:
        gpx_win = pd.DataFrame(columns=["t", "lat", "lon"])

    print(f"Track pts={len(track)} | AIS in DAS window={len(gpx_win)}")

    side = choose_side(track, fiber, gpx_win)
    track = project(track, fiber, side)

    # ---- Static PNG Map ----
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.plot(fiber["lon"], fiber["lat"], color="black", ls="--", lw=2, label="Fibre cable")
    if not gpx_win.empty:
        ax.plot(gpx_win["lon"], gpx_win["lat"], color="cyan", lw=3, label="AIS/GPX (true)")
    ax.plot(track["on_lon"], track["on_lat"], color="gray", ls=":", lw=1.5,
            label="DAS on-cable (h=0)")
    ax.plot(track["boat_lon"], track["boat_lat"], color="red", lw=2.5, marker="o", ms=4,
            label="DAS 2D (smoothed sourceDistance)")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_title("Fibre + AIS + DAS 2D Trajectory (h Interpolated)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"Saved {OUT_PNG}")

    # ---- Interactive HTML Map ----
    if HAS_FOLIUM:
        m = folium.Map(
            location=[track["boat_lat"].mean(), track["boat_lon"].mean()],
            zoom_start=13, tiles="OpenStreetMap",
        )
        folium.PolyLine(list(zip(fiber["lat"], fiber["lon"])),
                        color="blue", weight=3, popup="Fibre Cable").add_to(m)
        if not gpx_win.empty:
            folium.PolyLine(list(zip(gpx_win["lat"], gpx_win["lon"])),
                            color="cyan", weight=5, popup="AIS/GPX True Track").add_to(m)
        folium.PolyLine(list(zip(track["boat_lat"], track["boat_lon"])),
                        color="red", weight=4, popup="DAS 2D Track").add_to(m)
        folium.Marker(
            [track["boat_lat"].iloc[0], track["boat_lon"].iloc[0]],
            popup=f"DAS START {track['t'].iloc[0]}",
            icon=folium.Icon(color="green", icon="play"),
        ).add_to(m)
        folium.Marker(
            [track["boat_lat"].iloc[-1], track["boat_lon"].iloc[-1]],
            popup=f"DAS END {track['t'].iloc[-1]}",
            icon=folium.Icon(color="red", icon="stop"),
        ).add_to(m)
        m.save(OUT_HTML)
        print(f"Saved {OUT_HTML}")


if __name__ == "__main__":
    main()