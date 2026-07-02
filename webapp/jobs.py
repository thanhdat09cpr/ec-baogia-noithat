"""
jobs.py — Bóc khối lượng CHẠY NỀN (background job) cho web app.

Kiến trúc (đã chốt, đội <10): 1 gunicorn worker `gthread` + `ThreadPoolExecutor`.
Mọi request cùng process → không cần polling chéo worker. Executor tạo LAZY per-worker
(không `preload_app` → tránh fork hỏng).

- `submit_takeoff(...)` : tạo `TakeoffJob(pending)`, chặn trùng phòng đang pending/running, submit.
- `run_takeoff_job(...)`: worker chạy trong THREAD RIÊNG → dùng session thread-local riêng;
  gọi `do_takeoff` (key/model SERVER-SIDE, N3), ghi CSV atomic, lưu token+model, done/error.
- `reap_orphans()`      : job `running` quá TTL → `error` (O1), nhả khóa phòng.
"""
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from webapp.db import db_session
from webapp.models import Project, TakeoffJob

JOB_TTL = timedelta(minutes=10)     # job running lâu hơn TTL coi như mồ côi
MAX_WORKERS = 4

_executor = None
_executor_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC (khớp models._now)


def executor():
    """Tạo ThreadPoolExecutor một lần cho mỗi worker (lazy, sau fork)."""
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=MAX_WORKERS,
                                               thread_name_prefix="takeoff")
    return _executor


def active_job(project_id, room_ma):
    """Job đang pending/running cho phòng này (None nếu không có)."""
    return (db_session.query(TakeoffJob)
            .filter(TakeoffJob.project_id == project_id,
                    TakeoffJob.room_ma == room_ma,
                    TakeoffJob.status.in_(["pending", "running"]))
            .first())


def submit_takeoff(project_id, user_id, room, scope, api_key=None):
    """Tạo job + submit. Trả (job, created). Nếu phòng đang chạy → trả job cũ, created=False.
    api_key (nếu có) truyền thẳng vào thread job — KHÔNG lưu DB; để None thì dùng key server."""
    reap_orphans()  # dọn job mồ côi trước khi nhận việc mới (chặn khóa phòng vĩnh viễn)
    existing = active_job(project_id, room["ma"])
    if existing is not None:
        return existing, False
    job = TakeoffJob(id=str(uuid.uuid4()), project_id=project_id, user_id=user_id,
                     room_ma=room["ma"], status="pending")
    db_session.add(job)
    db_session.commit()
    job_id = job.id
    executor().submit(run_takeoff_job, job_id, room, scope, api_key)
    return job, True


def run_takeoff_job(job_id, room, scope, api_key=None):
    """Chạy trong thread worker. Session thread-local riêng; luôn remove() ở cuối.
    api_key chỉ tồn tại trong bộ nhớ thread (không ghi DB/log)."""
    # Import trong hàm để tránh vòng import (app.py import jobs ở top-level).
    from webapp.app import TAKEOFF_MODEL, do_takeoff, project_dir, slug, write_boq

    try:
        job = db_session.get(TakeoffJob, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now()
        db_session.commit()

        project = db_session.get(Project, job.project_id)
        pdf_path = os.path.join(project_dir(project), "input", f"{slug(room['ma'])}.pdf")
        # Key client gửi (bản test) nếu có; None → SDK đọc ANTHROPIC_API_KEY server-side.
        rows, usage = do_takeoff(pdf_path, room, scope, TAKEOFF_MODEL, api_key)
        write_boq(project, room["ma"], rows)  # atomic os.replace

        job = db_session.get(TakeoffJob, job_id)
        # H3: chỉ chốt 'done' nếu job VẪN đang running (reaper có thể đã đánh 'error' nếu quá TTL).
        if job is not None and job.status == "running":
            job.model = TAKEOFF_MODEL
            job.input_tokens = usage.get("input", 0)
            job.output_tokens = usage.get("output", 0)
            job.status = "done"
            job.finished_at = _now()
            db_session.commit()
    except Exception as e:  # noqa: BLE001 — lưu lỗi vào job, không để chết thread
        db_session.rollback()
        job = db_session.get(TakeoffJob, job_id)
        if job is not None and job.status == "running":  # không đè trạng thái reaper đã set
            job.status = "error"
            job.error = str(e)[:1000]
            job.finished_at = _now()
            db_session.commit()
    finally:
        db_session.remove()  # nhả session thread-local của worker


def reap_orphans():
    """O1: job `running` quá TTL → `error`. Trả số job đã dọn."""
    cutoff = _now() - JOB_TTL
    stuck = (db_session.query(TakeoffJob)
             .filter(TakeoffJob.status == "running",
                     TakeoffJob.started_at.isnot(None),
                     TakeoffJob.started_at < cutoff)
             .all())
    for j in stuck:
        j.status = "error"
        j.error = "Job quá thời gian (reaper dọn)."
        j.finished_at = _now()
    if stuck:
        db_session.commit()
    return len(stuck)
