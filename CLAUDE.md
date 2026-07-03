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
quy cách, ĐVT, khối lượng; **đơn giá để trống** cho NCC điền — tách 2 cột
**ĐG VẬT LIỆU + ĐG NHÂN CÔNG**, cột ĐƠN GIÁ = VL+NC là công thức, để so sánh thầu
và đàm phán theo thành phần). Không lộ profit.

**GĐ2 — Nhận giá NCC + cộng profit → báo giá nội bộ:**
NCC điền đơn giá → nhập cột `don_gia_vl` + `don_gia_nc` (chào tách) hoặc `don_gia_ncc`
(trọn gói) → áp **% profit** → tính thành tiền → cộng **Preliminaries (nhập tay trọn
gói)** + **VAT 8%** → `bao-gia-noi-bo.xlsx` (sheet TH). Công thức:
`đơn_giá = giá_NCC × (1 + profit%)`, với `giá_NCC = don_gia_ncc` nếu có, ngược lại
`= don_gia_vl + don_gia_nc`.

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

## Ảnh minh họa (cột E — MINH HỌA)
`scripts/spec_images.py` trích ảnh sản phẩm từ spec/PDF (auto-crop, phân loại
product/render/swatch, lấy mã lân cận) → `01-extract/spec-img/` + `index.csv`.
`scripts/match_images.py` ghép sơ bộ → `02-boq/<MaPhong>.anh.csv` (cột `img_path`
sửa được). Mã sản phẩm thường nằm TRONG ảnh raster → agent NHÌN ảnh (Read PNG) để
gán đúng, KHÔNG bịa. Build tự crop + fit (cao ≤112px) + nới cột E nên bố cục không vỡ.

## Định dạng BOQ (02-boq/<MaPhong>.csv, UTF-8)
Cột: `nhom_ma, nhom_ten, ky_hieu, hang_muc, quy_cach, don_vi, dien_giai, kl_1phong,
don_gia_vl, don_gia_nc, don_gia_ncc, do_tin_cay, ghi_chu`
- `nhom_ma`: I.1 … I.5 (+ I.6… nếu mở rộng). `kl_1phong` = khối lượng cho 1 phòng.
- `ky_hieu`: mã ký hiệu bản vẽ/spec KHỚP legend (LF-07, CA-2.01, D03…); không có → trống.
- `dien_giai` (bảng phân tích tính toán QĐ 451): **bắt buộc với dòng m²/md/m³** —
  `số bộ phận × dài × rộng × cao − khoét` + nguồn (vd `2×(3.2×2.6) − 1.7 cửa (MĐ 4102)`),
  kết quả phải khớp `kl_1phong` để người duyệt kiểm chứng được phép tính.
- Giá NCC: TRỐNG ở GĐ1, điền sau khi NCC chào ở GĐ2. KHÔNG tự bịa. NCC chào **tách
  vật liệu/nhân công** → điền `don_gia_vl` + `don_gia_nc`; chào **trọn gói** → điền
  `don_gia_ncc`. Có `don_gia_ncc` thì dùng nó; không thì giá NCC = VL + NC.
- `do_tin_cay`: cao / trung_binh / thap. Mục `thap` ghi vào notes.md.
- ĐVT chuẩn: `cai`, `bo`, `m2`, `md`, `goi`, `node`, `tủ`, `cây`. Cửa/vách kính tính
  cái/bộ **bắt buộc ghi kích thước R×C trong `quy_cach`**.

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
- **(Mở rộng tuỳ scope — theo form dự toán nội thất thực tế, vd mẫu DTC):**
  - **I.0 Tháo dỡ hiện trạng** (m²/cái/gói): dự án CẢI TẠO luôn mở đầu bằng tháo dỡ
    (nền, tường, trần, cửa cũ) + vận chuyển xà bần. Khai I.0 đầu `scope`.
  - **I.6 Hoàn thiện thô** (m²): lát sàn, ốp tường, sơn, trần thạch cao, chống thấm
    + xây tường, tô/trát, cán nền/xử lý sàn, sơn epoxy (cải tạo).
  - **I.7 Thiết bị vệ sinh** (bộ/cái).
  - **I.8 Điện nước** (cái/md/node/tủ/gói): đèn, ổ cắm/công tắc, tủ điện, cáp nguồn,
    **node đèn / node ổ cắm** (đi dây + đấu nối trọn điểm), trunking, ống cấp thoát.
  - **I.9 Logo – tranh vẽ – chữ trang trí** (bộ/m²). **I.10 Cây cảnh** (cây/cái/md/m² —
    ghi rõ cây thật/giả trong quy_cach). **I.11 Mặt tiền – bảng hiệu** (m²/bộ/gói,
    gồm giấy phép bảng hiệu).
  - Mỗi nhóm mở rộng nên có dòng **"Vật tư phụ & phụ kiện (gói)"**; dự án nhiều gói
    tách thêm "đóng gói & vận chuyển (gói)" theo từng gói thay vì dồn Preliminaries.
  Chỉ bật khi `cau-hinh.json` khai báo trong `scope`.

## Quy ước đọc bản vẽ nội thất
- **Ưu tiên SỐ GHI kích thước** trên bản vẽ (dim text) hơn đo pixel. Lưu ý ghi chú
  "không theo tỉ lệ bản vẽ, chỉ dùng kích thước ghi" rất phổ biến trong hồ sơ nội thất.
- Danh mục bản vẽ (drawing list) cho biết sheet nào là: mặt bằng kích thước, hoàn thiện
  sàn/tường/trần, bố trí vật dụng, mặt đứng, chi tiết đồ gỗ (4xxx/7xxx), cửa (5xxx).
