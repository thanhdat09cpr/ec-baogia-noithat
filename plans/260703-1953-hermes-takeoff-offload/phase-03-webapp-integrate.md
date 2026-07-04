# Phase 3 — Webapp tích hợp Hermes (bỏ gọi AI trực tiếp)

## Bối cảnh (code hiện tại)
- `webapp/app.py`: `do_takeoff()` (dòng ~243) gọi OpenRouter 1-shot cả PDF → rows JSON.
  `SYSTEM`, `SCHEMA`, `MODELS`, `TAKEOFF_MODEL`, `OPENROUTER_BASE_URL` (dòng ~60-313).
- `webapp/jobs.py`: `submit_takeoff` + `run_takeoff_job` (thread) gọi `do_takeoff`, ghi CSV atomic.
- `/api/takeoff` (dòng ~410), `/api/takeoff/status` (~431). check_boq gọi ở ~449.

## Yêu cầu
Thay bước AI bằng gọi Hermes; giữ nguyên job queue, ghi CSV, check_boq, build, status API.

## Việc làm
1. **Thêm client Hermes** `webapp/hermes_client.py` (FILE-DROP, không network):
   - `submit(project_dir, room, scope, model)`: tạo `<project>/_takeoff/` (mode 0o777 để uid 10000
     ghi status vào được), ghi atomic `<room>.request.json` `{room, scope, model, ts}`.
   - `poll(project_dir, room) -> done{rows} | pending | error`: đọc `_takeoff/<room>.status.json`;
     `done` → đọc `02-boq/<room>.csv`. Có timeout (job treo → error) + xử lỗi rõ ràng.
2. **Sửa `jobs.run_takeoff_job`**: nếu `TAKEOFF_ENGINE=hermes` → `submit` + poll `hermes_client`
   thay `do_takeoff`. Hermes ghi CSV thẳng vào shared dir → webapp chỉ validate cột (CSV_COLS) +
   lưu token/model từ status.json. Giữ nhánh `openrouter` cũ sau cờ để fallback.
3. **Feature flag** `TAKEOFF_ENGINE=hermes|openrouter` (env, mặc định `hermes` sau khi test).
4. **Dọn phụ thuộc AI khỏi app** (khi flag=hermes ổn định): `do_takeoff`, `SYSTEM`, `SCHEMA`,
   `_extract_rows`, `openai` client, `OPENROUTER_API_KEY` cho takeoff → chuyển thành nhánh
   fallback hoặc gỡ. `docker-compose.yml`: bỏ `OPENROUTER_API_KEY`/`TAKEOFF_MODEL` khỏi app
   nếu không còn fallback. (KHÔNG thêm env network nào — file-drop không cần.)
5. **pdf_extract phải chạy trước khi drop request** (Hermes đọc PNG): job chạy `pdf_extract`
   → `01-extract/pages/*.png` tồn tại trong shared volume TRƯỚC khi ghi `*.request.json`.
   Hiện `do_takeoff` gửi PDF thẳng, KHÔNG tách trang → **thêm bước gọi `pdf_extract`**.

## Validation
- `TAKEOFF_ENGINE=hermes`: POST `/api/takeoff` phòng GR1 → job pending → Hermes chạy → CSV về →
  status done → check_boq sạch → build `moi-thau.xlsx`.
- `TAKEOFF_ENGINE=openrouter`: luồng cũ vẫn chạy (fallback còn nguyên).
- Không còn call OpenRouter khi flag=hermes (grep log/network).

## Rủi ro / rollback
- Job treo nếu Hermes lâu/chết → timeout + status=error + cho retry. reap_orphans vẫn dọn.
- Hợp đồng file lệch (tên CSV/room slug) → thống nhất slug giữa 2 bên.
- Rollback: đặt `TAKEOFF_ENGINE=openrouter`, redeploy — về luồng cũ ngay.
