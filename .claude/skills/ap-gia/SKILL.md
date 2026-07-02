---
name: ap-gia
description: GĐ2 — Áp đơn giá nhà thầu phụ + cộng profit lên BOQ đã bóc, xuất báo giá nội bộ (có TH + VAT). Dùng khi đã nhận giá NCC, hoặc user nói "áp giá", "ra báo giá nội bộ", "cộng profit".
---

# /ap-gia — Áp giá NCC + profit → báo giá nội bộ

Tham số `$ARGUMENTS` = tên dự án trong `projects/`. Python: `.venv\Scripts\python.exe`.

## Điều kiện
- Có `02-boq/<MaPhong>.csv` đã bóc (GĐ1) và đã **điền cột `don_gia_ncc`** (giá NCC chào).
  Nếu NCC trả về file Excel, giúp user chép đơn giá vào cột `don_gia_ncc` của CSV.

## Các bước
1. Kiểm `cau-hinh.json`: `profit_percent` (mặc định 10), `preliminaries_lumpsum`
   (nhập tay trọn gói), `vat_percent` (8). Markup không đều → có thể thêm cột
   `profit_override` trong CSV để ghi đè từng dòng.

2. Xuất báo giá nội bộ:
   ```
   .venv\Scripts\python.exe scripts/build_baogia_xlsx.py projects/<ten> [--profit 10]
   ```
   → `03-baogia/bao-gia-noi-bo.xlsx`:
   - Mỗi phòng 1 sheet, `đơn giá = don_gia_ncc × (1 + profit%)`, thành tiền là công thức.
   - Sheet **TH**: cộng các phòng + Preliminaries (trọn gói) + VAT.

3. Báo cáo: tổng từng loại phòng, tổng dự án trước/sau VAT, suất/phòng, và **danh sách
   dòng CHƯA có giá NCC** (để "báo sau" — tuyệt đối không tự bịa giá).

## Lưu ý
- File này LÀ file nội bộ (có profit) — KHÔNG gửi cho NCC. File gửi NCC là `moi-thau.xlsx`.
- Sửa khối lượng/đơn giá trong CSV rồi chạy lại; file Excel cũ sẽ bị ghi đè.
