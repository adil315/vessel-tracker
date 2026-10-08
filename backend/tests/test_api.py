"""API and pipeline regressions; run with `python -m unittest discover -s tests`."""
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from main import app
from pipeline import _load_fiber_latlon, _normalize_track_result, run_tracking


REQUEST = {
    "cable": "s1",
    "algorithm": "VITERBI-BEAM",
    "chain": "Frequency tonality chain",
    "table": "detections",
    "min_od": 22000,
    "max_od": 75000,
    "start_time": "2026-09-29 03:00:00.000000+00",
    "end_time": "2026-09-29 05:00:00.000000+00",
    "conf_min": 0,
    "overlay_ais": False,
}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_preflight_allows_local_dev_origins(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/track",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_preflight_blocks_unlisted_origin(self):
        response = self.client.options(
            "/api/track",
            headers={
                "Origin": "http://unlisted.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_table_name_rejects_sql(self):
        response = self.client.post(
            "/api/track", json={**REQUEST, "table": "detections; DROP TABLE users"},
        )
        self.assertEqual(response.status_code, 422)

    def test_track_returns_cors_headers_even_for_errors(self):
        origin = "http://127.0.0.1:5173"
        with patch("main.run_tracking", side_effect=RuntimeError("test failure")):
            response = self.client.post("/api/track", json=REQUEST, headers={"Origin": origin})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_pipeline_passes_db_config_and_detector_dataframe_to_tracker(self):
        detections = pd.DataFrame([{
            "t": pd.Timestamp("2026-09-29T03:00:00"),
            "t_epoch": 1790650800.0,
            "pos_km": 30.0,
            "z": 24.0,
            "lat": 10.0,
            "lon": 76.0,
        }])

        def load_detections(cfg):
            self.assertIn("db_host", cfg)
            self.assertIn("db_name", cfg)
            self.assertEqual(cfg["table"], "detections")
            return detections

        def track(df):
            self.assertIs(df, detections)
            return df

        with patch("pipeline.db_mod") as db, patch.dict("pipeline.ALGO_MAP", {"VITERBI-BEAM": track}):
            db.load_detections_from_db.side_effect = load_detections
            response = run_tracking(REQUEST)
        self.assertEqual(len(response["fibre_detections"]), 1)
        self.assertEqual(response["fibre_detections"][0]["time"], "2026-09-29T03:00:00")
        self.assertEqual(response["tracks"][0]["points"][0]["time"], "2026-09-29T03:00:00")

    def test_empty_track_has_no_fake_zero_coordinate_point(self):
        result = _normalize_track_result("VITERBI-BEAM", pd.DataFrame(), "#00f")
        self.assertEqual(result["points"], [])

    def test_cable_workbook_uses_requested_sheet_and_offset(self):
        s1 = _load_fiber_latlon("s1")
        s2 = _load_fiber_latlon("s2")
        self.assertTrue(s1)
        self.assertTrue(s2)
        self.assertEqual(s1[0]["km"], 18.0)
        self.assertEqual(s2[0]["km"], 8.0)


if __name__ == "__main__":
    unittest.main()
