# Báo cáo: xử lý code-review Phase 4/5 + kết quả test local

**Ngày:** 2026-07-02 · **Plan:** 20260702-webapp-multiuser-hoan-chinh

## Review: DONE_WITH_CONCERNS → đã vá

| # | Mức | Vấn đề | Fix |
|---|-----|--------|-----|
| 1 | Critical | UNIQUE `(project_id,room_ma,status)` làm **bóc lại phòng** đụng ràng buộc (done→re-run→done collision; worker error-path & reaper cũng đụng → khóa phòng) | Bỏ constraint khỏi `models.py` + migration. Dựa guard app `jobs.active_job()` (chặn pending/running). Postgres: partial-unique index CHỈ trên `status IN (pending,running)` (dialect-guarded trong migration). |
| 2 | High | `DateTime(timezone=True)` + `_now()` naive → reaper crash trên Postgres (SQLite giấu bug) | Đổi mọi cột thời gian sang **naive** (bỏ `timezone=True`) ở models + migration → đồng nhất SQLite/Postgres. |
| 3 | High | Worker ghi `done` vô điều kiện → đè trạng thái reaper | Chỉ chốt `done`/`error` khi `job.status == "running"`. |
| 5/6 | Medium | KeyError khi thiếu key form/JSON → 400/500 thô | `api_project/upload/takeoff/boq` validate `.get()` → trả 400 thông điệp rõ. |
| 4,7,8 | Low/note | commit-visibility cross-thread; stdout global dưới lock; slug PDF trùng | Ghi nhận, chấp nhận cho đội <10 (không sửa — YAGNI). |

## Verify sau fix
- Test: **Phase 4 9/9** (thêm 2 regression: bóc lại phòng không collision + reaper không đụng terminal job), Phase 2 5/5, Phase 5 3/3, to_number 4/4 — tất cả PASS.
- Alembic `upgrade head`/`downgrade base` trên SQLite: PASS (partial index Postgres bị skip đúng).
- **Chạy server local thật** (`python webapp/app.py`): boot OK, `/health` 200, tạo dự án trả uuid, `/api/projects` list đúng, trang `/` render — tất cả 200.

## Còn lại / chưa giải quyết
- **Round-trip 68-Tho-Nhuom** chưa chạy được ở clone này (thiếu `data/` + `projects/` — gitignore). Cần chạy trên máy có dữ liệu thật để chốt bất biến GĐ1/GĐ2.
- **Bóc AI thật** chưa test (thiếu `ANTHROPIC_API_KEY` + `data/danh-muc-noi-that.csv`). Logic job nền đã test bằng fake executor.
- Chưa có **Postgres CI/smoke** — bug datetime giờ đã vá ở tầng model nên local SQLite đại diện đúng cho Postgres về mặt so sánh thời gian.
- **Phase 6 (deploy VPS)** chưa làm: cần docker-compose (app+db+caddy) + `.env` + deploy.md; cần VPS/DNS từ khách để chạy thật.
