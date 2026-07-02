# Deploy lên VPS (Docker Compose + Postgres + Caddy HTTPS)

Bản đa người dùng. **Trạng thái hiện tại: auth Google đang HOÃN** — ai vào được domain là dùng
được (chung 1 user hệ thống). Khi bật lại auth (Phase 3), thêm biến `GOOGLE_*`/`ADMIN_EMAILS`.

## 0. Test local TRƯỚC khi lên VPS (khuyến nghị)
```powershell
.venv\Scripts\python.exe webapp\app.py     # http://127.0.0.1:5000 (SQLite, không cần Docker)
```
Chạy test:
```powershell
.venv\Scripts\python.exe tests\test-phase2-multiuser.py
.venv\Scripts\python.exe tests\test-phase4-jobs.py
.venv\Scripts\python.exe tests\test-phase5-frontend-api.py
.venv\Scripts\python.exe tests\test-to-number.py
```

## 1. Chuẩn bị (một lần)
1. **VPS Linux** có Docker + Docker Compose plugin. Mở firewall **port 80 & 443**.
2. **DNS**: tạo A-record `DOMAIN` (vd `baogia.eurostyle.com.vn`) trỏ về **IP VPS TRƯỚC** khi chạy
   Caddy (ACME cần DNS resolve + port 80). Kiểm: `dig +short baogia.eurostyle.com.vn`.
3. **ANTHROPIC_API_KEY** chung của công ty.

## 2. Cấu hình
```bash
git clone <repo> && cd ec-baogia-noithat
cp .env.example .env
nano .env          # điền POSTGRES_PASSWORD, DATABASE_URL, ANTHROPIC_API_KEY, SECRET_KEY, DOMAIN, ACME_EMAIL
```
- `SECRET_KEY`: `python -c "import secrets;print(secrets.token_urlsafe(48))"`
- `DATABASE_URL` phải khớp user/pass/db ở trên, host = `db` (tên service): 
  `postgresql+psycopg://baogia:<pass>@db:5432/baogia`

## 3. Chạy
```bash
docker compose up -d --build
docker compose ps            # db healthy, migrate exited 0, app healthy, caddy up
docker compose logs migrate  # xác nhận "Running upgrade -> 0001_initial"
```
Thứ tự tự động: `db` (healthy) → `migrate` (alembic upgrade head, one-shot) → `app` → `caddy` (xin cert).

## 4. Đưa 2 dự án legacy lên (nếu cần)
```bash
# copy thư mục dự án cũ vào volume projects/ (bind mount ./projects)
scp -r 68-Tho-Nhuom ROX2-Z3SL4 user@vps:/path/ec-baogia-noithat/projects/
docker compose exec app python -m webapp.import_legacy_projects
```

## 5. Nghiệm thu
- Mở `https://<DOMAIN>` → cert hợp lệ, trang dashboard hiện.
- Tạo dự án → upload PDF → bóc khối lượng (job nền) → mời thầu → nhập giá NCC → báo giá → tải file.
- `docker compose restart` → dữ liệu (DB + projects/) còn nguyên (volume `pgdata` + bind `./projects`).

## 6. Backup (cron)
```bash
# trong container app (đã có pg_dump? — dùng service db hoặc cài postgresql-client trên host)
docker compose exec app bash webapp/scripts/backup.sh   # đặt BACKUP_DIR, GPG_RECIPIENT qua env
```
Khuyến nghị: cron host chạy `pg_dump` qua `docker compose exec db pg_dump` + tar `projects/`, mã hóa GPG.

## Nâng cấp code
```bash
git pull && docker compose up -d --build   # migrate tự chạy lại (idempotent) trước app
```

## Còn thiếu (làm sau)
- **Auth Google (Phase 3)**: bật lại đăng nhập + admin duyệt; thêm cookie `SESSION_COOKIE_SECURE=1`
  (đặt env `COOKIE_SECURE=1`), CSRF, rate-limit. Cần `GOOGLE_CLIENT_ID/SECRET` + redirect
  `https://<DOMAIN>/auth/callback`.
- **Round-trip 68-Tho-Nhuom** nên chạy lại trên máy có dữ liệu thật để chốt số GĐ1/GĐ2.
- **Enforce quota token** (v2) — hiện chỉ LOG token vào `takeoff_jobs`.
