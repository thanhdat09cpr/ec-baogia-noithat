---
name: boc-tach
description: GĐ1 — Bóc khối lượng nội thất từ bản vẽ PDF và xuất file mời thầu (BOQ trống giá) để gửi nhà thầu phụ. Dùng khi user nói "bóc khối lượng", "lập BOQ", "làm file mời thầu".
---

# /boc-tach — Bóc khối lượng → file mời thầu (trống giá)

Tham số `$ARGUMENTS` = tên dự án trong `projects/`. Python: `.venv\Scripts\python.exe`.
Tham chiếu danh mục chuẩn: `data/danh-muc-noi-that.csv`. Luật: `CLAUDE.md`.

## Các bước
1. Kiểm tra `projects/<ten>/cau-hinh.json` (danh sách phòng + số lượng + scope) và PDF
   trong `input/`. Thiếu config → copy `templates/cau-hinh.mau.json` và hỏi user.

2. **Trích xuất**:
   ```
   .venv\Scripts\python.exe scripts/pdf_extract.py projects/<ten>/input -o projects/<ten>/01-extract
   ```
   Đọc `_summary.json` để lập danh mục sheet (mặt bằng bố trí, mặt đứng, chi tiết đồ gỗ,
   cửa, hoàn thiện tường/sàn/trần).

3. **Bóc khối lượng** mỗi loại phòng (chạy song song subagent `takeoff`):
   - Đọc ảnh trang `01-extract/pages/*.png` (vision) + kích thước trong `*.json`.
   - Theo nhóm I.1–I.5 (và I.0 tháo dỡ, I.6–I.11 nếu scope mở rộng — xem CLAUDE.md),
     đối chiếu `data/danh-muc-noi-that.csv`: đếm SL (cai/bo) từ legend + mặt bằng bố trí;
     đo m²/md từ mặt đứng + chi tiết. Dự án CẢI TẠO: bóc I.0 tháo dỡ trước.
   - Ghi `02-boq/<MaPhong>.csv` đúng cột: `nhom_ma,nhom_ten,ky_hieu,hang_muc,quy_cach,
     don_vi,dien_giai,kl_1phong,don_gia_vl,don_gia_nc,don_gia_ncc,do_tin_cay,ghi_chu`.
     **3 cột giá để TRỐNG.**
   - `ky_hieu` = mã bản vẽ/spec khớp legend (LF-07, D03…). `dien_giai` **bắt buộc với dòng
     m²/md/m³**: `số bộ phận × dài × rộng × cao − khoét` (bảng phân tích QĐ 451) khớp
     `kl_1phong`. Cửa/vách kính tính cái/bộ phải ghi kích thước R×C trong `quy_cach`.

4. **notes.md**: tỉ lệ, giả định (hệ số rèm, kích thước suy ra), dòng `do_tin_cay=thap`.
   Ghi rõ ranh giới scope (vd "HVAC/cấp thoát nước do gói M&E riêng").

4b. **SOÁT LỖI bắt buộc** (theo CLAUDE.md "Quy tắc ĐO BÓC CHUẨN"):
   ```
   .venv\Scripts\python.exe scripts/check_boq.py projects/<ten>
   ```
   Sửa các cảnh báo (ốp tường WC gộp với sàn, rèm/đồ gỗ tính "bộ", thiếu chống thấm,
   thiếu mặt đứng/vách trang trí, phòng trong config chưa bóc…) rồi chạy lại tới khi sạch.

5. **Xuất file mời thầu**:
   ```
   .venv\Scripts\python.exe scripts/build_boq_xlsx.py projects/<ten>
   ```
   → `03-baogia/moi-thau.xlsx`: NCC điền 2 cột **ĐG VẬT LIỆU + ĐG NHÂN CÔNG** (tách
   thành phần để so sánh thầu), cột ĐƠN GIÁ = VL+NC và thành tiền là công thức sẵn.
   KHÔNG profit.

6. Báo cáo: số hạng mục mỗi phòng, nhắc người duyệt `02-boq/` rồi gửi `moi-thau.xlsx`
   cho nhà thầu phụ. Áp giá bằng `/ap-gia` sau khi NCC chào.
