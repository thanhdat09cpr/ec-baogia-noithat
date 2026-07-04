# Phase 4 — E2E test + rollout

## Yêu cầu
Chứng minh luồng web→Hermes→web đạt chất lượng ≥ luồng 1-shot cũ, đo chi phí, rollout an toàn.

## Việc làm
1. **E2E 68-Tho-Nhuom** (có ground truth `02-boq/GR1.csv`):
   - Upload `king1.pdf` → chọn phòng GR1, scope I.1–I.5 → chạy engine=hermes.
   - So kết quả vs ground truth: đếm I.1 (giường/tủ đầu giường ×2/minibar/armchair/đôn/bàn trà),
     m²/md I.2 có `dien_giai`. Chấm: đúng SL, không sót nhóm, không bịa.
2. **So sánh 3 luồng** trên cùng phòng (bảng): (a) 1-shot Opus 4.8 cũ, (b) Hermes per-page,
   ghi: độ chính xác đếm, số dòng, thời gian, token/chi phí ước tính.
3. **Model production = `anthropic/claude-opus-4.6`** (đã chốt). Phase này chỉ ĐO chi phí/thời gian
   thực tế/phòng để user biết; hạ model chỉ khi user yêu cầu.
4. **Rollout**: bật `TAKEOFF_ENGINE=hermes` mặc định; giữ fallback 1 thời gian; theo dõi job lỗi.
5. **Docs**: cập nhật `webapp/README.md` + `docs/system-architecture.md` (nếu có) mô tả luồng mới.

## Acceptance (khớp plan.md)
- BOQ 13 cột sinh qua Hermes, check_boq sạch, build xlsx OK.
- GR1 đếm I.1 đúng ground truth.
- Webapp không gọi OpenRouter khi flag=hermes.
- Có đường rollback (flag).

## Rủi ro
- Chi phí per-page cao hơn 1-shot (nhiều call) → nếu vượt ngân sách, cân nhắc: chỉ per-page
  các trang then chốt (legend + layout + mặt đứng), trang khác gộp.
- Thời gian/phòng lâu (POC Opus 71s/trang × N trang) → cân nhắc model nhanh + xử song song.