- **Bảng legend (FF/LF/PF/SA/finishes)** là nguồn đếm số lượng & mã vật liệu đáng tin nhất.
- Diện tích vách (tivi, đầu giường): lấy từ **mặt đứng** + chi tiết, KL = rộng × cao − khoét.
- md len chân/nẹp: chu vi phòng − cửa, từ mặt bằng len chân.

## Quy tắc ĐO BÓC CHUẨN (bắt buộc — chống 6 nhóm lỗi thường gặp)
Rút ra từ review QS thực tế. Vi phạm các mục này = BOQ không đủ cơ sở mời thầu.

**A. Phương pháp đo (đơn vị & cách đo):**
- **Mọi dòng đo (m²/md/m³) phải có `dien_giai`** theo bảng phân tích tính toán QĐ 451:
  `số bộ phận × dài × rộng × cao − khoét` + nguồn kích thước — người duyệt kiểm chứng
  được phép tính, không chấp nhận con số trơ.
- **Cửa/vách kính** tính cái/bộ (trọn gói khuôn+cánh+phụ kiện theo thông lệ fit-out)
  nhưng **bắt buộc ghi kích thước R×C trong quy_cach** (chuẩn QS gốc đo m² — đã chọn
  phương án cái/bộ + kích thước).
- **Ốp lát khu ướt (WC, bếp, sân phơi): TÁCH RIÊNG lát sàn và ốp tường.** Ốp tường =
  chu vi ốp × chiều cao ốp − cửa/hốc (đo từ mặt đứng WC), KHÔNG lấy bằng diện tích sàn.
  Một dòng "ốp/lát gạch WC = diện tích sàn" là SAI.
- **Đồ gỗ may đo (tủ bếp, tủ quần áo, tủ lavabo, vách gỗ): đo md hoặc m²**, không để
  "bộ/cái × 1". Tủ bếp: md theo tuyến (trên+dưới tách). Tủ áo/vách: m² mặt. Chỉ cho "bộ trọn gói"
  khi có spec chi tiết kèm kích thước.
- **Rèm: đo m² (rộng × cao) hoặc md thanh ray**, không tính "bộ". Rèm vải nhân hệ số xếp ly ghi notes.
- Vách trang trí (đá/gỗ/kính/kim loại/giấy/mosaic): m² từ mặt đứng, KL = rộng × cao − khoét.

**B. Đối chiếu Specification (bắt buộc, không chỉ mặt bằng):**
- Gán ĐÚNG MÃ vật tư từ Spec (vd bồn cầu `BH-01 NOKEN Smart Toilet`, đèn `LA-1.08`, đá `XTONE`).
  Thiếu file spec → ghi `do_tin_cay=thap` + ghi_chu "CHỜ SPEC", KHÔNG bịa mã, KHÔNG bỏ trống lặng lẽ.
- Phân loại **đồ rời vs đồ liền tường theo danh sách Loose Furniture của Spec**, không suy đoán.
  (vd CA-x.xx tủ đầu giường thường là Loose Furniture → I.1, không mặc định I.2.)
- Kiểm mã: không trùng mã cho 2 hạng mục; đúng tiền tố (WC-02 giấy dán, không phải UC-02).

**C. Chống bỏ sót (nhóm ảnh hưởng tiền lớn nhất):**
- **Mọi không gian trên mặt bằng phải có trong `cau-hinh.json`** — kể cả Outdoor/tum, Gara,
  sân phơi, hành lang. Thiết bị đặc biệt trên layout (vd Car Turntable) phải thành 1 dòng.
- **Bắt buộc đọc MẶT ĐỨNG từng phòng** → bóc vách trang trí; phòng chỉ có "sàn + trần" là THIẾU.
- Đèn/đồ trang trí: đối chiếu Spec số cụm/chủng loại (2 cụm LA-1.08 ≠ 1 đèn).
- **Chống thấm**: WC (đáy + chân tường), sân phơi, ban công — luôn có dòng riêng (m²).
- Ranh giới **MEP**: BOQ nội thất gồm đèn + ổ cắm; HVAC/VRV/ống gió/cấp thoát nước/tủ điện là
  **gói M&E riêng** — nếu ngoài scope phải GHI RÕ "do gói M&E khác", không im lặng bỏ.

**D. Đối chiếu Layout (logic KL):**
- Đúng phòng: thiết bị/đồ đặt sát ranh giới (ghế trang điểm, bồn tắm) phải gán đúng không gian
  theo layout, không theo vị trí ký hiệu.
- Không tính đúp / không thừa: đối chiếu legend + layout (2 mã riêng = 2 vật; 1 mã đặt 2 chỗ ≠ 2 vật).

**E. Chi phí cấu thành tổng mức (Preliminaries — khai trong config, không bỏ):**
- Logistics (vận chuyển, cẩu lắp, đưa vật tư lên cao), quản lý/giám sát, dự phòng, **hao hụt vật liệu %**
  (đá/gỗ/kính). Ghi trong `preliminaries_items` hoặc `preliminaries_lumpsum` + `wastage_percent`.

> Chạy `scripts/check_boq.py <project>` để tự soát 6 nhóm lỗi trên trước khi build.

## Nguyên tắc bất biến
- KHÔNG bịa đơn giá NCC. Dòng chưa có giá để trống + "tạm tính / báo sau".
- Mọi giả định (kích thước suy ra, hệ số rèm, hàm lượng) ghi `notes.md`.
- Thành tiền trong Excel là CÔNG THỨC để sửa khối lượng/đơn giá là tổng tự cập nhật.
- File mời thầu KHÔNG chứa profit/giá nội bộ.
