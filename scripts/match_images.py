"""
match_images.py — Ghep BOQ item <-> anh spec (de chen vao cot MINH HOA).

Doc 02-boq/<room>.csv + 01-extract/spec-img/index.csv, voi moi hang muc chon anh
phu hop nhat theo:
  1) MA trung (LF-02, FA-01, LA-06...) giua quy_cach/hang_muc va anh  -> tin cay cao
  2) fuzzy ten hang_muc <-> text canh anh                              -> tin cay tb
Ket qua ghi 02-boq/<room>.anh.csv (co cot img_path SUA DUOC + cot ung_vien de
nguoi duyet chon tay). Cot img_path la thu duoc build script doc de chen anh.

Dung:  python scripts/match_images.py <project_dir> <room_ma>
"""
import sys, os, csv, re
from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_images import CODE_RE

FUZZY_MIN = 62


def codes_of(*texts):
    s = set()
    for t in texts:
        for m in CODE_RE.finditer(t or ""):
            s.add(m.group(0).upper().replace(" ", ""))
    return s


def load_index(proj):
    p = os.path.join(proj, "01-extract", "spec-img", "index.csv")
    if not os.path.exists(p):
        sys.exit(f"Chua co {p}. Chay spec_images.py truoc.")
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_boq(proj, room):
    p = os.path.join(proj, "02-boq", room + ".csv")
    if not os.path.exists(p):
        sys.exit(f"Khong thay {p}")
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    if len(sys.argv) < 3:
        sys.exit("Dung: python scripts/match_images.py <project_dir> <room_ma>")
    proj = sys.argv[1].rstrip("\\/"); room = sys.argv[2]
    idx = load_index(proj)
    products = [im for im in idx if im.get("kind") in ("product", "swatch")]
    renders = [im for im in idx if im.get("kind") == "render"]
    pool = products + renders          # uu tien product khi fuzzy
    boq = load_boq(proj, room)

    out = []
    for it in boq:
        hm = it.get("hang_muc", ""); qc = it.get("quy_cach", "")
        ic = codes_of(hm, qc)
        pick, by, score = "", "", 0
        # 1) match theo ma
        for im in pool:
            imc = set((im.get("codes") or "").split())
            if ic and (ic & imc):
                pick, by, score = im["img_path"], "code:" + ",".join(ic & imc), 100
                break
        # 2) fuzzy theo ten
        if not pick:
            best = (0, "")
            for im in pool:
                cand = (im.get("text", "") + " " + im.get("codes", "")).strip()
                if not cand:
                    continue
                s = fuzz.token_set_ratio(hm, cand)
                if s > best[0]:
                    best = (s, im["img_path"])
            if best[0] >= FUZZY_MIN:
                pick, by, score = best[1], "fuzzy", int(best[0])
        # ung vien de nguoi duyet chon (top 4 product theo fuzzy)
        cand_sorted = sorted(
            products,
            key=lambda im: fuzz.token_set_ratio(hm, im.get("text", "") + " " + im.get("codes", "")),
            reverse=True)[:4]
        candidates = " | ".join(im["img_path"].split("/")[-1] for im in cand_sorted)
        tc = "cao" if by.startswith("code") else ("trung_binh" if by == "fuzzy" else "")
        out.append({
            "nhom_ma": it.get("nhom_ma", ""), "hang_muc": hm,
            "quy_cach": (qc.replace("\n", " ")[:60]),
            "img_path": pick, "matched_by": by, "score": score,
            "do_tin_cay_anh": tc, "ung_vien": candidates,
        })

    op = os.path.join(proj, "02-boq", room + ".anh.csv")
    with open(op, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["nhom_ma", "hang_muc", "quy_cach",
                                          "img_path", "matched_by", "score",
                                          "do_tin_cay_anh", "ung_vien"])
        w.writeheader(); w.writerows(out)
    matched = sum(1 for r in out if r["img_path"])
    print(f"Ghep {matched}/{len(out)} hang muc co anh -> {op}")
    print("  Mo file, sua cot img_path (dan ten anh trong 01-extract/spec-img/) cho dong con thieu, roi build lai.")


if __name__ == "__main__":
    main()
