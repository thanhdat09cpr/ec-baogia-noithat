---
phase: 1
title: "Chuẩn hóa chạy Linux/Docker"
status: done
priority: P1
effort: "0.5d"
dependencies: []
---

# Phase 1: Chuẩn hóa chạy Linux/Docker

## Overview
Bỏ ràng buộc Windows để app chạy trên VPS Linux; đóng gói Docker. Tiền đề cho mọi pha sau.

## Requirements
- Functional: 4 bước hiện tại chạy được trên Linux container; xuất Excel không lỗi path.
- Non-functional: image dựng lại 1 lệnh; khởi động qua gunicorn (không dùng dev server).

## Architecture
Nút chặn gốc: `webapp/app.py:18` `VPY = ROOT/.venv/Scripts/python.exe` (Windows) + `run_script()`
spawn subprocess tới path đó. Trên Linux path này không tồn tại → `/api/moi-thau`, `/api/bao-gia` chết.

Giải pháp — **gọi hàm trực tiếp thay vì subprocess**:
- Thêm entry callable vào 2 script build (giữ `__main__` cũ để CLI vẫn chạy):
  - `build_boq_xlsx.build(project_dir) -> out_path`
  - `build_baogia_xlsx.build(project_dir, profit=None) -> out_path`
  - Hiện `main()` đọc `sys.argv`/argparse → refactor tách phần lõi ra hàm `build(...)`, `main()` chỉ parse args rồi gọi `build()`.
- `app.py`: bỏ `VPY`, `run_script()`; import 2 module, gọi `build()` trong try/except, trả lỗi rõ.
- Loại rủi ro encoding (subprocess `PYTHONIOENCODING`) vì chạy in-process.

## Related Code Files
- Modify: `webapp/app.py` (bỏ VPY & run_script; import build modules; `/api/moi-thau`, `/api/bao-gia`)
- Modify: `scripts/build_boq_xlsx.py`, `scripts/build_baogia_xlsx.py` (tách `build()` khỏi `main()`)
- Create: `webapp/Dockerfile`, `webapp/gunicorn.conf.py`, `.dockerignore`, `webapp/requirements-web.txt` (rà lại)

## Implementation Steps
1. Refactor `build_boq_xlsx.py`: `def build(project_dir): ...` ; `main()` gọi `build(sys.argv[1])`.
2. Refactor `build_baogia_xlsx.py`: `def build(project_dir, profit=None): ...` ; `main()` parse argparse rồi gọi.
3. `app.py`: `from scripts import build_boq_xlsx, build_baogia_xlsx`; thay `run_script(...)` bằng gọi hàm; bắt exception → trả `{ok:false,error}`.
4. Dockerfile: `python:3.12-slim`; `pip install -r requirements.txt -r webapp/requirements-web.txt`; copy repo; `CMD gunicorn -c webapp/gunicorn.conf.py app:app`.
5. gunicorn.conf: `workers=2, threads=4, timeout=300` (takeoff dài — sẽ giảm sau khi có pha 4).
6. Rà requirements: giữ PyMuPDF, openpyxl, Pillow, rapidfuzz, flask, anthropic; cắt pandas/pdfplumber nếu grep xác nhận không dùng.
7. `docker build` + `docker run` → chạy tay 4 bước với dự án mẫu.

## Success Criteria
- [ ] `docker run` khởi động app, mở được UI.
- [ ] Chạy trọn 4 bước (tạo dự án → bóc → mời thầu → báo giá) trong container Linux, xuất được 2 file .xlsx.
- [ ] `scripts/*.py` vẫn chạy độc lập qua CLI (không phá bản cũ).

## Hardening (red-team — bắt buộc)
- **F1 — sửa `lib_boq.to_number` cho số VN:** chuỗi khớp `^\d{1,3}([.,]\d{3})+$` → bỏ hết dấu ngăn
  nghìn (`12.500`→12500, `2.500.000`→2500000). Chỉ coi là thập phân khi 1 dấu + ≤2 chữ số sau. Viết unit test bảng giá VN.
- **F1 — fixture round-trip CÓ giá NCC:** dùng `GR1.thuc-tham-chieu.csv` (đã có giá) làm test GĐ2 →
  xác nhận báo giá lệch 0 (không chỉ mời thầu). Không tin "lệch 0" cho GĐ2 tới khi test này xanh.
- **F8:** `build()` trả thêm dict thống kê (`n_no_price`, `n_img`) để UI vẫn nhận cảnh báo (không mất khi bỏ subprocess). Thêm `scripts/__init__.py`.

## Risk Assessment
- **PyMuPDF thiếu system lib trên slim image** → nếu wheel manylinux không đủ, thêm `apt-get install libgl1` (hiếm). Mitigation: test trong build.
- **Refactor build scripts phá round-trip** → chạy lại round-trip 68-Tho-Nhuom sau refactor, phải vẫn lệch 0.
- **Import path `scripts`** → thêm `scripts/__init__.py` hoặc sửa sys.path; test import.
