---
phase: 2
title: "PostgreSQL + mô hình dữ liệu + tách dự án theo người"
status: pending
priority: P1
effort: "1.5d"
dependencies: [1]
---

# Phase 2: PostgreSQL + mô hình dữ liệu + tách dự án theo người

## Overview
Thêm PostgreSQL quản metadata (user, dự án, job, usage). Mỗi dự án có ID riêng + chủ sở hữu →
hết cảnh trùng tên ghi đè. File Excel/CSV/PDF vẫn nằm trên đĩa, DB chỉ index.

## Requirements
- Functional: 2 người tạo dự án trùng tên → 2 bản ghi + 2 thư mục riêng; đọc/ghi BOQ theo project.id.
- Non-functional: migration versioned (Alembic); 2 dự án cũ (68-Tho-Nhuom, ROX2) import được, không mất dữ liệu.

## Architecture
Nút chặn gốc: `app.py` `pdir(name)=PROJECTS/slug(name)` → cùng tên = cùng thư mục = **ghi đè**.

Đổi sang: thư mục dự án = `projects/<project.id>/` (id = uuid). Cấu trúc con giữ nguyên
(`input/`, `01-extract/`, `02-boq/`, `03-baogia/`, `cau-hinh.json`).

**Models (SQLAlchemy):**
- `User(id, email UNIQUE, name, google_sub, role[user|admin], status[pending|approved|rejected], created_at)`
- `Project(id uuid, owner_id FK→User, ten, slug, dia_diem, hang_muc, status[draft|takeoff|awaiting_ncc|quoted], created_at, updated_at)` — đường dẫn suy ra từ id.
- `TakeoffJob(id, project_id FK, user_id FK, room_ma, status[pending|running|done|error], model, input_tokens, output_tokens, error, created_at, finished_at)` — vừa là job (pha 4) vừa là usage log để tính chi phí.

Config nghiệp vụ (profit/scope/phong/preliminaries) VẪN ở `cau-hinh.json` trong thư mục dự án
(tái dùng `lib_boq.load_config` không đổi) — DB chỉ giữ metadata + quyền sở hữu.

## Related Code Files
- Create: `webapp/models.py`, `webapp/db.py` (engine/session), `webapp/migrations/` (Alembic), `webapp/import_legacy_projects.py`
- Modify: `webapp/app.py` (`pdir` → theo id; route project CRUD gắn owner; đọc/ghi BOQ theo id)

## Implementation Steps
1. Thêm SQLAlchemy + psycopg + Alembic; kết nối qua `DATABASE_URL`.
2. Viết `models.py` (User/Project/TakeoffJob) + `db.py`.
3. `alembic init` + migration đầu tạo 3 bảng.
4. `pdir(project_id)` = `PROJECTS/<id>`; helper `project_dir(project)`.
5. Route `/api/project` (POST): tạo `Project` (owner=current_user — tạm hardcode tới khi pha 3), mkdir `projects/<id>`, ghi `cau-hinh.json`. Trả `project_id`.
6. Sửa `read_boq/write_boq/upload/pdf/download/moi-thau/bao-gia` nhận `project_id` (uuid) thay vì slug tên.
7. Route `/api/projects` (GET): list dự án của owner (chuẩn bị dashboard pha 5).
8. `import_legacy_projects.py`: quét `projects/68-Tho-Nhuom`, `projects/ROX2-Z3SL4` → tạo Project record trỏ tới thư mục cũ (giữ nguyên tên thư mục cho 2 dự án legacy; dự án mới dùng uuid).

## Success Criteria
- [ ] Tạo 2 dự án cùng tên "Dự án X" → 2 id, 2 thư mục, không đè nhau.
- [ ] BOQ/Excel đọc-ghi đúng theo project.id.
- [ ] 2 dự án legacy hiện trong danh sách, mở + build lại ra đúng số cũ (round-trip lệch 0).

## Hardening (red-team — bắt buộc)
- **F2 — cột `dir_name` trong `Project`:** `project_dir()` đọc cột này (mới = uuid, legacy = tên
  thư mục cũ). KHÔNG suy đường dẫn thuần từ id → tránh 68/ROX2 báo FileNotFound.
- **N1 — `TakeoffJob.id` = UUID** (không int tuần tự, tránh đoán/IDOR).
- **N1 — helper `load_project_or_403(id)`:** `p=Project.get_or_404(id); if p.owner_id!=current_user.id and not is_admin: abort(403)`. MỌI route project/pdf/download/boq/moi-thau/bao-gia/status PHẢI đi qua helper này (không kiểm rời rạc).

## Risk Assessment
- **Migrate legacy sai** → giữ nguyên thư mục 68/ROX2, chỉ thêm record trỏ vào; test build lại.
- **owner_id chưa có ở pha 2** (auth ở pha 3) → tạm gán 1 user hệ thống/seed admin; nối current_user ở pha 3.
- **Rò rỉ dữ liệu giữa user** → mọi truy vấn Project phải filter `owner_id` (admin thấy tất) — bắt buộc test ở pha 3.
