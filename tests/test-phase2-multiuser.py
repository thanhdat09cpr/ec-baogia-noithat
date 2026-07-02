"""
Phase 2 — kiểm mô hình đa người dùng + tách dự án theo id (không đè khi trùng tên).

Dùng DB SQLite tạm + thư mục projects tạm (không đụng dữ liệu thật). Không cần Postgres/API.
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
from webapp.models import Project, User  # noqa: E402


class Phase2MultiuserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._proj_tmp = tempfile.TemporaryDirectory()
        app_module.PROJECTS = cls._proj_tmp.name  # tách khỏi projects/ thật
        app_module.app.config["TESTING"] = True
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        from webapp.db import engine
        db_session.remove()
        engine.dispose()  # nhả kết nối để Windows cho xoá file DB
        cls._proj_tmp.cleanup()
        try:
            os.unlink(_TMPDB.name)
        except OSError:
            pass

    def _create(self, ten="Dự án X"):
        r = self.client.post("/api/project", json={"du_an": ten})
        self.assertEqual(r.status_code, 200)
        return r.get_json()["project_id"]

    def test_same_name_two_projects_no_overwrite(self):
        id1 = self._create("Dự án Trùng Tên")
        id2 = self._create("Dự án Trùng Tên")
        self.assertNotEqual(id1, id2)
        d1 = os.path.join(app_module.PROJECTS, id1, "cau-hinh.json")
        d2 = os.path.join(app_module.PROJECTS, id2, "cau-hinh.json")
        self.assertTrue(os.path.isfile(d1))
        self.assertTrue(os.path.isfile(d2))
        self.assertNotEqual(os.path.dirname(d1), os.path.dirname(d2))

    def test_boq_read_write_by_id(self):
        pid = self._create("Dự án BOQ")
        rows = [{"nhom_ma": "I.1", "hang_muc": "Giường", "don_vi": "cai",
                 "kl_1phong": "1", "profit_override": "15"}]
        r = self.client.post("/api/boq", json={"project_id": pid, "ma": "GR1", "rows": rows})
        self.assertEqual(r.status_code, 200)
        got = self.client.get("/api/boq", query_string={"project_id": pid, "ma": "GR1"})
        data = got.get_json()["rows"]
        self.assertEqual(len(data), 1)
        # F3: profit_override phải được giữ lại (nằm trong CSV_COLS).
        self.assertEqual(data[0]["profit_override"], "15")

    def test_projects_list(self):
        before = len(self.client.get("/api/projects").get_json()["projects"])
        self._create("Dự án List A")
        after = len(self.client.get("/api/projects").get_json()["projects"])
        self.assertEqual(after, before + 1)

    def test_unknown_project_404(self):
        r = self.client.get("/api/boq", query_string={"project_id": "khong-ton-tai", "ma": "GR1"})
        self.assertEqual(r.status_code, 404)

    def test_ownership_403_for_non_owner(self):
        # Dự án của user khác; current_user (non-admin) không phải owner → 403.
        pid = self._create("Dự án Người Khác")
        other = User(email="other@eurostyle.com.vn", name="Khác", role="user", status="approved")
        db_session.add(other)
        db_session.commit()
        p = db_session.get(Project, pid)
        p.owner_id = other.id
        db_session.commit()

        intruder = User(email="intruder@eurostyle.com.vn", name="Kẻ lạ",
                        role="user", status="approved")
        db_session.add(intruder)
        db_session.commit()

        orig = app_module.current_user
        app_module.current_user = lambda: db_session.get(User, intruder.id)
        try:
            r = self.client.get("/api/boq", query_string={"project_id": pid, "ma": "GR1"})
            self.assertEqual(r.status_code, 403)
        finally:
            app_module.current_user = orig


if __name__ == "__main__":
    unittest.main()
