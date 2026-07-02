# Web app — Báo giá fit-out nội thất (gửi nội bộ)

Giao diện web (Flask) cho quy trình: **upload PDF bản vẽ → AI bóc khối lượng → file
mời thầu → áp giá NCC + profit → báo giá nội bộ**. Đầu vào là PDF, đầu ra là Excel theo
từng bước.

## Chạy
```powershell
# (đã cài flask + anthropic trong .venv)
.venv\Scripts\python.exe webapp\app.py
# Mở http://127.0.0.1:5000
```

## Cần Anthropic API key (cho bước bóc khối lượng AI)
AI đọc PDF bằng Claude (model mặc định **Opus 4.8**). Cung cấp key theo 1 trong 3 cách:
- Nhập trực tiếp ô **API key** ở bước 1 (chỉ dùng cho phiên, không lưu), hoặc
- Đặt biến môi trường `ANTHROPIC_API_KEY` trước khi chạy, hoặc
- `ant auth login` (SDK tự nhận profile).

Các bước **mời thầu** và **báo giá nội bộ** KHÔNG cần key (chạy bằng script Python local).

## 4 bước trên giao diện
1. **Dự án & bản vẽ** — tên dự án, phạm vi nhóm (I.1–I.8), thêm loại phòng + tải PDF mỗi loại, chọn model.
2. **Bóc khối lượng (AI)** — bấm "Bóc khối lượng bằng AI": Claude đọc PDF → bảng BOQ. Xem/sửa,
   điền **Đơn giá NCC** (sau khi nhà thầu phụ chào), bấm **Lưu**.
3. **File mời thầu** — xuất `moi-thau.xlsx` (đơn giá trống) gửi nhà thầu phụ.
4. **Báo giá nội bộ** — đặt profit/VAT/preliminaries → xuất `bao-gia-noi-bo.xlsx` (TH + VAT).

Dữ liệu mỗi dự án lưu trong `projects/<tên>/` (cùng cấu trúc với CLI). File Excel tải về
từ `projects/<tên>/03-baogia/`.

## Kiến trúc
- `app.py` — Flask: endpoints upload/takeoff/moi-thau/bao-gia/download; takeoff gọi
  Claude API (gửi PDF dạng document block + structured JSON output).
- `templates/index.html`, `static/style.css`, `static/app.js` — wizard 4 bước.
- Tái dùng `scripts/build_boq_xlsx.py` & `build_baogia_xlsx.py` (qua subprocess) và
  `data/danh-muc-noi-that.csv`.

## Lưu ý
- Chạy local (127.0.0.1) cho nội bộ. Nếu chia sẻ trong mạng LAN, bọc sau reverse proxy
  có xác thực — API key không nên truyền qua mạng không mã hoá.
- Chi phí token: 1 phòng ~ vài chục nghìn–trăm nghìn token đầu vào (PDF nhiều trang) →
  vài nghìn đồng/phòng tuỳ model. Sonnet 4.6 rẻ hơn Opus ~40%.
