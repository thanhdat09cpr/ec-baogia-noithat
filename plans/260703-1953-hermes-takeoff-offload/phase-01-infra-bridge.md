---
phase: 1
title: "Infra bridge — volume chung + quyền + cron watcher"
status: pending
priority: P1
effort: "0.5d"
dependencies: []
---

# Phase 1: Infra bridge (file-drop)

## Overview
Cho Hermes đọc/ghi được thư mục dự án của webapp qua volume chung, xử quyền uid 10000,
và dựng `hermes cron` quét file yêu cầu. KHÔNG webhook, KHÔNG network mới, KHÔNG HMAC.

## Requirements
- Hermes container thấy `/opt/projects` = host `/opt/ec-baogia-noithat/projects`.
- Hermes (uid 10000) ghi được `02-boq/*.csv` + `_takeoff/*.status.json`.
- 1 lịch quét (`hermes cron`) chạy bền, phát hiện `*.request.json` mới.

## Architecture
- Backup compose Hermes (đã làm: `docker-compose.yml.bak-baogia-260703`).
- Mount thêm vào service `hermes-agent`: `- /opt/ec-baogia-noithat/projects:/opt/projects`.
- Recreate container (`docker compose up -d`) — gián đoạn ~vài giây, `restart: unless-stopped`.

## Related Code Files
- Modify (trên VPS, KHÔNG trong repo): `/docker/hermes-agent-hsju/docker-compose.yml`
- Create (trên VPS): script watcher `/opt/data/.hermes/takeoff-scan.sh` (hoặc job `hermes cron`)

## Implementation Steps
1. **Mount volume**: thêm dòng mount vào compose Hermes → `docker compose up -d`.
2. **Fix quyền**: `projects/` do root tạo. Chọn 1:
   - a) `chown -R 10000:10000 /opt/ec-baogia-noithat/projects` (root webapp vẫn ghi được vì bypass perm) — nhưng thư mục MỚI webapp tạo lại root → cần (b).
   - b) webapp tạo `_takeoff/` + `02-boq/` với `mode=0o777` (làm ở Phase 3); Phase 1 chmod thủ công dir test.
   - Chốt cách ở bước validate; ghi vào report.
3. **Watcher**: tạo `hermes cron` job chạy mỗi ~30s: quét `/opt/projects/*/_takeoff/*.request.json`
   chưa có `.status.json` → gọi skill boc-tach (Phase 2) cho từng request → ghi status.
   Nếu `hermes cron` không hợp → fallback 1 script `while+sleep` chạy nền trong container.
4. **Test 2 chiều** (dùng 68-Tho-Nhuom sẵn có).

## Success Criteria
- [ ] Trong Hermes: `ls /opt/projects/68-Tho-Nhuom/01-extract/pages/ | head` → thấy PNG.
- [ ] Trong Hermes (uid 10000): ghi `/opt/projects/68-Tho-Nhuom/_probe.txt` OK; webapp container đọc được → xoá.
- [ ] `hermes cron` (hoặc watcher) chạy, log phát hiện file test `*.request.json`.
- [ ] Container Hermes up lại khỏe (`hermes status` OK), dashboard/gateway không hỏng.

## Risk Assessment
- **Hostinger ghi đè compose**: nếu panel redeploy revert mount → tìm cách mount bền (khai qua panel) hoặc chấp nhận re-apply. Verify + ghi report.
- **Quyền**: uid 10000 vs root — nếu rối, tạm `chmod -R 777` dir test (VPS 1 tenant) rồi chuẩn hoá ở Phase 3.
- **cron bền**: nếu `hermes cron` không sống qua restart → dùng watcher script + `restart` policy.
- Rollback: khôi phục `docker-compose.yml.bak-baogia-260703`, gỡ cron, `docker compose up -d`.
