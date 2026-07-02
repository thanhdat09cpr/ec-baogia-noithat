# Báo cáo Red-Team — Plan webapp báo giá đa người dùng

Ngày: 2026-07-02 · 3 reviewer đối kháng (bảo mật · dữ liệu/logic · ops/scope).
Trạng thái: đề xuất vá — một số cần user/khách quyết (đánh dấu ⏳).

## 🔴 NGHIÊM TRỌNG — phải vá trước khi code

| ID | Phát hiện | Vá | Phase | Trạng thái |
|----|-----------|-----|-------|-----------|
| F1 | `to_number` parse SAI số kiểu VN: `12.500`→12,5 (**sai ×1000 im lặng**), `2.500.000`→None (mất giá). Round-trip "lệch 0" CHƯA từng chạy path có giá NCC → an toàn giả. | Chuẩn hóa parser cho VN: chuỗi khớp `^\d{1,3}([.,]\d{3})+$` → bỏ hết dấu ngăn nghìn. Thêm fixture round-trip CÓ giá NCC + preliminaries thật. | 1,5 | ✅ vá |
| N1 | IDOR: `TakeoffJob.id` không uuid (đoán được); thiếu kiểm ownership tập trung; thư mục legacy tên đoán được. User A đọc BOQ/chi phí user B qua `/api/takeoff/status/2,3...`, tải file dự án khác. | Helper trung tâm `load_project_or_403`; `TakeoffJob.id`=uuid; status route join `user_id=current_user`. | 2,3,4 | ✅ vá |
| N2 | Gate = gắn `@approved_required` từng route → quên 1 route mới là rò (default-allow). | Đổi sang **default-deny**: `@app.before_request` chặn tất trừ allowlist (`/auth/*,/health,/static,/pending`); đọc `status` tươi từ DB mỗi request. | 3 | ✅ vá |
| N3 | Client tự truyền `api_key`+`model` (app.py:240-241) → chọn model đắt, bypass quota, lạm dụng key. | XÓA `api_key`/`model` khỏi payload client; key CHỈ server-side (DB/env); model allowlist server. GET Cài đặt KHÔNG trả key ra browser. | 4,6 | ✅ vá |
| F3 | `write_boq` (app.py:51-58) dùng 9 cột cứng → **mất `profit_override`** khi lưu (phase-05 sửa nhầm chỗ: lib_boq thay vì app.py). | Thêm `profit_override` vào `app.py CSV_COLS` + đồng bộ `lib_boq`; ghi động theo union cột. | 5 | ✅ vá |
| F4 | `build_th` before_vat = `E{thi_cong}+E{prelim}` (1 ô) — khi chèn nhiều dòng preliminaries chi tiết + hao hụt sẽ **BỎ SÓT** → báo giá thiếu tiền. Plan tự mâu thuẫn ("giữ nguyên công thức" vs "chèn nhiều dòng"). | before_vat = `thi_cong + SUM(prelim_block)`; tính chỉ số dòng ĐỘNG sau khi chèn. Test riêng nhánh items. | 5 | ⏳ tùy scope |
| F2 | Model `Project` không có cột đường dẫn; "path suy từ uuid" mâu thuẫn với "giữ tên thư mục legacy" → mở 68/ROX2 báo FileNotFound. | Thêm cột `dir_name` vào `Project`; `project_dir()` đọc cột (mới=uuid, legacy=tên cũ). | 2 | ✅ vá |

## 🟠 CAO

