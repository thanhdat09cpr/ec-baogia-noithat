# E&C — Agent báo giá fit-out nội thất từ bản vẽ PDF

Agent (chạy trong Claude Code) tự động lập **báo giá thi công hoàn thiện nội thất**
(fit-out) từ **bản vẽ PDF vector xuất từ CAD** — điển hình: hồ sơ thiết kế nội thất
khách sạn/căn hộ (FF&E + đồ gỗ + trang trí + phụ kiện).

> ⚠️ ĐÂY KHÔNG dùng định mức/đơn giá nhà nước. Giá là **đơn giá cung cấp + lắp đặt
> theo spec**, lấy từ **nhà thầu phụ (NCC) chào giá**, rồi cộng **% profit**.
> Agent KHÔNG tự bịa đơn giá. Bóc khối lượng bằng AI luôn có sai số → bắt buộc
> **người duyệt khối lượng**.

## Mô hình 2 giai đoạn

**GĐ1 — Bóc khối lượng → BOQ "trống giá" (file mời thầu):**
PDF → đếm số lượng (cái/bộ) + đo m²/md theo nhóm → xuất `moi-thau.xlsx` (hạng mục,
quy cách, ĐVT, khối lượng; **đơn giá để trống** cho NCC điền). Không lộ profit.

**GĐ2 — Nhận giá NCC + cộng profit → báo giá nội bộ:**
NCC điền đơn giá → nhập vào cột `don_gia_ncc` → áp **% profit** → tính thành tiền →
cộng **Preliminaries (nhập tay trọn gói)** + **VAT 8%** → `bao-gia-noi-bo.xlsx`
(đủ I/J + sheet TH). Công thức: `đơn_giá = don_gia_ncc × (1 + profit%)`.

## Cấu trúc 1 dự án (projects/<ten>/)
- `input/` — PDF bản vẽ
- `01-extract/` — dữ liệu trích xuất + ảnh trang (PNG)
- `02-boq/<MaPhong>.csv` — bóc khối lượng từng loại phòng (người duyệt ở đây)
- `cau-hinh.json` — cấu hình dự án (danh sách phòng+số lượng, profit, vat, preliminaries, scope)
- `03-baogia/` — `moi-thau.xlsx` (GĐ1), `bao-gia-noi-bo.xlsx` (GĐ2)
- `notes.md` — giả định, tỉ lệ, mục tin cậy thấp

Python dự án: `.venv\Scripts\python.exe`. Skills: `/boc-tach` (GĐ1), `/ap-gia` (GĐ2),
`/bao-gia` (điều phối), `/chen-anh` (quét ảnh spec → cột MINH HỌA). Bóc nhiều loại
phòng → mỗi loại 1 subagent `takeoff`.

## Ảnh minh họa (cột D — MINH HỌA)
`scripts/spec_images.py` trích ảnh sản phẩm từ spec/PDF (auto-crop, phân loại
product/render/swatch, lấy mã lân cận) → `01-extract/spec-img/` + `index.csv`.
`scripts/match_images.py` ghép sơ bộ → `02-boq/<MaPhong>.anh.csv` (cột `img_path`
sửa được). Mã sản phẩm thường nằm TRONG ảnh raster → agent NHÌN ảnh (Read PNG) để
gán đúng, KHÔNG bịa. Build tự crop + fit (cao ≤112px) + nới cột D nên bố cục không vỡ.

## Định dạng BOQ (02-boq/<MaPhong>.csv, UTF-8)
Cột: `nhom_ma, nhom_ten, hang_muc, quy_cach, don_vi, kl_1phong, don_gia_ncc, do_tin_cay, ghi_chu`
- `nhom_ma`: I.1 … I.5 (+ I.6… nếu mở rộng). `kl_1phong` = khối lượng cho 1 phòng (F).
- `don_gia_ncc`: TRỐNG ở GĐ1; điền sau khi NCC chào ở GĐ2. KHÔNG tự bịa.
- `do_tin_cay`: cao / trung_binh / thap. Mục `thap` ghi vào notes.md.
- ĐVT chuẩn: `cai`, `bo`, `m2`, `md`, `goi`.

## Nhóm hạng mục (theo form chuẩn fit-out nội thất phòng)
- **I.1 Đồ rời** (cai/bo): giường, tủ đầu giường, minibar, bàn trà, ghế đôn, armchair,
  vanity (chưa gồm TBVS), gương, đèn rời. Đếm từ legend LF + mặt bằng bố trí.
- **I.2 Hoàn thiện tường & đồ liền tường** (m²/md/cai): vách tivi, vách đầu giường (m²),
  nẹp, len chân tường (md), tủ quần áo, hộc (cai). Đo từ mặt đứng + chi tiết đồ gỗ.
- **I.3 Cửa, vách kính** (cai): cửa WC, vách kính WC, khuôn. Đếm + kích thước từ door details.
- **I.4 Nội thất trang trí** (m²/md/cai): thảm, rèm (sheer/che/kéo), giấy dán tường,
  vải bọc đầu giường, gương toàn thân, thanh inox + dây da. Đo từ mặt bằng sàn/tường + mặt đứng.
- **I.5 Phụ kiện** (cai/bo/md): bản lề, ray trượt, tay nắm, khóa, LED + máng nhôm, nguồn, cảm biến.
  Suy theo số cánh tủ/cửa + chi tiết.
- **(Mở rộng tuỳ scope)** I.6 Hoàn thiện thô (lát sàn/sơn/trần thạch cao – m²),
  I.7 Thiết bị vệ sinh (bộ/cái), I.8 Đèn & MEP điện (cái/m). Chỉ bật khi `cau-hinh.json`
  khai báo scope mở rộng.

## Quy ước đọc bản vẽ nội thất
- **Ưu tiên SỐ GHI kích thước** trên bản vẽ (dim text) hơn đo pixel. Lưu ý ghi chú
  "không theo tỉ lệ bản vẽ, chỉ dùng kích thước ghi" rất phổ biến trong hồ sơ nội thất.
- Danh mục bản vẽ (drawing list) cho biết sheet nào là: mặt bằng kích thước, hoàn thiện
  sàn/tường/trần, bố trí vật dụng, mặt đứng, chi tiết đồ gỗ (4xxx/7xxx), cửa (5xxx).
- **Bảng legend (FF/LF/PF/SA/finishes)** là nguồn đếm số lượng & mã vật liệu đáng tin nhất.
- Diện tích vách (tivi, đầu giường): lấy từ **mặt đứng** + chi tiết, KL = rộng × cao − khoét.
- md len chân/nẹp: chu vi phòng − cửa, từ mặt bằng len chân.

## Nguyên tắc bất biến
- KHÔNG bịa đơn giá NCC. Dòng chưa có giá để trống + "tạm tính / báo sau".
- Mọi giả định (kích thước suy ra, hệ số rèm, hàm lượng) ghi `notes.md`.
- Thành tiền trong Excel là CÔNG THỨC để sửa khối lượng/đơn giá là tổng tự cập nhật.
- File mời thầu KHÔNG chứa profit/giá nội bộ.
