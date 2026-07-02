"""
check_boq.py — Soát BOQ tự động BẰNG LUẬT (không dùng AI) trước khi build.

Soát 6 nhóm lỗi QS thường gặp (theo CLAUDE.md "Quy tắc ĐO BÓC CHUẨN"):
  A. Phương pháp đo   — thiếu diễn giải m²/md/m³; cửa/vách thiếu R×C; rèm/đồ gỗ tính "bộ".
  B. Đối chiếu spec   — trùng ký hiệu cho 2 hạng mục khác nhau.
  C. Chống bỏ sót     — phòng trong config chưa bóc; khu ướt có lát sàn mà thiếu ốp tường / chống thấm.
  (D/E là đối chiếu layout & chi phí gián tiếp — cần người duyệt, không tự soát được.)
  + Giá: don_gia_ncc và (VL+NC) đều điền mà lệch nhau.

Dùng:   python scripts/check_boq.py <project_dir>
Import: from check_boq import check;  findings, stats = check(project_dir)

Công cụ ADVISORY — luôn thoát mã 0; đọc cảnh báo và sửa CSV rồi chạy lại.
"""
import os
import re
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_boq import load_config, load_room_rows  # noqa: E402

# Đơn vị đo lường (bắt buộc có diễn giải phép tính)
DO_UNITS = {"m2", "md", "m3", "m²", "m³"}
# Đơn vị đếm (không hợp lệ cho rèm / đồ gỗ may đo)
COUNT_UNITS = {"cai", "bo", "cái", "bộ"}
# Mẫu kích thước R×C: "800x2200", "1.2 x 2,4", "800×2200"
DIM_RE = re.compile(r"\d+([.,]\d+)?\s*[x×*]\s*\d+([.,]\d+)?")

# Từ khóa nhận dạng (đã bỏ dấu, thường)
KW_CUA = ("cua", "vach kinh")
KW_REM = ("rem",)
KW_DOGO = ("tu bep", "tu quan ao", "tu ao", "tu lavabo", "tu do", "vach go", "tu ke")
KW_WET = ("wc", "toilet", "ve sinh", "bep", "san phoi", "ban cong", "tam")
KW_LAT = ("lat san", "lat gach", "lat nen", "sanh")
KW_OP = ("op tuong", "op gach", "op da")
KW_CHONGTHAM = ("chong tham",)