| ID | Phát hiện | Vá | Phase |
|----|-----------|-----|-------|
| C1 | Race quota: check-then-run + job song song → N job cùng qua "dưới ngưỡng" → vượt ngân sách. | Giới hạn job đang chạy/người (transaction row-lock); UNIQUE `(project_id,room_ma,status∈running/pending)`; vượt→429. |4,6|
| C2 | Sau Caddy, Flask thấy HTTP → cookie không Secure + redirect_uri sinh `http` → login fail/hạ cấp. | `ProxyFix(x_proto,x_host)`; ép `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE`, `PREFERRED_URL_SCHEME=https`. |3,6|
| C3 | Thiếu CSRF cho POST admin (`approve/lock`) + lưu key/quota → CSRF dụ admin. | Flask-WTF CSRF mọi POST mutation; SameSite=Lax/Strict. |3|
| C4 | Upload thiếu kiểm ownership + không validate PDF thật → đầu độc dữ liệu/DoS. | Kiểm owner; verify magic `%PDF`; giới hạn số trang/dung lượng. |3,5|
| C5 | OAuth state/nonce/open-redirect + SECRET_KEY mới nêu mục tiêu. | Authlib `authorize_redirect` (state+nonce); whitelist `next` path nội bộ; SECRET_KEY ≥32B cố định env. |3|
| O1 | Job `running` mồ côi khi worker recycle/deploy → spinner vĩnh viễn + khóa phòng vĩnh viễn. | Cột `started_at`/heartbeat + reaper đánh `error` job quá TTL lúc boot + định kỳ; lock tự nhả. |4|
| O2 | Alembic migrate trong app boot + nhiều worker → race double-apply/crash loop. | Migrate **one-shot** trong entrypoint TRƯỚC gunicorn (hoặc service `migrate` riêng). |6|
| O3 | Thiếu `/health` + compose healthcheck + `depends_on db healthy` → 502/crash loop khi khởi động. | Thêm `/health`; compose healthcheck app+db. |3,6|

## 🟡 TRUNG BÌNH (gộp, vá gọn)
- **O4 Kiến trúc job:** multi-worker + in-process executor = kém bền nhất + phức tạp nhất. → **1 worker gthread + ThreadPoolExecutor** (đủ cho đội nội bộ nhỏ, bỏ bài toán polling chéo worker). Executor tạo lazy per-worker (tránh `preload_app` fork hỏng).
- **O5 Caddy tiên quyết:** DNS A-record trỏ IP TRƯỚC + mở port 80&443 + email ACME. Redirect URI Google khớp EXACT.
- **O6 Legacy lên VPS:** volume `projects/` rỗng trên VPS mới → phải scp file 2 dự án cũ vào volume trước khi import; `projects/` trong `.dockerignore`.
- **T1** chuẩn hóa so email: `.lower().split("@")[-1]=="eurostyle.com.vn"` + bắt buộc `email_verified`.
- **T2** rò lỗi: đừng trả stack/stdout ra client; log server, trả thông báo chung.
- **T3/Admin recovery:** dùng `ADMIN_EMAILS` (list) qua env, tối thiểu 2 người — làm luôn, rẻ.
- **T4** rate limit login + takeoff (Flask-Limiter).
- **T5** DoS RAM: giới hạn số trang/dung lượng PDF thật; cap queue.
- **T7** backup chứa key/profit → mã hóa + hạn quyền; ưu tiên key ở env (không lưu DB).
- **F5** `load_config` thêm `setdefault("preliminaries_items",[])`, `setdefault("wastage_percent",0)`; nhánh chi tiết chỉ bật khi list≠rỗng (legacy bất biến).
- **F8** `build()` trả thêm dict thống kê (n_no_price, n_img) để không mất cảnh báo; thêm `scripts/__init__.py`.
- **F9** `FLOOR_BY_ROOM` hard-code → phòng lạ dồn sheet "KHÁC"; lấy `tang` từ config (hoãn được).

## ⏳ CẦN USER/KHÁCH QUYẾT (KHÔNG tự đảo quyết định đã chốt)
1. **Scope bản đầu:** red-team (YAGNI) đề xuất HOÃN 3 mục sang sau go-live để giảm rủi ro + effort: **preliminaries chi tiết+hao hụt, ảnh minh họa, enforce quota** (chỉ log token). NHƯNG user đã chốt "làm preliminaries chi tiết cách 1" + duyệt mockup có ảnh+quota → KHÔNG tự cắt, phải hỏi.
2. **F6 hao hụt %:** cách 1 áp trên tổng ĐÃ cộng profit (profit chồng hao hụt) — đúng ý không, hay tính trên giá NCC gốc?
3. **Effort:** giữ nguyên scope ~11–13 ngày thực tế; cắt 3 mục trên ~8–9 ngày.

## Đã sửa mâu thuẫn nội tại plan
- Job kém bền vs "bản hoàn chỉnh" → chọn 1-worker-gthread + reaper (O4).
- OAuth creds xếp blocker phase 6 nhưng phase 3 cần để nghiệm thu → **kéo tạo creds lên trước phase 3**.
- `/health` được viện dẫn ở gate phase 3 nhưng không phase nào tạo → thêm ở phase 3/6.
