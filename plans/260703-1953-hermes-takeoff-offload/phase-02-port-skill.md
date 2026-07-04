---
phase: 2
title: "Orchestrator 2-stage trên Hermes (lọc text → vision từng trang)"
status: pending
priority: P1
effort: "1d"
dependencies: [1]
---

# Phase 2: Orchestrator 2-stage trên Hermes

## Overview
1 script python trong container Hermes: nhận request → Stage 1 lọc trang bằng text (1 call
Hermes) → Stage 2 vision từng trang đã lọc (`hermes chat --image`) → merge → ghi CSV 13 cột.
Watcher (cron/loop) kích hoạt khi có `_takeoff/<room>.request.json`.

## Bài học phải tuân (từ test 2026-07-03)
- Stage 2 **đính `--image` từng trang** (vision native). KHÔNG để agent tự `read` PNG (→ OCR sai).
- Mọi call `hermes chat`: `--max-turns` thấp (S1 ~4, S2 ~6), **cấm delegate/subagent** trong prompt.
- Model `anthropic/claude-opus-4.6` (cred funded #2).

## Related Code Files
- Create (VPS, /opt/data hoặc mount): `takeoff_orchestrator.py`, `takeoff_watcher` (cron/loop)
- Giữ bản gốc trong repo để version: `deploy/hermes/takeoff_orchestrator.py` (copy tham chiếu)
- Đọc: `/opt/projects/<id>/01-extract/*.json` (text), `pages/*.png`; danh-muc-noi-that.csv

## Implementation Steps
1. **Catalog builder (python, free):** từ `01-extract/*.json` gom mỗi trang: tag, loai, bo_mon,
   tiêu đề khung tên, danh sách mã (LF/PF/SA/DE...), so_dong_text. → JSON gọn cho Stage 1.
2. **Stage 1 — lọc (1 call text):** `hermes chat -q "<catalog + scope + phòng> → JSON {pages:[{tag,loai_dung}]}"`
   `--max-turns 4`, không ảnh. Parse ra danh sách trang liên quan (sửa được lỗi regex).
3. **Stage 2 — vision/trang:** mỗi trang đã lọc:
   `hermes chat --image pages/<tag>.png -q "<bóc rows JSON cho nhóm I.x trên trang này>" --max-turns 6`.
   Thu JSON rows từng trang.
4. **Merge (python):** gộp rows các trang, dedup theo (nhom_ma,hang_muc,ky_hieu), chuẩn hoá 13 cột
   (3 cột giá trống) → ghi atomic `02-boq/<room>.csv` (UTF-8).
5. **Status:** ghi `_takeoff/<room>.status.json` {status, rows, input_tokens?, output_tokens?, error}.
6. **Watcher:** vòng lặp/cron quét `_takeoff/*.request.json` chưa có status → chạy orchestrator →
   ghi status. Cân nhắc `hermes cron` vs script `nohup` (bền qua recreate → verify).

## Success Criteria
- [ ] Stage 1 chọn đúng bộ trang GR1 (gồm p12 layout dù regex gắn sai) — RẺ (~$0.02), verify trước.
- [ ] Stage 2 mỗi trang trả rows JSON hợp lệ (vision native, không OCR).
- [ ] Merge ra `02-boq/GR1.csv` 13 cột đúng header.
- [ ] check_boq (chạy ở webapp) không lỗi cấu trúc.

## Risk Assessment
- Chi phí Stage 2 (~15 trang Opus) — đo + đặt trần; nếu đắt: chỉ vision trang đếm/đo, trang legend đọc text.
- Parse JSON từ `hermes chat` stdout (có thể lẫn log) → cần bóc JSON chắc tay (regex/markers).
- Watcher bền: nếu `hermes cron` không sống → script nền + restart.
- Rollback: xoá watcher + orchestrator; `TAKEOFF_ENGINE=openrouter` ở webapp.
