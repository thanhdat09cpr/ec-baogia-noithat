# Plan: Bóc tách qua Hermes — pipeline 2-stage (lọc text → vision từng trang)

> ⛔ **SUPERSEDED (2026-07-04).** Bỏ hướng Hermes cho khâu takeoff. Lý do đã kiểm chứng:
> **Hermes CLI không nhận PDF cho model nhìn** (chỉ `--image` 1 ảnh/lần); các skill Hermes
> đọc-tài-liệu (pptx/pdf, SQLite FTS5) chỉ xử lý CHỮ, không "nhìn" bản vẽ để đếm/đo.
> → Khâu takeoff làm THẲNG trong webapp qua OpenRouter (Opus 4.8 nhìn cả PDF) + **mỏ neo
> legend text** trích tại chỗ (`scripts/legend_context.py`). E2E GR1 đạt: đếm đúng tủ đối
> xứng (LF-04=2), dien_giai chuẩn QS, check_boq 0 lỗi, ~$1/loại phòng. Giữ plan này chỉ để
> lưu bài học. Bài học Hermes vẫn dùng được SAU NÀY cho việc đọc SPEC text (FF&E).

**Ngày:** 2026-07-03 · **Trạng thái:** ⛔ SUPERSEDED (xem banner) · **Nhánh:** main

## Mục tiêu
Webapp bỏ gọi AI trực tiếp. Đẩy bóc tách qua **Hermes agent** (user chốt dùng Hermes) theo
pipeline **2-stage do 1 orchestrator điều khiển** — KHÔNG thả agent tự do:
- **Stage 1 (lọc, TEXT, rẻ):** dùng text `pdf_extract` trích sẵn → 1 call Hermes chọn trang liên quan.
- **Stage 2 (vision, từng trang đã lọc):** mỗi trang 1 call `hermes chat --image <png>` (vision native) → bóc rows.
- **Merge → 02-boq/<room>.csv (13 cột).** Webapp: `check_boq` + build Excel + UI duyệt.

## Bài học đã kiểm chứng (bắt buộc tuân theo)
1. **PHẢI đính ảnh `--image`** cho model (vision native). NẾU để agent tự `read` file `.png`
   → nó đi cài OCR (tesseract/easyocr), sai + tốn turns (test 12-turn hỏng vì thế).
2. **CẤM delegate/subagent + cap turns thấp.** Thả tự do → Opus đẻ subagent, mỗi con 50 vòng,
   đốt ~$8/phòng, không hội tụ (đã thấy).
3. **Vision đọc bản vẽ VN CHUẨN** (POC: đếm đúng 2 tủ đầu giường đối xứng, đọc legend đúng) —
   giữ lại kết luận này; chỉ cần gọi đúng cách + bounded.
4. `pdf_extract` trích **text nhúng thật** từ PDF vector → đủ để LỌC trang (Stage 1) không cần vision;
   vision chỉ cần cho ĐẾM/ĐO (Stage 2). Text còn vá được lỗi phân loại regex (vd p12 regex gắn
   `chi_tiet XD` nhưng text ghi rõ "FURNITURE LAYOUT PLAN").

## Kiến trúc (file-drop + orchestrator Hermes-side)
```
WEBAPP (không AI)                         HERMES (VPS) — orchestrator python
  upload PDF/phòng
  → pdf_extract → 01-extract/pages/*.png + *.json(text) vào /opt/projects (SHARED)
  → ghi _takeoff/<room>.request.json
                                          watcher phát hiện request → chạy orchestrator:
                                            S1: hermes chat -q "<catalog text các trang>"  → [trang chọn + loại]
                                            S2: mỗi trang: hermes chat --image pages/<tag>.png -q "<bóc rows JSON>"
                                            merge (python) → 02-boq/<room>.csv (13 cột)
                                          → ghi _takeoff/<room>.status.json {done, rows, tokens}
  poll status → done → check_boq + build moi-thau.xlsx → UI duyệt
```
- Orchestrator = python script trong container Hermes, `subprocess` gọi `hermes chat` (S1 text, S2 --image/trang).
- Model: `anthropic/claude-opus-4.6` (key funded #2). Mỗi call bounded (`--max-turns` thấp, cấm delegate).
- File chung: mount `/opt/ec-baogia-noithat/projects:/opt/projects` (Phase 1 DONE). Quyền: webapp tạo dir `0o777`.

## Phases
| # | Tên | Trạng thái |
|---|-----|-----------|
| 1 | [Infra bridge](phase-01-infra-bridge.md) — mount volume + quyền | ✅ DONE |
| 2 | [Orchestrator 2-stage trên Hermes](phase-02-port-skill.md) — watcher + S1 lọc text + S2 vision/trang + merge CSV + cron | ⏳ next |
| 3 | [Webapp tích hợp](phase-03-webapp-integrate.md) — pdf_extract trước; drop request + poll (`hermes_client.py` đã viết); bỏ do_takeoff; flag | pending |
| 4 | [E2E + rollout](phase-04-e2e-rollout.md) — GR1 vs ground truth; đo chi phí thật; rollback | pending |

## Acceptance
- Upload PDF → CSV 13 cột sinh qua Hermes 2-stage, check_boq sạch, build xlsx.
- Webapp không gọi OpenRouter khi `TAKEOFF_ENGINE=hermes`.
- GR1: đếm I.1 khớp ground truth `GR1.csv`.
- Chi phí/phòng đoán được (~$0.5–1.5), có trần; flag rollback `openrouter`.

## Câu hỏi mở
1. Merge rows: dùng python (dedup/group theo nhom_ma) hay 1 call synthesis Hermes text? → chọn python (rẻ, xác định) trước.
2. Watcher bền qua recreate container? `hermes cron` vs script nền — verify Phase 2.
3. Chi phí thật/phòng khi ~15 trang vision — đo Phase 4, đặt trần.
4. Key OpenRouter đã lộ trong chat → user thu hồi + thay sau khi xong.
