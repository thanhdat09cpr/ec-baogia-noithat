---
phase: 4
title: "Bóc khối lượng chạy nền"
status: pending
priority: P2
effort: "1d"
dependencies: [3]
---

# Phase 4: Bóc khối lượng chạy nền

## Overview
Bóc AI mất 1–3 phút/phòng, hiện gọi đồng bộ → treo. Chuyển sang job nền + polling.
Kiến trúc (đã chốt, đội <10): **1 gunicorn worker gthread + ThreadPoolExecutor** (đơn giản, bền).

## Requirements
- Functional: bấm bóc → job nền, trả `job_id`; UI polling; xong đổ bảng + lưu CSV.
- Non-functional: nhiều người bóc song song không treo; token/model lưu DB (chỉ LOG, chưa chặn quota — v2).

## Architecture
- 1 worker gthread → mọi request cùng process → KHÔNG cần polling chéo worker. Executor tạo
  **lazy per-worker** (không `preload_app`, tránh fork hỏng).
- `/api/takeoff` (POST): **KHÔNG nhận api_key/model từ client** (N3) — key/model đọc server-side
  (DB/env, allowlist). Tạo `TakeoffJob(id=uuid, status=pending, started_at)`; submit; trả `job_id`.
- Worker `run_takeoff_job`: set running, gọi `do_takeoff` (key server-side), lưu tokens+model+CSV, set done/error.
- **Reaper (O1):** lúc boot + định kỳ, job `running` quá TTL (vd 10') → `error`; lock tự nhả.
- **Chống trùng (F7/C1):** UNIQUE DB `(project_id, room_ma)` cho job đang pending/running
  (thay check-then-insert); ghi CSV atomic (`os.replace`). Giới hạn số job chạy/người.
- `/api/takeoff/status/<job_id>` (GET): **join `user_id=current_user`** (N1) → `{status,error?,rows?,usage?}`.

## Related Code Files
- Create: `webapp/jobs.py` (executor lazy, run_takeoff_job, reaper)
- Modify: `webapp/app.py` (`/api/takeoff` bỏ api_key/model client; `/api/takeoff/status/<id>` scope user), `webapp/static/app.js` (polling + progress)
- Modify: `webapp/gunicorn.conf.py` (`workers=1, worker_class=gthread, threads=8`; timeout thường)

## Implementation Steps
1. `jobs.py`: executor lazy + `run_takeoff_job(job_id)` (running→done/error, lưu tokens+CSV atomic) + `reap_orphans()`.
2. `/api/takeoff`: bỏ api_key/model khỏi payload; tạo job (uuid) + UNIQUE check; submit; trả id.
3. `/api/takeoff/status/<id>`: scope theo user_id; trả trạng thái/rows/usage.
4. Frontend: nút bóc → job → poll ~2s → progress → render bảng (giữ sửa tay).
5. Lỗi rõ (key sai/PDF hỏng/quá token). Reaper chạy lúc startup + timer.
6. Test: 3 job song song; 1 job "mồ côi" được reaper dọn; trùng phòng bị chặn.

## Success Criteria
- [ ] Bóc không block; UI hiện tiến trình từng phòng.
- [ ] 3 người bóc cùng lúc không treo.
- [ ] Token+model lưu `TakeoffJob`; client KHÔNG truyền được key/model.
- [ ] Job `running` mồ côi bị reaper đánh `error`, không khóa phòng vĩnh viễn.

## Risk Assessment
- **1 worker gthread giới hạn CPU song song** → đủ cho <10 người (I/O-bound chờ API); nâng RQ+Redis nếu vượt.
- **Executor tạo sai lúc (preload)** → tạo lazy sau fork; test.
- **Ghi CSV đè khi trùng** → UNIQUE + atomic replace.
