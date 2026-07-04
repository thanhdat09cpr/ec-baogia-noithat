"""
legend_context.py — Trích LEGEND (mã→tên) và đếm mã đặt trên mặt bằng TỪ TEXT bản vẽ
PDF vector, để bơm làm "mỏ neo" cho bước bóc khối lượng (do_takeoff).

Vì sao: bản vẽ nội thất luôn có bảng legend (LF/PF/SA/DE/DP/CP → tên vật dụng) dưới
dạng TEXT nhúng — trích được chính xác 100%, gần như miễn phí. Bơm vào prompt giúp
model (1) dùng ĐÚNG mã ký hiệu (không bịa), (2) không bỏ sót loại vật dụng. Vẫn để
VISION lo phần ĐẾM số lượng thật (vẽ đối xứng hay thiếu nhãn) + ĐO m²/md.

Chỉ trích LEGEND (mã→tên): dòng là MÃ (vd "LF-04") có DÒNG MÔ TẢ NGAY bên phải cùng
hàng ngang (khoảng cách nhỏ) → 1 mục legend. KHÔNG đếm số nhãn đặt trên bản vẽ: đếm
bằng text không tin được (vẽ đối xứng chỉ ghi 1 nhãn) + lẫn nhiều finish/khung tên →
để VISION đếm số lượng.

Dùng như thư viện: build_legend_context(pdf_path, scope) -> str (rỗng nếu lỗi/không có).
"""
import os
import re

# Mã ký hiệu bản vẽ nội thất: 2-3 chữ HOA + '-' + số (LF-04, CA-2.01, LA-1.08, WC-02).
# Bắt buộc có dấu '-' để tránh nhận nhầm chữ/số linh tinh trên bản vẽ.
CODE_RE = re.compile(r"^[A-Z]{2,3}-\d{1,3}(?:\.\d{1,3})?$")
# Tiền tố mã → gợi ý nhóm (chỉ để chú thích cho model, KHÔNG ép ánh xạ cứng).
PREFIX_HINT = {
    "LF": "đồ rời", "CA": "đồ rời", "PF": "thiết bị vệ sinh", "SA": "phụ kiện vệ sinh",
    "DE": "đèn trang trí", "DP": "rèm", "CP": "thảm", "WC": "hoàn thiện tường",
}
_Y_TOL = 3.5   # dung sai lệch tâm dọc (pt) để coi 2 dòng "cùng hàng"
_MAX_DX = 60   # legend: mã→mô tả luôn SÁT nhau; > ngưỡng này là trùng hàng ngẫu nhiên
_MAX_CODES = 120
# Từ khoá KHUNG TÊN / GHI CHÚ (không phải tên vật dụng) → loại mô tả nhiễu.
_TITLEBLOCK_RE = re.compile(
    r"APPROVED|CONSULTANT|COMPANY|CLIENT|MANAGER|DIRECTOR|DRAWING|PROJECT|CHECK\b|"
    r"SCALE|REVISION|COMMENCING|PERSPECTIVE|HOTEL|INVESTOR|CERTIFIED|CONTRACTOR|"
    r"DESIGNED|DEVELOPMENT|CONSULTANT|SPECIFICATION|"
    r"CÔNG TY|CỔ PHẦN|TƯ VẤN|CHỦ ĐẦU TƯ|CHỦ NHIỆM|GIÁM ĐỐC|PHÊ DUYỆT", re.I)


def _center_y(bbox):
    return (bbox[1] + bbox[3]) / 2.0


def _is_desc(txt):
    """Dòng mô tả hợp lệ: tên vật dụng ngắn gọn — không phải mã/số trơ/khung tên/ghi chú."""
    if CODE_RE.match(txt):
        return False
    if not re.search(r"[A-Za-zÀ-ỹ]", txt):
        return False
    if not (1 < len(txt) <= 40):
        return False
    if txt[-1] in ".:/,":        # nhãn khung tên / câu ghi chú thường có dấu câu cuối
        return False
    if _TITLEBLOCK_RE.search(txt):
        return False
    # Loại mojibake (glyph symbol-font lỗi, vd "3+Ò1*.,1*"): quá ít ký tự chữ/khoảng trắng.
    letters = sum(c.isalpha() or c.isspace() for c in txt)
    if letters < 0.6 * len(txt):
        return False
    return True


def _page_lines(page):
    """[(text, bbox)] các dòng text 1 trang (bbox = [x0,y0,x1,y1])."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            txt = "".join(sp["text"] for sp in line["spans"]).strip()
            if txt:
                out.append((txt, [round(c, 1) for c in line["bbox"]]))
    return out


def _scan_page(lines, legend):
    """Cập nhật legend{code:desc} từ các dòng 1 trang: mã có mô tả SÁT bên phải cùng hàng."""
    for txt, bbox in lines:
        if txt in legend or not CODE_RE.match(txt):
            continue
        cy, x1 = _center_y(bbox), bbox[2]
        best, best_dx = None, _MAX_DX
        for t2, b2 in lines:
            if abs(_center_y(b2) - cy) <= _Y_TOL and b2[0] >= x1 - 1 and _is_desc(t2):
                dx = b2[0] - x1
                if 0 <= dx < best_dx:   # gần nhất VÀ trong ngưỡng _MAX_DX
                    best, best_dx = t2, dx
        if best is not None:
            legend[txt] = best


def build_legend_context(pdf_path, scope=None):
    """Trả text gọn (legend + số nhãn đặt) để nối vào prompt. Rỗng nếu không đọc được.

    scope hiện chỉ dùng để tham khảo; KHÔNG lọc mã theo nhóm (ánh xạ tiền tố→nhóm dễ sai,
    để model tự phân nhóm dựa danh mục + tên trong legend).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""
    if not os.path.exists(pdf_path):
        return ""
    legend = {}
    try:
        doc = fitz.open(pdf_path)
        try:
            for page in doc:
                _scan_page(_page_lines(page), legend)
        finally:
            doc.close()
    except Exception:  # noqa: BLE001 — hỏng đọc PDF thì bỏ mỏ neo, không chặn takeoff
        return ""
    if not legend:
        return ""

    rows = []
    for code in sorted(legend)[:_MAX_CODES]:
        hint = PREFIX_HINT.get(code.split("-")[0], "")
        hint_s = f"  [{hint}]" if hint else ""
        rows.append(f"- {code} = {legend[code]}{hint_s}")
    return ("LEGEND trích TỪ BẢN VẼ (mã → tên vật dụng/vật liệu). DÙNG ĐÚNG các mã này "
            "cho `ky_hieu`, KHÔNG bịa mã mới:\n" + "\n".join(rows))


if __name__ == "__main__":   # tiện test tay: python scripts/legend_context.py <pdf>
    import sys
    print(build_legend_context(sys.argv[1] if len(sys.argv) > 1 else ""))
