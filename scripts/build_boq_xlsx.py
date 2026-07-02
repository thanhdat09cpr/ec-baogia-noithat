"""
build_boq_xlsx.py - GIAI ĐOẠN 1: xuất file MỜI THẦU (BOQ trống giá).

Từ cau-hinh.json + 02-boq/<phong>.csv -> 03-baogia/moi-thau.xlsx:
  - Mỗi tầng 1 sheet, các phòng cùng tầng nằm liên tiếp trong sheet đó.
  - Cột đơn giá để trống cho nhà thầu phụ điền.
  - Thành tiền là công thức (=KL*đơn giá).

Dùng:  python scripts/build_boq_xlsx.py <project_dir>
"""
import os
import sys

from openpyxl import Workbook

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_boq import (  # noqa: E402
    load_config, load_room_rows, group_rows, style_header_row,
    set_widths, roman, safe_save, place_image, load_image_map, minhhoa_col_width,
    MONEY, QTY, BOLD, GRP_FILL, TOTAL_FILL, BORDER,
)
from openpyxl.utils import get_column_letter  # noqa: E402

HEADERS = [
    "STT", "HẠNG MỤC / MÔ TẢ CÔNG VIỆC", "QUY CÁCH / THÔNG SỐ KỸ THUẬT",
    "MINH HỌA", "ĐVT", "KHỐI LƯỢNG", "TỔNG KHỐI LƯỢNG", "ĐƠN GIÁ (VND)",
    "THÀNH TIỀN 1 PHÒNG", "THÀNH TIỀN ĐỦ PHÒNG", "GHI CHÚ / NGUỒN GỐC",
]
WIDTHS = [6, 34, 34, 10, 8, 11, 13, 15, 16, 17, 26]

FLOOR_BY_ROOM = {
    "GT": "T.HẦM", "GARA": "T.HẦM", "WC0": "T.HẦM", "KHO-KT": "T.HẦM",
    "BEP": "T1", "LIVING": "T1", "POWDER": "T1",
    "PN1": "T2", "WC1": "T2", "THUVIEN": "T2",
    "PN2": "T3", "WC3": "T3", "MASTER": "T3", "WC4": "T3",
    "WORKSHOP": "TUM", "SANPHOI": "TUM",
}


def create_floor_sheet(wb, cfg, floor):
    ws = wb.create_sheet(floor[:31])
    ws["A1"] = f"DỰ ÁN: {cfg['du_an']}"
    ws["A2"] = f"HẠNG MỤC: {cfg.get('hang_muc', '')}"
    ws["A3"] = f"TẦNG: {floor}"
    ws["A1"].font = ws["A2"].font = ws["A3"].font = BOLD
    header_row = 4
    for j, h in enumerate(HEADERS, 1):
        ws.cell(header_row, j, h)
    style_header_row(ws, header_row, len(HEADERS))
    set_widths(ws, WIDTHS)
    ws.freeze_panes = "A5"
    return ws, header_row + 1


def append_room(ws, cfg, phong, rows, row, images=None):
    images = images or {}
    sl = phong["so_luong"]
    ws.cell(row, 1, "A")
    ws.cell(row, 2, f"Phòng {phong['ma']} ({phong['ten']})")
    ws.cell(row, 3, f"{sl} phòng")
    ws.cell(row, 7, sl)
    for c in range(1, len(HEADERS) + 1):
        ws.cell(row, c).font = BOLD
        ws.cell(row, c).fill = TOTAL_FILL
    row += 1

    stt = 0
    first_item = row
    last_item = row
    for gi, (_nm, group) in enumerate(group_rows(rows, cfg["scope"]), 1):
        ws.cell(row, 1, roman(gi))
        ws.cell(row, 2, group["ten"]).font = BOLD
        for c in range(1, len(HEADERS) + 1):
            ws.cell(row, c).fill = GRP_FILL
        row += 1

        for it in group["items"]:
            stt += 1
            kl = it["_kl"]
            ws.cell(row, 1, stt)
            ws.cell(row, 2, it.get("hang_muc"))
            ws.cell(row, 3, it.get("quy_cach"))
            ws.cell(row, 5, it.get("don_vi"))
            if kl is not None:
                ws.cell(row, 6, kl).number_format = QTY
                ws.cell(row, 7, f"=F{row}*{sl}").number_format = QTY
            ws.cell(row, 8).number_format = MONEY
            ws.cell(row, 9, f"=F{row}*H{row}").number_format = MONEY
            ws.cell(row, 10, f"=G{row}*H{row}").number_format = MONEY
            ws.cell(row, 11, it.get("ghi_chu"))
            for c in range(1, len(HEADERS) + 1):
                ws.cell(row, c).border = BORDER
            img = images.get((it.get("hang_muc") or "").strip())
            if img:
                place_image(ws, row, img, col_idx=4)
            last_item = row
            row += 1

    ws.cell(row, 2, "TỔNG PHÒNG TRƯỚC VAT").font = BOLD
    ws.cell(row, 9, f"=SUM(I{first_item}:I{last_item})").number_format = MONEY
    ws.cell(row, 10, f"=SUM(J{first_item}:J{last_item})").number_format = MONEY
    ws.cell(row, 9).font = ws.cell(row, 10).font = BOLD
    total_row = row
    return row + 2, total_row, stt


