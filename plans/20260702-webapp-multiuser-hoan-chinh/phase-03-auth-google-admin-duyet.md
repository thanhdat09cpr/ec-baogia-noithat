---
phase: 3
title: "Đăng nhập Google OAuth + admin duyệt"
status: pending
priority: P1
effort: "1.5d"
dependencies: [2]
---

# Phase 3: Đăng nhập Google OAuth + admin duyệt

## Overview
Đăng nhập bằng Google (chỉ email @eurostyle.com.vn). User mới = trạng thái *chờ duyệt*, không
dùng được cho tới khi admin duyệt. Admin: `hoang.dang@eurostyle.com.vn` (auto admin + approved).

## Requirements
- Functional: login Google; user lạ thấy màn "chờ duyệt"; admin duyệt → user vào được, chỉ thấy dự án của mình; admin thấy tất + duyệt/khóa user.
- Non-functional: session an toàn (cookie secure khi HTTPS), chống CSRF/open-redirect ở callback; chặn email ngoài domain.

## Architecture
- **Authlib** (`authlib.integrations.flask_client`) đăng ký Google OIDC. Cần `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET` (env), redirect `https://<domain>/auth/callback`.
- **Flask-Login** giữ session; `SECRET_KEY` từ env.
- Luồng callback: lấy `email`, `hd`/`email_verified`, `sub`, `name`. Chặn nếu domain ≠ `eurostyle.com.vn`.
  Tìm/tạo `User`. Nếu email == admin → `role=admin, status=approved`. Ngược lại user mới → `status=pending`.
- **Gate:** decorator `@approved_required` bọc TẤT CẢ route nghiệp vụ + `/api/*` (trừ auth + pending).
  `pending` → redirect màn `pending.html`. `@admin_required` cho route admin.
- **Owner scoping:** `/api/project` gán `owner_id=current_user.id`; `/api/projects` lọc theo owner
  (admin: thấy tất). Mọi thao tác trên project kiểm quyền sở hữu (403 nếu không phải owner/admin).

## Related Code Files
- Create: `webapp/auth.py` (blueprint: `/auth/login`, `/auth/callback`, `/logout`), `webapp/templates/pending.html`, `webapp/templates/admin_users.html`
- Modify: `webapp/app.py` (init login_manager, đăng ký blueprint, thêm `@approved_required`/`@admin_required` lên route), `webapp/models.py` (User đã có role/status ở pha 2)
- Create: route `/admin/users` (GET list), `/admin/users/<id>/approve|reject|lock` (POST)

## Implementation Steps
1. Cài authlib + flask-login; cấu hình OAuth Google + `SECRET_KEY`.
2. `auth.py`: login redirect Google; callback verify domain + email_verified, upsert User, set role/status, login_user.
3. `@approved_required` + `@admin_required`; áp lên toàn bộ route nghiệp vụ + API.
4. `pending.html` (màn chờ duyệt) + `/logout`.
5. `admin_users.html` + route list/approve/reject/lock; nút hiện số user pending.
6. Nối `current_user` vào `/api/project` (owner) + lọc `/api/projects`; kiểm quyền mọi route theo project.
7. Test: user lạ domain khác → chặn; user domain hợp lệ → pending; admin duyệt → vào được, chỉ thấy dự án mình.

## Success Criteria
- [ ] Email ngoài @eurostyle.com.vn → không đăng nhập được.
- [ ] User mới → màn "chờ duyệt", mọi /api trả 403/redirect.
- [ ] Admin duyệt → user dùng được, chỉ thấy dự án của mình.
- [ ] Admin thấy toàn bộ dự án + duyệt/khóa được user.

## Hardening (red-team — bắt buộc)
- **N2 — default-deny:** `@app.before_request` chặn MỌI request trừ allowlist tường minh
  (`/auth/*`, `/health`, `/static`, `/pending`). Đọc `status` TƯƠI từ DB mỗi request (khóa user có hiệu lực ngay). Không dựa gắn decorator từng route.
- **N3 — bỏ `api_key`/`model` khỏi client** (nối pha 4); key chỉ server-side; model allowlist.
- **C2 — `ProxyFix(x_proto,x_host)`** + `SESSION_COOKIE_SECURE/HTTPONLY`, `SAMESITE=Lax`, `PREFERRED_URL_SCHEME=https` (chạy sau Caddy).
- **C3 — CSRF (Flask-WTF)** cho mọi POST mutation (admin approve/reject/lock, tạo dự án, cài đặt).
- **C5 — OAuth an toàn:** Authlib `authorize_redirect` (state+nonce id_token); whitelist `next` chỉ path nội bộ; `SECRET_KEY` ≥32B cố định trong `.env`.
- **T1 — chuẩn hóa email:** `email.strip().lower().split("@")[-1]=="eurostyle.com.vn"` + BẮT BUỘC `email_verified`. Admin qua `ADMIN_EMAILS` (list ≥2 người) thay vì 1 email hardcode.
- **O3 — tạo route `/health`** (được allowlist tham chiếu). **T2** không trả stack/stdout ra client. **T4** rate-limit `/auth/login` + `/api/takeoff` (Flask-Limiter).

## Risk Assessment
- **Redirect URI lệch domain** → callback fail. Mitigation: cấu hình env theo domain thật, test kỹ ở pha 6.
- **`hd` claim không đáng tin cho Gmail thường** → verify cả `email` endswith `@eurostyle.com.vn` + `email_verified`.
- **Bỏ sót gate 1 route → rò dữ liệu** → checklist: mọi route trừ auth/pending/health phải có `@approved_required`; test bằng user pending.
- **Session cookie không secure trên HTTP dev** → cấu hình theo môi trường (secure khi HTTPS).
