# Hướng dẫn chạy trên Windows (sau khi pull về)

Mục tiêu: pull repo về máy Windows là chạy + tiếp tục triển khai được ngay.

## 1. Chuẩn bị môi trường (1 lần)

```powershell
# Trong thư mục E&C
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt -r webapp\requirements-web.txt
```

> `.venv\` KHÔNG được commit (mỗi máy tự tạo). `projects\` (dữ liệu 2 dự án cũ),
> file `.xlsx`/`.pdf` cũng không lên git — copy tay nếu cần chạy round-trip với dữ liệu thật.

## 2. Kiểm chứng Phase 1 (phải xanh)

```powershell
.venv\Scripts\python.exe tests\test-to-number.py
.venv\Scripts\python.exe tests\test-round-trip-68-tho-nhuom.py
```

Round-trip 68-Tho-Nhuom phải **lệch 0** (GĐ1 mời thầu + GĐ2 báo giá có giá NCC).

## 3. Chạy web app (bản Phase 1 hiện tại)

```powershell
.venv\Scripts\python.exe webapp\app.py
# mở http://127.0.0.1:5000
```

## 4. Tiếp tục triển khai (Phase 2 → 6)

Mở Claude Code trong thư mục `E&C` và nói: **"tiếp tục cook Phase 2"**.
Agent đọc `plans/20260702-webapp-multiuser-hoan-chinh/` để chạy tiếp.

- **Phase 2–6 cần Postgres.** Trên Windows dùng **Docker Desktop** (khớp bản deploy):
  `docker compose up -d` (khi đã tới Phase 6), hoặc dev nhanh bằng SQLite qua biến
  môi trường `DATABASE_URL=sqlite:///dev.db` (code Phase 2 sẽ hỗ trợ DATABASE_URL).
- Dependencies Phase 2–6 đã khai trong `webapp\requirements-web.txt` (cài ở bước 1).

## Trạng thái hiện tại

| Phase | Trạng thái |
|-------|-----------|
| 1. Chuẩn hóa Linux/Docker | ✅ XONG (verified: test_to_number + round-trip lệch 0) |
| 2. PostgreSQL + mô hình dữ liệu | ⬜ chưa bắt đầu (bắt đầu từ đây) |
| 3. Google OAuth + admin duyệt | ⬜ |
| 4. Bóc chạy nền | ⬜ |
| 5. Frontend + nhập giá NCC | ⬜ |
| 6. Deploy VPS | ⬜ (đã có sẵn `docker-compose.yml` nháp) |

Chi tiết: `plans/20260702-webapp-multiuser-hoan-chinh/plan.md`.
