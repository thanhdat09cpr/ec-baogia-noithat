"""
Phase 5 — kiểm hợp đồng API mà frontend mới phụ thuộc: trang render, mở lại dự án (GET config),
lưu giá NCC + profit_override per-dòng (F3) không mất.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMPDB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMPDB.close()
os.environ["DATABASE_URL"] = "sqlite:///" + _TMPDB.name.replace("\\", "/")
sys.path.insert(0, ROOT)

from webapp import app as app_module  # noqa: E402
from webapp.db import db_session  # noqa: E402


class Phase5FrontendApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._proj_tmp = tempfile.TemporaryDirectory()
        app_module.PROJECTS = cls._proj_tmp.name
        app_module.app.config["TESTING"] = True
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        from webapp.db import engine
        db_session.remove(); engine.dispose(); cls._proj_tmp.cleanup()
        try:
            os.unlink(_TMPDB.name)
        except OSError:
            pass

    def test_index_renders_dashboard_and_5_steps(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn('id="dashboard"', html)
        self.assertIn('data-w="5"', html)              # wizard 5 bước (app-shell mockup v3)
        self.assertIn('class="shell"', html)           # app-shell sidebar + topbar
        self.assertNotIn('id="api_key"', html)         # N3: bỏ input key khỏi client
        self.assertNotIn('id="model"', html)           # N3: bỏ chọn model khỏi client

    def test_reopen_project_returns_config(self):
        pid = self.client.post("/api/project", json={
            "du_an": "Mở lại", "dia_diem": "HN", "profit_percent": 12.5,
            "phong": [{"ma": "GR1", "ten": "King", "so_luong": 5}]}).get_json()["project_id"]
        d = self.client.get(f"/api/project/{pid}").get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["config"]["profit_percent"], 12.5)
        self.assertEqual(d["config"]["phong"][0]["ma"], "GR1")

    def test_price_entry_persists_don_gia_and_profit_override(self):
        pid = self.client.post("/api/project", json={"du_an": "Giá NCC"}).get_json()["project_id"]
        rows = [{"nhom_ma": "I.1", "nhom_ten": "Đồ rời", "hang_muc": "Giường", "don_vi": "cai",
                 "kl_1phong": "1", "don_gia_ncc": "2.500.000", "profit_override": "15"}]
        self.client.post("/api/boq", json={"project_id": pid, "ma": "GR1", "rows": rows})
        got = self.client.get("/api/boq", query_string={"project_id": pid, "ma": "GR1"}).get_json()["rows"]
        self.assertEqual(got[0]["don_gia_ncc"], "2.500.000")
        self.assertEqual(got[0]["profit_override"], "15")


if __name__ == "__main__":
    unittest.main()
