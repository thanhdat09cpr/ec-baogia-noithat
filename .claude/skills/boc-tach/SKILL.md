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
   - Theo nhóm I.1–I.5 (và I.6–I.8 nếu scope mở rộng), đối chiếu `data/danh-muc-noi-that.csv`:
     đếm SL (cai/bo) từ legend + mặt bằng bố trí; đo m²/md từ mặt đứng + chi tiết.
   - Ghi `02-boq/<MaPhong>.csv` đúng cột: `nhom_ma,nhom_ten,hang_muc,quy_cach,don_vi,
     kl_1phong,don_gia_ncc,do_tin_cay,ghi_chu`. **don_gia_ncc để TRỐNG.**

4. **notes.md**: tỉ lệ, giả định (hệ số rèm, kích thước suy ra), dòng `do_tin_cay=thap`.

5. **Xuất file mời thầu**:
   ```
   .venv\Scripts\python.exe scripts/build_boq_xlsx.py projects/<ten>
   ```
   → `03-baogia/moi-thau.xlsx` (đơn giá trống, công thức thành tiền sẵn). KHÔNG profit.

6. Báo cáo: số hạng mục mỗi phòng, nhắc người duyệt `02-boq/` rồi gửi `moi-thau.xlsx`
   cho nhà thầu phụ. Áp giá bằng `/ap-gia` sau khi NCC chào.