def build(project_dir):
    project_dir = str(project_dir).rstrip("\\/")
    cfg = load_config(project_dir)
    wb = Workbook()
    wb.remove(wb.active)
    out_dir = os.path.join(project_dir, "03-baogia")
    os.makedirs(out_dir, exist_ok=True)

    floors = []
    floor_rooms = {}
    for phong in cfg["phong"]:
        floor = FLOOR_BY_ROOM.get(phong["ma"], "KHÁC")
        if floor not in floor_rooms:
            floors.append(floor)
            floor_rooms[floor] = []
        floor_rooms[floor].append(phong)

    missing = []
    total_no_price = 0
    n_img = 0
    for floor in floors:
        ws, row = create_floor_sheet(wb, cfg, floor)
        total_rows = []
        has_data = False
        floor_has_img = False
        for phong in floor_rooms[floor]:
            rows = load_room_rows(project_dir, phong["ma"])
            if rows is None:
                missing.append(phong["ma"])
                continue
            total_no_price += sum(1 for r in rows if r.get("_gia_ncc") is None)
            images = load_image_map(project_dir, phong["ma"])
            row, total_row, count = append_room(ws, cfg, phong, rows, row, images)
            total_rows.append(total_row)
            has_data = True
            if images:
                floor_has_img = True
                n_img += sum(1 for v in images.values() if v)
            print(f"  {floor}/{phong['ma']}: {count} hạng mục"
                  + (f" (+{len(images)} ảnh)" if images else ""))
        if floor_has_img:
            ws.column_dimensions[get_column_letter(4)].width = minhhoa_col_width()

        if has_data and total_rows:
            ws.cell(row, 2, f"TỔNG CỘNG {floor} TRƯỚC VAT").font = BOLD
            ws.cell(row, 9, "=" + "+".join(f"I{x}" for x in total_rows)).number_format = MONEY
            ws.cell(row, 10, "=" + "+".join(f"J{x}" for x in total_rows)).number_format = MONEY
            ws.cell(row, 9).font = ws.cell(row, 10).font = BOLD
            for c in range(1, len(HEADERS) + 1):
                ws.cell(row, c).fill = TOTAL_FILL
        else:
            del wb[ws.title]

    if not wb.sheetnames:
        raise ValueError(f"Không có file 02-boq/*.csv. Thiếu: {missing}")
    out = safe_save(wb, os.path.join(out_dir, "moi-thau.xlsx"))
    print(f"\n[GĐ1] File mời thầu (trống giá) -> {out}")
    if n_img:
        print(f"  Đã chèn {n_img} ảnh minh họa vào cột MINH HỌA.")
    if missing:
        print(f"  (Chưa có BOQ cho phòng: {missing})")
    print("  Gửi file này cho nhà thầu phụ điền cột ĐƠN GIÁ. KHÔNG chứa profit.")
    return out, {"n_no_price": total_no_price, "n_img": n_img}


def main():
    if len(sys.argv) < 2:
        sys.exit("Dùng: python scripts/build_boq_xlsx.py <project_dir>")
    try:
        build(sys.argv[1])
    except Exception as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
