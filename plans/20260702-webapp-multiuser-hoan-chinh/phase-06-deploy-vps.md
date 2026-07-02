---
phase: 6
title: "Deploy VPS (Docker Compose + HTTPS)"
status: config-ready
priority: P1
effort: "1.5d"
dependencies: [1, 2, 3, 4, 5]
---

# Phase 6: Deploy VPS (Docker Compose + HTTPS)

## Overview
Đưa lên VPS Linux bằng Docker Compose: app (gunicorn) + PostgreSQL + Caddy (HTTPS tự động).
v1: LOG chi phí token cho admin xem (CHƯA enforce quota — v2).

## Phụ thuộc bên ngoài (CẦN từ khách)
- VPS (SSH) + **tên miền + DNS A-record trỏ IP TRƯỚC** (Caddy ACME cần DNS resolve + port 80).
- `GOOGLE_CLIENT_ID`/`SECRET` + redirect URI khớp EXACT `https://<domain>/auth/callback`
  (+ redirect `http://localhost:5000/auth/callback` cho dev — tạo TRƯỚC pha 3).
- `ANTHROPIC_API_KEY` chung.

## Requirements
- Functional: vào bằng domain HTTPS, login Google (chặn ngoài domain), admin duyệt, dùng trọn quy trình; dữ liệu bền qua restart.
- Non-functional: HTTPS tự động; secret qua env; migrate one-shot; healthcheck; backup; LOG chi phí/người.

## Architecture
- `docker-compose.yml`: `migrate` (one-shot, chạy `alembic upgrade head` TRƯỚC), `app` (gunicorn
  1 worker gthread), `db` (postgres:16), `caddy` (auto TLS). `depends_on: db condition service_healthy`.
- **O3** healthcheck: `/health` (app) + pg healthcheck. **O2** migrate KHÔNG nằm trong app boot.
- **C2** `ProxyFix(x_proto,x_host)` + cookie Secure/HttpOnly/SameSite + `PREFERRED_URL_SCHEME=https`.
- Volume bền: `pgdata`, `projects/` (`projects/` trong `.dockerignore`, chỉ sống ở volume — O6).
- Secret `.env`: `DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, ANTHROPIC_API_KEY, SECRET_KEY(≥32B), ADMIN_EMAILS(list), USD_VND_RATE`.
- **Chi phí (v1 = LOG):** tính ước tính từ `TakeoffJob` (token×giá model×tỷ giá), hiện cho admin xem theo người/tháng. **Enforce (chặn) = v2.**
- Seed admin idempotent theo `ADMIN_EMAILS`. **T7** backup mã hóa + hạn quyền.

## Related Code Files
- Create: `docker-compose.yml`, `Caddyfile`, `.env.example`, `deploy.md`, `webapp/scripts/backup.sh`
- Modify: `webapp/app.py` (ProxyFix, cookie config, `/health`, đọc key/rate từ env; màn Cài đặt admin xem chi phí — chưa chặn)

## Implementation Steps
1. `docker-compose.yml` (migrate one-shot + app + db + caddy) + volume + healthcheck + depends_on healthy.
2. `Caddyfile` reverse proxy + auto TLS theo domain; email ACME. Mở firewall 80 & 443.
3. `.env.example` + `deploy.md` (tạo OAuth creds, DNS-first, đưa file 2 dự án legacy lên volume bằng scp, set env).
4. `app.py`: ProxyFix + cookie secure + `/health`; màn Cài đặt admin xem chi phí token/người (LOG).
5. Deploy: DNS trỏ sẵn → `docker compose up -d` → migrate chạy → seed admin; cấu hình redirect URI Google đúng domain.
6. Test end-to-end domain thật: login (chặn ngoài domain) → duyệt → bóc → mời thầu → giá NCC → báo giá → tải file.
7. Cron backup mã hóa `pg_dump` + tar `projects/`.

## Success Criteria
- [ ] Domain HTTPS, login Google (chặn ngoài @eurostyle.com.vn), admin duyệt, dùng trọn quy trình.
- [ ] Dữ liệu (DB + file) bền sau `docker compose restart`.
- [ ] Migrate chạy 1 lần (không race); `/health` xanh; app chờ db healthy.
- [ ] Admin xem được chi phí token/người (LOG). Backup chạy + phục hồi thử được.

## Risk Assessment
- **DNS chưa trỏ / port 80 đóng** → Caddy không xin được cert. Mitigation: DNS-first + mở firewall, ghi rõ deploy.md.
- **Redirect URI lệch** → login fail; test kỹ.
- **Mất dữ liệu file khi rebuild** → BẮT BUỘC volume `projects/` + pgdata; kiểm trước go-live.
- **Chỉ 1 admin** → dùng `ADMIN_EMAILS` list ≥2 người.
