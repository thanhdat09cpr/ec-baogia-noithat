"""
Phase 4 — kiểm job nền: submit trả job_id (không block), chặn trùng phòng, reaper dọn mồ côi,
status scope theo user (403/404). KHÔNG gọi API thật (patch executor để worker không chạy).
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMPDB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMPDB.close()
os.environ["DATABASE_URL"] = "sqlite:///" + _TMPDB.name.replace("\\", "/")
sys.path.insert(0, ROOT)

from webapp import app as app_module  # noqa: E402
from webapp import jobs  # noqa: E402
from webapp.db import db_session  # noqa: E402
from webapp.models import TakeoffJob, User  # noqa: E402


class _FakeExecutor:
    """Không chạy worker → job giữ nguyên 'pending' để test logic điều phối."""
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args):
        self.submitted.append((fn, args))
        return None


class Phase4JobsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._proj_tmp = tempfile.TemporaryDirectory()
        app_module.PROJECTS = cls._proj_tmp.name
        app_module.app.config["TESTING"] = True
        cls.client = app_module.app.test_client()
        jobs._executor = _FakeExecutor()  # chặn worker chạy do_takeoff thật

    @classmethod
    def tearDownClass(cls):
        from webapp.db import engine
        db_session.remove()
        engine.dispose()
        cls._proj_tmp.cleanup()
        try:
            os.unlink(_TMPDB.name)
        except OSError:
            pass

    def _project_with_pdf(self, ma="GR1"):
        pid = self.client.post("/api/project", json={"du_an": "Job Test"}).get_json()["project_id"]
        input_dir = os.path.join(app_module.PROJECTS, pid, "input")
        os.makedirs(input_dir, exist_ok=True)
        with open(os.path.join(input_dir, f"{app_module.slug(ma)}.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 dummy")
        return pid

    def test_takeoff_returns_job_without_block(self):
        pid = self._project_with_pdf("GR1")
        r = self.client.post("/api/takeoff", json={
            "project_id": pid, "room": {"ma": "GR1", "ten": "Phòng"}, "scope": ["I.1"]})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "pending")
        self.assertTrue(body["created"])
        self.assertTrue(body["job_id"])

    def test_no_pdf_returns_400(self):
        pid = self.client.post("/api/project", json={"du_an": "No PDF"}).get_json()["project_id"]
        r = self.client.post("/api/takeoff", json={
            "project_id": pid, "room": {"ma": "GR9", "ten": "P"}, "scope": ["I.1"]})
        self.assertEqual(r.status_code, 400)

    def test_duplicate_room_blocked(self):
        pid = self._project_with_pdf("GR2")
        room = {"ma": "GR2", "ten": "Phòng"}
        first = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()
        second = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])          # phòng đang chạy → không tạo job mới
        self.assertEqual(first["job_id"], second["job_id"])

    def test_status_route(self):
        pid = self._project_with_pdf("GR3")
        job_id = self.client.post("/api/takeoff", json={
            "project_id": pid, "room": {"ma": "GR3", "ten": "P"}}).get_json()["job_id"]
        r = self.client.get(f"/api/takeoff/status/{job_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "pending")

    def test_status_unknown_404(self):
        self.assertEqual(self.client.get("/api/takeoff/status/khong-co").status_code, 404)

    def test_status_403_for_non_owner(self):
        pid = self._project_with_pdf("GR4")
        job_id = self.client.post("/api/takeoff", json={
            "project_id": pid, "room": {"ma": "GR4", "ten": "P"}}).get_json()["job_id"]
        # Gán job cho user khác; current_user (intruder, non-admin) không phải chủ → 403.
        other = User(email="owner4@eurostyle.com.vn", role="user", status="approved")
        intruder = User(email="intruder4@eurostyle.com.vn", role="user", status="approved")
        db_session.add_all([other, intruder])
        db_session.commit()
        db_session.get(TakeoffJob, job_id).user_id = other.id
        db_session.commit()
        orig = app_module.current_user
        app_module.current_user = lambda: db_session.get(User, intruder.id)
        try:
            self.assertEqual(self.client.get(f"/api/takeoff/status/{job_id}").status_code, 403)
        finally:
            app_module.current_user = orig

    def test_rerun_room_after_done_no_collision(self):
        # Critical #1: bóc lại phòng đã 'done' phải tạo job mới + chốt done lại KHÔNG đụng ràng buộc.
        pid = self._project_with_pdf("GR6")
        room = {"ma": "GR6", "ten": "P"}
        j1 = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()["job_id"]
        job1 = db_session.get(TakeoffJob, j1)
        job1.status = "done"; db_session.commit()               # phòng đã bóc xong
        second = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()
        self.assertTrue(second["created"])                       # tạo job mới (không bị chặn)
        self.assertNotEqual(second["job_id"], j1)
        # mô phỏng worker chốt done cho job2 — trước fix sẽ IntegrityError vì trùng (project,room,status)
        job2 = db_session.get(TakeoffJob, second["job_id"])
        job2.status = "done"
        db_session.commit()                                      # không được raise
        self.assertEqual(db_session.get(TakeoffJob, second["job_id"]).status, "done")

    def test_reaper_no_collision_with_terminal_job(self):
        # reaper set 'error' cho job running mồ côi dù đã có job 'error'/'done' cùng phòng.
        pid = self._project_with_pdf("GR7")
        room = {"ma": "GR7", "ten": "P"}
        j1 = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()["job_id"]
        db_session.get(TakeoffJob, j1).status = "error"; db_session.commit()
        j2 = self.client.post("/api/takeoff", json={"project_id": pid, "room": room}).get_json()["job_id"]
        job2 = db_session.get(TakeoffJob, j2)
        job2.status = "running"
        job2.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        db_session.commit()
        self.assertGreaterEqual(jobs.reap_orphans(), 1)          # không raise IntegrityError
        db_session.expire_all()
        self.assertEqual(db_session.get(TakeoffJob, j2).status, "error")

    def test_reaper_marks_orphan_error(self):
        pid = self._project_with_pdf("GR5")
        job_id = self.client.post("/api/takeoff", json={
            "project_id": pid, "room": {"ma": "GR5", "ten": "P"}}).get_json()["job_id"]
        job = db_session.get(TakeoffJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        db_session.commit()
        n = jobs.reap_orphans()
        self.assertGreaterEqual(n, 1)
        db_session.expire_all()
        self.assertEqual(db_session.get(TakeoffJob, job_id).status, "error")


if __name__ == "__main__":
    unittest.main()
