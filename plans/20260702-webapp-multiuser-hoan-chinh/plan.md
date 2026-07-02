# Kế hoạch: Đưa web app báo giá nội thất lên bản HOÀN CHỈNH đa người dùng

**Trạng thái tổng:** 🟡 Chưa bắt đầu
**Ngày tạo:** 2026-07-02
**Work context:** `E&C/`

## Mục tiêu
Nâng cấp web app Flask thử nghiệm (`webapp/`) thành **ứng dụng online hoàn chỉnh** cho nhân sự
công ty dùng: đăng nhập Google + admin duyệt, PostgreSQL, đa người dùng an toàn, deploy VPS
bằng Docker. **KHÔNG đụng chất lượng bóc AI** (giai đoạn sau).

## Quyết định đã chốt (không tự đảo)
- **Giữ Flask**, tái dùng lõi (gọi AI + xuất Excel). Không viết lại.
- **VPS:** đã có (Linux). Deploy bằng **Docker Compose**.
- **DB:** PostgreSQL (trong Docker).
- **Đăng nhập:** Google OAuth, giới hạn email công ty; user mới = trạng thái *chờ duyệt*;
  admin `hoang.dang@eurostyle.com.vn` duyệt mới dùng được. Admin auto-approved.
- **API key AI:** 1 key chung do admin nhập ở màn Cài đặt; giới hạn chi phí/người/tháng.
- **Preliminaries:** hỗ trợ CẢ trọn gói (như hiện tại) VÀ chi tiết (bật/tắt); nếu config có
  `preliminaries_items` → chi tiết, không có → trọn gói (2 dự án cũ chạy nguyên). **Hao hụt %
  = cách 1: % trên TỔNG THI CÔNG** (1 dòng = tổng_thi_công × wastage%), không tách vật liệu.
- **Theo dõi chi phí AI:** log token mỗi lần bóc vào DB → tính ước tính VND (token × giá model
  × tỷ giá cấu hình); enforce quota/người. Token chính xác, chi phí là ƯỚC TÍNH.
- **GÁC LẠI:** cải thiện độ chính xác bóc (đọc-theo-trang, soát-sót-món), soát 6 nhóm lỗi
  (check_boq — script chưa tồn tại), surface notes/độ tin — pha sau.
- **Logic tính tiền:** web GỌI LẠI `lib_boq.py`/`build_boq_xlsx.py`/`build_baogia_xlsx.py`,
  KHÔNG viết lại công thức. Đã verify: round-trip 68-Tho-Nhuom lệch 0 + đọc trực tiếp code.

## Nguyên tắc bất biến (giữ nguyên từ CLAUDE.md dự án)
- Người duyệt khối lượng trước khi xuất; đơn giá do NCC chào (AI không bịa giá).
- File mời thầu không lộ profit. Thành tiền Excel là công thức.

## Các giai đoạn
| # | Giai đoạn | File | Trạng thái |
|---|-----------|------|------------|
| 1 | Chuẩn hóa chạy Linux/Docker (bỏ path Windows hardcode) | [phase-01](phase-01-chuan-hoa-linux-docker.md) | ✅ (verified: test to_number + round-trip GĐ1/GĐ2 lệch 0) |
| 2 | PostgreSQL + mô hình dữ liệu + tách dự án theo người | [phase-02](phase-02-database-va-mo-hinh.md) | ⬜ |
| 3 | Đăng nhập Google OAuth + admin duyệt | [phase-03](phase-03-auth-google-admin-duyet.md) | ⬜ |
| 4 | Bóc khối lượng chạy nền (job + tiến trình) | [phase-04-boc-chay-nen.md](phase-04-boc-chay-nen.md) | ⬜ |
| 5 | Chỉnh frontend (dashboard + wizard gọn) | [phase-05-frontend.md](phase-05-frontend.md) | ⬜ |
| 6 | Deploy VPS (Docker Compose + HTTPS + quota) | [phase-06-deploy-vps.md](phase-06-deploy-vps.md) | ⬜ |

## Phụ thuộc bên ngoài (CẦN từ khách/bạn)
1. **Google OAuth credentials** — tạo OAuth 2.0 Client trên Google Cloud Console →
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` + redirect URI (`https://<domain>/auth/callback`).
2. **Thông tin VPS** — IP/SSH, tên miền (nếu có) để cấu hình HTTPS.
3. **ANTHROPIC_API_KEY** — key chung của công ty.
4. Xác nhận: có giới hạn email đăng nhập theo domain `@eurostyle.com.vn` không (đề xuất: CÓ).

## Phạm vi v1 (sau red-team — đã chốt) vs v2 (hoãn)
**v1 (làm ngay, ~8–9 ngày):** chuẩn hóa Linux/Docker · PostgreSQL + tách dự án theo owner ·
Google OAuth + admin duyệt · bóc chạy nền · dashboard + wizard + **nhập giá NCC per-dòng** · deploy VPS.
**v2 (hoãn sau go-live — red-team YAGNI):** preliminaries chi tiết + hao hụt % (giữ trọn gói ở v1) ·
ảnh minh họa cột MINH HỌA · **enforce** quota (v1 chỉ LOG token cho admin xem, chưa chặn).
> Hao hụt %: khi làm v2 dùng **cách 1** (% trên tổng đã cộng profit) — đã chốt.

## Hardening BẮT BUỘC (từ red-team — xem reports/redteam-report.md)
Không phải "checklist", là yêu cầu cứng, gắn vào phase tương ứng:
- **F1** `to_number` chuẩn hóa số VN (`12.500`→12500, không ×1/1000) + fixture round-trip CÓ giá NCC.
- **N1** helper `load_project_or_403` cho MỌI truy cập; `TakeoffJob.id`=uuid; status join theo user.
- **N2** gate **default-deny** `before_request` (allowlist `/auth,/health,/static,/pending`), đọc status tươi.
- **N3** BỎ `api_key`/`model` từ client; key chỉ server-side; model allowlist.
- **F3** thêm `profit_override` vào `app.py CSV_COLS` (không mất khi lưu).
- **C2** ProxyFix + cookie Secure/HttpOnly/SameSite + PREFERRED_URL_SCHEME=https (sau Caddy).
- **C3** CSRF (Flask-WTF) cho mọi POST mutation (admin approve/lock…).
- **C5** OAuth state+nonce, whitelist `next` nội bộ, SECRET_KEY ≥32B cố định env.
- **O1** reaper job `running` mồ côi (started_at + TTL) + lock tự nhả.
- **O2** Alembic migrate **one-shot** trong entrypoint TRƯỚC gunicorn.
- **O3** `/health` + compose healthcheck + `depends_on db healthy`.
- **T1** so email `.lower().split("@")[-1]` + bắt buộc `email_verified`; **ADMIN_EMAILS** (list ≥2).
- **T2** không trả stack/stdout ra client. **T4** rate-limit login+takeoff. **T5** giới hạn trang/dung lượng PDF.

## Kiến trúc job nền (đã chốt)
Đội <10 người → **1 gunicorn worker (gthread) + ThreadPoolExecutor** (executor lazy per-worker,
không `preload_app`). Bỏ bài toán polling chéo worker. Nâng RQ+Redis chỉ khi >10 đồng thời.

## Thứ tự thực thi
Tạo Google OAuth creds **TRƯỚC pha 3** (để nghiệm thu được, dùng redirect localhost cho dev).
Pha 1 → 2 → 3 tuần tự; pha 4, 5 song song sau pha 3; pha 6 cuối (cần VPS + creds + ANTHROPIC key).
Phần code (pha 1–5) làm ngay không cần VPS.
