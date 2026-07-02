---
phase: 5
title: "Frontend redesign + dashboard + nhập giá NCC (v1)"
status: done
priority: P2
effort: "2d"
dependencies: [3]
---

# Phase 5: Frontend redesign + dashboard + nhập giá NCC (v1)

## Overview
Dựng lại giao diện theo mockup đã duyệt (app-shell + dashboard + wizard 5 bước) và bổ sung
**nhập giá NCC per-dòng** (lõi GĐ2). Song song pha 4 (sau pha 3).
**HOÃN sang v2 (red-team YAGNI):** preliminaries chi tiết + hao hụt %, ảnh minh họa cột MINH HỌA.
→ v1 giữ Preliminaries **trọn gói** như code hiện tại (build_th KHÔNG đổi → round-trip bất biến).

## Requirements
- Functional: dashboard danh sách dự án (mở lại được, không mất khi refresh); wizard 5 bước;
  bước 4 nhập `don_gia_ncc` + `profit_override` per-dòng; bước 5 báo giá (profit/vat + prelim trọn gói).
- Non-functional: trạng thái persist server-side (DB/file); giao diện theo mockup, gọn.

## Architecture
- App-shell (sidebar + topbar, role-aware) thay layout 1 trang; dashboard đọc `/api/projects`.
- Mở dự án → nạp lại config + BOQ từ server (không mất khi refresh).
- **Nhập giá NCC (bước 4):** bảng sửa `don_gia_ncc` + `profit_override` từng dòng → `/api/boq`.
  **F3:** `app.py CSV_COLS` PHẢI thêm `profit_override` (hiện 9 cột cứng làm mất cột này); reader
  `lib_boq.load_room_rows` đã đọc `_profit_override` → sẵn sàng nửa dưới.
  **F1:** giá NCC dán từ Excel VN qua `to_number` đã sửa (không sai ×1000). Highlight dòng trống giá.
- Preliminaries (v1): giữ trọn gói (`preliminaries_lumpsum`), form 1 ô như hiện tại.
- **KHÔNG đụng calc từng dòng (F/G/H/I/J) và build_th** ở v1 → round-trip 68-Tho-Nhuom vẫn lệch 0.

## Related Code Files
- Modify: `webapp/templates/index.html` → `dashboard.html` + app-shell base; `static/style.css`, `app.js`
- Modify: `webapp/app.py` (`CSV_COLS` + `profit_override`; `/api/boq` giữ cột này; `/api/projects` list theo owner)
- (v2, không làm bây giờ) `build_baogia_xlsx.build_th`, `spec_images.py`/`match_images.py`, config schema

## Implementation Steps
1. Base app-shell + sidebar/topbar role-aware; dashboard `/api/projects` + mở dự án.
2. Wizard 5 bước theo mockup; giữ trạng thái qua DB/file.
3. **F3:** thêm `profit_override` vào `app.py CSV_COLS`; `write_boq` giữ cột (union cột đầu vào).
4. Bước 4: bảng nhập `don_gia_ncc`/`profit_override` per-dòng → `/api/boq`; highlight dòng trống.
5. Bước 5: form profit/vat + preliminaries trọn gói; gọi `build()` báo giá (pha 1).
6. Chạy lại round-trip 68-Tho-Nhuom → phải vẫn lệch 0; thêm fixture có giá NCC (F1) → verify GĐ2.

## Success Criteria
- [ ] Refresh không mất việc; mở lại dự án cũ đúng trạng thái.
- [ ] Nhập giá NCC + profit_override per-dòng → LƯU không mất → báo giá đúng công thức.
- [ ] Giá dán kiểu VN (2.500.000) tính đúng, không sai ×1000.
- [ ] Round-trip 68-Tho-Nhuom vẫn lệch 0 (build_th không đổi ở v1).

## Risk Assessment
- **Quên sửa `app.py CSV_COLS`** → mất profit_override. Bắt buộc test lưu-đọc lại.
- **Phạm vi FE phình** → bám mockup, không sa đà thẩm mỹ.
- **v2 sau này đụng build_th** → khi làm phải test cả nhánh lumpsum (bất biến) + items (F4: before_vat SUM động).
