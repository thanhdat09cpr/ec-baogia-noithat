---
name: bao-gia
description: Điều phối trọn quy trình báo giá fit-out nội thất từ bản vẽ PDF — bóc khối lượng → file mời thầu → (NCC chào giá) → áp profit → báo giá nội bộ. Dùng khi user nói "báo giá nội thất", "làm báo giá từ bản vẽ", đưa thư mục dự án có PDF.
---

# /bao-gia — Quy trình báo giá fit-out nội thất (2 giai đoạn)

Tham số `$ARGUMENTS` = tên dự án trong `projects/`. Python: `.venv\Scripts\python.exe`.
Đọc `CLAUDE.md` để nắm mô hình & luật bóc tách.

## Giai đoạn 1 — Bóc khối lượng → file mời thầu (gọi `/boc-tach`)
1. Đảm bảo `projects/<ten>/cau-hinh.json` (copy từ `templates/cau-hinh.mau.json`, khai
   danh sách phòng + số lượng + scope + profit + preliminaries) và PDF trong `input/`.
2. Trích xuất + bóc khối lượng từng loại phòng (subagent `takeoff`) → `02-boq/<MaPhong>.csv`
   (đơn giá để TRỐNG).
3. Xuất `python scripts/build_boq_xlsx.py projects/<ten>` → `03-baogia/moi-thau.xlsx`.
4. **DỪNG**: người duyệt khối lượng (`02-boq/`), rồi gửi `moi-thau.xlsx` cho nhà thầu phụ.

## Giai đoạn 2 — Nhận giá NCC + profit → báo giá nội bộ (gọi `/ap-gia`)
5. NCC chào giá → điền vào cột `don_gia_ncc` trong `02-boq/<MaPhong>.csv`.
6. Chỉnh `profit_percent` / `preliminaries_lumpsum` trong `cau-hinh.json` (mặc định 10% / 0).
7. Xuất `python scripts/build_baogia_xlsx.py projects/<ten>` → `03-baogia/bao-gia-noi-bo.xlsx`
   (đủ I/J + sheet TH + VAT). Báo cáo tổng từng phòng, tổng dự án, dòng chưa có giá.

## Nguyên tắc
- Không bịa đơn giá NCC. File mời thầu KHÔNG chứa profit (tách 2 file).
- Markup không đều: chỉnh `profit_percent` chung, hoặc thêm cột `profit_override` từng
  dòng trong CSV để ghi đè.
