# Báo cáo Phase 2 — PostgreSQL + mô hình dữ liệu + tách dự án theo người

**Ngày:** 2026-07-02 · **Plan:** 20260702-webapp-multiuser-hoan-chinh · **Trạng thái:** ✅ DONE

## Đã làm
- `webapp/db.py` — engine/session SQLAlchemy 2.0; `DATABASE_URL` (Postgres prod) → fallback SQLite `webapp/dev.db` (dev). scoped_session theo thread (khớp gunicorn gthread); teardown nhả phiên.
- `webapp/models.py` — `User` / `Project` / `TakeoffJob`. `Project.dir_name` (F2: đường dẫn thật, mới=uuid, legacy=tên cũ). `TakeoffJob.id`=uuid (N1). UNIQUE (project_id,room_ma,status) chuẩn bị pha 4.
- `webapp/app.py` — refactor: `pdir(name)` → `project_dir(project)` theo `dir_name`; `load_project_or_403()` (N1, mọi route project đi qua); route theo `project_id` (uuid) thay slug tên; thêm `/api/projects` (list theo owner, admin thấy tất), `/api/project` trả `project_id`, `/health`. Owner tạm = user hệ thống seed (pha 3 nối `current_user` thật). F3: `profit_override` vào `CSV_COLS`. Ghi CSV atomic (`os.replace`).
- `webapp/migrations/` — Alembic (alembic.ini + env.py đọc `DATABASE_URL` + metadata từ models) + migration `0001_initial` tạo 3 bảng. UNIQUE inline (tương thích SQLite, không ALTER).
- `webapp/import_legacy_projects.py` — quét `projects/*/cau-hinh.json`, tạo Project trỏ `dir_name`=tên cũ, idempotent.
- `tests/test-phase2-multiuser.py` — Flask test client + SQLite tạm.
- `.gitignore` — thêm `*.db`, `webapp/dev.db`.

## Verify
- `test-phase2-multiuser.py`: **5/5 PASS** — trùng tên→2 id/2 thư mục không đè; BOQ đọc/ghi theo id; F3 giữ `profit_override`; 404 id lạ; 403 non-owner.
- Alembic `upgrade head` → 3 bảng; `downgrade base` → sạch. Chạy trên SQLite; DDL chuẩn cho Postgres.
- `import_legacy_projects` smoke OK; regression `test-to-number` 4/4 PASS.

## Success criteria (phase-02)
- [x] 2 dự án cùng tên → 2 id, 2 thư mục, không đè.
- [x] BOQ/Excel đọc-ghi theo project.id (route + helper).
- [~] Round-trip 2 dự án legacy: cơ chế sẵn (import + dir_name); **chưa chạy được ở clone này** vì `data/` + `projects/` bị gitignore (không có file 68-Tho-Nhuom/ROX2). Cần chạy trên máy có dữ liệu thật.

## Lưu ý / chưa giải quyết
- **Frontend tạm lệch API:** `index.html`/`app.js` vẫn dùng `project` (slug); API đã chuyển sang `project_id`. Sẽ đồng bộ ở **Phase 5**. Giữa pha 2–4 UI cũ chưa chạy full — đúng trình tự plan.
- **Takeoff vẫn đồng bộ + nhận api_key/model từ client** — Phase 4 chuyển job nền + bỏ key client (N3).
- **Phase 3 (Google OAuth) cần credential từ khách** (GOOGLE_CLIENT_ID/SECRET) — phụ thuộc ngoài #1 trong plan; không ver(login flow) được cho tới khi có creds.
- SQLite partial-unique pending/running cho job: pha 4 làm bản Postgres partial index.