def _norm(s):
    """Bỏ dấu tiếng Việt + thường hóa (cho khớp từ khóa bền vững)."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower().strip()


def _unit(row):
    return _norm(row.get("don_vi")).replace(" ", "")


def _has_kw(text, kws):
    t = _norm(text)
    return any(k in t for k in kws)


def check(project_dir):
    """Trả (findings, stats). findings = list dict{level, room, code, msg}."""
    project_dir = str(project_dir).rstrip("\\/")
    cfg = load_config(project_dir)
    findings = []

    def add(level, room, code, msg):
        findings.append({"level": level, "room": room, "code": code, "msg": msg})

    seen_kyhieu = {}   # ky_hieu -> (room, hang_muc) để bắt trùng mã
    n_thap = 0

    for phong in cfg.get("phong", []):
        ma = phong["ma"]
        rows = load_room_rows(project_dir, ma)
        if rows is None:
            add("warn", ma, "C-missing", f"Phòng '{ma}' trong config nhưng CHƯA có 02-boq/{ma}.csv (bỏ sót?).")
            continue

        room_has_lat = any(_has_kw(r.get("hang_muc"), KW_LAT) for r in rows)
        room_has_op = any(_has_kw(r.get("hang_muc"), KW_OP) for r in rows)
        room_has_ct = any(_has_kw(r.get("hang_muc"), KW_CHONGTHAM) for r in rows)
        room_is_wet = _has_kw(ma, KW_WET) or _has_kw(phong.get("ten"), KW_WET) \
            or any(_has_kw(r.get("hang_muc"), KW_WET) for r in rows)

        for r in rows:
            hm = r.get("hang_muc") or ""
            unit = _unit(r)
            dg = (r.get("dien_giai") or "").strip()
            qc = r.get("quy_cach") or ""
            ky = (r.get("ky_hieu") or "").strip()

            # A1 — dòng đo m²/md/m³ phải có diễn giải phép tính
            if unit in {u.replace(" ", "") for u in DO_UNITS} and not dg:
                add("warn", ma, "A-diengiai",
                    f"[{hm[:40]}] ĐVT '{unit}' nhưng THIẾU diễn giải (số bộ phận×dài×rộng×cao−khoét).")

            # A2 — cửa/vách kính tính cái/bộ phải ghi kích thước R×C
            if _has_kw(hm, KW_CUA) and unit in {u.replace(" ", "") for u in COUNT_UNITS} \
                    and not DIM_RE.search(qc):
                add("warn", ma, "A-kichthuoc",
                    f"[{hm[:40]}] cửa/vách tính cái/bộ nhưng quy_cach THIẾU kích thước R×C.")

            # A3 — rèm nên đo m²/md, không tính bộ/cái
            if _has_kw(hm, KW_REM) and unit in {u.replace(" ", "") for u in COUNT_UNITS}:
                add("warn", ma, "A-rem",
                    f"[{hm[:40]}] rèm nên đo m² (rộng×cao) hoặc md, không tính '{unit}'.")

            # A4 — đồ gỗ may đo nên đo md/m², cảnh báo nếu tính bộ/cái ×1
            if _has_kw(hm, KW_DOGO) and unit in {u.replace(" ", "") for u in COUNT_UNITS}:
                add("info", ma, "A-dogo",
                    f"[{hm[:40]}] đồ gỗ may đo thường đo md/m² (trừ khi spec trọn gói); đang tính '{unit}'.")

            # B — trùng ký hiệu cho 2 hạng mục khác nhau
            if ky:
                prev = seen_kyhieu.get(ky)
                if prev and _norm(prev[1]) != _norm(hm):
                    add("warn", ma, "B-trungma",
                        f"Ký hiệu '{ky}' dùng cho 2 hạng mục khác: '{prev[1][:30]}' ({prev[0]}) và '{hm[:30]}'.")
                else:
                    seen_kyhieu.setdefault(ky, (ma, hm))

            # Giá — ncc trọn gói và VL+NC đều điền mà lệch nhau
            if r["_gia_ncc"] is not None and (r["_gia_vl"] is not None or r["_gia_nc"] is not None):
                vlnc = (r["_gia_vl"] or 0) + (r["_gia_nc"] or 0)
                if abs(vlnc - r["_gia_ncc"]) > 1:
                    add("warn", ma, "gia-lech",
                        f"[{hm[:40]}] don_gia_ncc ({r['_gia_ncc']:,.0f}) ≠ VL+NC ({vlnc:,.0f}).")

            if _norm(r.get("do_tin_cay")) == "thap":
                n_thap += 1

        # C — khu ướt: có lát sàn mà thiếu ốp tường / chống thấm
        if room_is_wet and room_has_lat and not room_has_op:
            add("warn", ma, "C-optuong",
                f"Phòng ướt '{ma}' có LÁT SÀN nhưng KHÔNG có dòng ỐP TƯỜNG (ốp = chu vi×cao−cửa, tách khỏi sàn).")
        if room_is_wet and not room_has_ct:
            add("info", ma, "C-chongtham",
                f"Phòng ướt '{ma}' chưa có dòng CHỐNG THẤM — kiểm nếu thuộc scope.")

    stats = {
        "warn": sum(1 for f in findings if f["level"] == "warn"),
        "info": sum(1 for f in findings if f["level"] == "info"),
        "n_thap": n_thap,
    }
    return findings, stats


def _print_report(findings, stats):
    if not findings:
        print("✓ BOQ sạch — không phát hiện lỗi theo luật.")
    else:
        for f in findings:
            icon = "⚠" if f["level"] == "warn" else "·"
            print(f"  {icon} [{f['room']}] {f['msg']}")
    print(f"\nTổng: {stats['warn']} cảnh báo, {stats['info']} lưu ý, "
          f"{stats['n_thap']} dòng độ tin cậy THẤP (nên ghi notes.md).")
    if stats["warn"]:
        print("→ Sửa các cảnh báo trong 02-boq/*.csv rồi chạy lại tới khi sạch.")


def main():
    if len(sys.argv) < 2:
        sys.exit("Dùng: python scripts/check_boq.py <project_dir>")
    try:
        findings, stats = check(sys.argv[1])
    except Exception as e:
        sys.exit(str(e))
    _print_report(findings, stats)


if __name__ == "__main__":
    main()
