# E&C — Agent báo giá fit-out nội thất từ bản vẽ PDF

Agent chạy trong **Claude Code**, tự động lập **báo giá thi công hoàn thiện nội thất**
(FF&E + đồ gỗ + trang trí + phụ kiện) từ **bản vẽ PDF nội thất**. Theo mô hình **2 giai
đoạn** thực tế: bóc khối lượng → file mời thầu (trống giá) → nhà thầu phụ chào giá →
cộng profit → báo giá nội bộ.

> ⚠️ KHÔNG dùng định mức nhà nước. Giá = **đơn giá cung cấp+lắp của NCC × (1+profit%)**.
> Agent không tự bịa giá; bắt buộc người duyệt khối lượng.

## Cài đặt (đã xong)
Python 3.12 + venv `.venv` + thư viện trong `requirements.txt`. Python: `.venv\Scripts\python.exe`.

## Cách dùng A — Web app (giao diện, gửi nội bộ)
```powershell
.venv\Scripts\python.exe webapp\app.py     # mở http://127.0.0.1:5000
```
Wizard 4 bước: upload PDF → **AI bóc khối lượng** (Claude API, cần API key) → file mời
thầu → áp giá NCC + profit → báo giá nội bộ. Chi tiết: [webapp/README.md](webapp/README.md).

## Cách dùng B — Skill trong Claude Code
- `/bao-gia <ten-du-an>` — chạy trọn quy trình 2 giai đoạn.
- `/boc-tach <ten-du-an>` — GĐ1: PDF → `02-boq/*.csv` + `03-baogia/moi-thau.xlsx` (gửi NCC).
- `/ap-gia <ten-du-an>` — GĐ2: CSV (đã điền giá NCC) + profit → `03-baogia/bao-gia-noi-bo.xlsx`.
- `/chen-anh <ten-du-an> [MaPhong]` — quét ảnh sản phẩm trong spec/PDF → chèn vào cột
  MINH HỌA (crop vừa đủ, fit ô, không vỡ bố cục). Agent nhìn ảnh để gán đúng hạng mục.

## Ảnh minh họa cột MINH HỌA
```powershell
.venv\Scripts\python.exe scripts\spec_images.py "<pdf|thư mục ảnh ...>" -o projects\<ten>
.venv\Scripts\python.exe scripts\match_images.py projects\<ten> <MaPhong>   # ghép sơ bộ → <MaPhong>.anh.csv
```
Sửa/điền `img_path` trong `02-boq/<MaPhong>.anh.csv` (agent nhìn `01-extract/spec-img/*.png`
để gán), rồi build lại — ảnh tự chèn cột D. Ảnh đặt sẵn: bỏ file tên theo mã (vd `LA-06.png`)
vào 1 thư mục và trỏ `spec_images.py` vào đó.

## Một dự án (`projects/<ten>/`)
```
input/         PDF bản vẽ
01-extract/    text + ảnh trang (PNG)
02-boq/<Ma>.csv  bóc khối lượng từng loại phòng (người duyệt; đơn giá NCC điền ở GĐ2)
cau-hinh.json  danh sách phòng+số lượng, profit, vat, preliminaries, scope
03-baogia/     moi-thau.xlsx (GĐ1) · bao-gia-noi-bo.xlsx (GĐ2)
notes.md       giả định & cảnh báo
```
Tạo dự án mới: tạo thư mục trên, copy `templates/cau-hinh.mau.json` → `cau-hinh.json` và chỉnh.

## Chạy thủ công
```powershell
.venv\Scripts\python.exe scripts\pdf_extract.py projects\<ten>\input -o projects\<ten>\01-extract
.venv\Scripts\python.exe scripts\build_boq_xlsx.py projects\<ten>       # GĐ1 mời thầu
.venv\Scripts\python.exe scripts\build_baogia_xlsx.py projects\<ten>    # GĐ2 nội bộ
```

## Định dạng BOQ (`02-boq/<Ma>.csv`)
`nhom_ma, nhom_ten, hang_muc, quy_cach, don_vi, kl_1phong, don_gia_ncc, do_tin_cay, ghi_chu`
- Nhóm: I.1 Đồ rời · I.2 Hoàn thiện tường & đồ liền tường · I.3 Cửa, vách kính ·
  I.4 Nội thất trang trí · I.5 Phụ kiện (+ I.6/I.7/I.8 nếu scope mở rộng).
- `don_gia_ncc` trống ở GĐ1, NCC điền ở GĐ2. Thêm cột `profit_override` để ghi đè profit từng dòng.

## Đã kiểm chứng
Engine được calibrate round-trip bằng số liệu thật phòng King1 (dự án `68-Tho-Nhuom`):
tái lập đúng tổng mời thầu **1.302.963.612,5 VND** (lệch 0). File mời thầu để trống đơn giá.

## Cấu trúc
```
CLAUDE.md            luật nghiệp vụ + luật bóc tách (2 giai đoạn)
.claude/skills/      /bao-gia, /boc-tach, /ap-gia
.claude/agents/      takeoff (bóc 1 loại phòng)
data/                danh-muc-noi-that.csv + file BOQ/báo giá tham chiếu (Handwritten, 68 Thợ Nhuộm)
scripts/             pdf_extract, build_boq_xlsx, build_baogia_xlsx, lib_boq
templates/           cau-hinh.mau.json
projects/            mỗi dự án 1 thư mục
```
