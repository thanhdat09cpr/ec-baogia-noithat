---
name: chen-anh
description: Tự quét spec/PDF tìm ảnh sản phẩm và chèn vào đúng ô MINH HỌA của báo giá (crop vừa đủ, không vỡ bố cục). Dùng khi user nói "chèn ảnh minh họa", "thêm hình sản phẩm", "quét ảnh trong spec".
---

# /chen-anh — Quét ảnh spec → chèn vào cột MINH HỌA

Tham số `$ARGUMENTS` = `<ten-du-an> [<MaPhong>]`. Python: `.venv\Scripts\python.exe`.
Ảnh nằm ở cột **E (MINH HỌA)**; mỗi hạng mục 1 ảnh, cùng dòng với hạng mục đó.

## Nguyên tắc
- **KHÔNG bịa ảnh.** Chỉ dùng ảnh trích từ spec/bản vẽ user cung cấp, hoặc ảnh user tự bỏ vào thư mục.
- Ảnh phải **crop vừa đủ** (cắt viền trắng) và **fit trong ô** (cao ≤ ~112px) để bố cục file không vỡ.
- Ghép ảnh ↔ hạng mục là bước **có người/agent duyệt** (mã sản phẩm thường nằm trong ảnh raster, không phải text) → agent NHÌN ảnh để gán.

## Các bước

1. **Trích ảnh** từ spec/PDF (bản vẽ chi tiết, spec NCC) hoặc thư mục ảnh đặt sẵn:
   ```
   .venv\Scripts\python.exe scripts/spec_images.py "<pdf hoặc thư mục ...>" -o projects/<ten>
   ```
   → `01-extract/spec-img/*.png` + `index.csv` (cột: id, page, **kind** [product/render/swatch],
   px_w, px_h, **codes** [mã tìm được], text, img_path). Auto-crop + chống trùng sẵn.
   Có thể truyền nhiều nguồn; thư mục chứa ảnh đặt tên theo mã (vd `LA-06.png`) sẽ nhận thẳng.

2. **Ghép sơ bộ** (khớp mã + fuzzy tên) tạo file duyệt:
   ```
   .venv\Scripts\python.exe scripts/match_images.py projects/<ten> <MaPhong>
   ```
   → `02-boq/<MaPhong>.anh.csv` (cột `img_path` SỬA ĐƯỢC + `ung_vien` liệt kê ảnh gợi ý).

3. **Agent duyệt bằng vision** (quan trọng — đây là bước "tìm đúng ảnh"):
   - Mở các ảnh `kind=product` trong `01-extract/spec-img/` (Read từng PNG).
   - Với mỗi hạng mục trong `02-boq/<MaPhong>.csv` còn trống `img_path`, nhìn ảnh đối chiếu
     tên/quy cách/mã (giường, tủ đầu giường, ghế, bàn trà…) rồi điền `img_path`
     (dán đường dẫn `spec-img/<file>.png`) vào `<MaPhong>.anh.csv`.
   - Ảnh `kind=render` (phối cảnh) chỉ dùng minh họa tổng thể, không gán cho 1 đồ rời.
   - Không chắc thì để trống + ghi vào notes để người duyệt.

4. **Build lại** (ảnh tự chèn vào cột MINH HỌA):
   ```
   .venv\Scripts\python.exe scripts/build_boq_xlsx.py projects/<ten>        # mời thầu
   .venv\Scripts\python.exe scripts/build_baogia_xlsx.py projects/<ten>     # nội bộ
   ```
   Build đọc `<MaPhong>.anh.csv`, tự crop + fit + nới cột E + set cao dòng. Báo "Đã chèn N ảnh".

5. Báo cáo: số ảnh đã gán / tổng hạng mục; liệt kê hạng mục chưa có ảnh để user bổ sung
   (bỏ ảnh vào 1 thư mục đặt tên theo mã rồi chạy lại bước 1 với thư mục đó).

## Ghi chú kỹ thuật
- Ảnh neo kiểu `oneCellAnchor` (di chuyển theo ô, cố định kích thước) → sửa dòng/cột không lệch ảnh.
- Kích thước ô ảnh & bề rộng cột E chỉnh trong `lib_boq.py` (`MINHHOA_BOX`, `MINHHOA_COL_CHARS`).
- Nguồn ảnh tin cậy nhất: sheet chi tiết đồ gỗ / legend trong bản vẽ (có render sản phẩm + mã).
