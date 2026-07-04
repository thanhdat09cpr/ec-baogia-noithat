# Phase 1 — Infra bridge: KẾT QUẢ

**Ngày:** 2026-07-03 21:40 · **Trạng thái:** DONE (phần volume+quyền); watcher dời sang Phase 2 (ghép với skill)

## Đã làm (trên VPS production, có backup)
- Thêm mount `/opt/ec-baogia-noithat/projects:/opt/projects` vào `/docker/hermes-agent-hsju/docker-compose.yml`.
- `docker compose up -d` → container **Recreated + Started** OK. Mount **bền qua recreate** (verified).
- Hermes container giờ **thấy** 4 project của webapp tại `/opt/projects/<uuid>`.

## Kiểm chứng quyền ghi
- Agent process chạy **uid 10000** (`hermes gateway run`); `docker exec` mặc định root.
- uid 10000 ghi vào dir `root:root 755` → **Permission denied**.
- Sau `chmod 777` dir → uid 10000 **ghi OK**.
- ⟹ Phase 3: webapp phải tạo `_takeoff/` + `02-boq/` mode **0o777** (hoặc chuẩn hoá group) để agent ghi được.

## ⚠️ Phát hiện làm lệch giả định (ảnh hưởng Phase 2–4)
1. **`68-Tho-Nhuom` (ground truth GR1.csv) KHÔNG có trên VPS** — chỉ ở máy local. VPS chỉ có 4 project UUID tạo qua web. → Phase 4 E2E cần **upload 68-Tho-Nhuom lên VPS** trước khi so ground truth.
2. **Webapp chạy trên VPS (container)** — code Phase 3 sửa ở local phải **deploy lên VPS** mới test được E2E. Cần 1 chu kỳ deploy vào production.
3. Container root (qua exec) vs agent uid 10000 — mọi file agent tạo là 10000; đã tính ở điểm quyền trên.

## Rủi ro còn treo
- Hostinger panel ghi đè compose Hermes? — CHƯA verify (chưa thấy redeploy tự động; theo dõi).
- `hermes cron` autonomous gọi skill non-interactive + parse CSV — CHƯA làm, là trọng tâm Phase 2 (cần thử nghiệm + tốn token Opus thật).

## Rollback
Khôi phục `docker-compose.yml.bak-baogia-260703` + `docker compose up -d`.
