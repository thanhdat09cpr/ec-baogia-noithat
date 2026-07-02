"""
pdf_extract.py — Trích xuất dữ liệu từ bản vẽ PDF vector (CAD xuat PDF).

Voi moi trang PDF:
  - render ra anh PNG (de Claude doc bang vision)
  - lay text + bbox (uu tien so ghi kich thuoc)
  - doan ti le (TL 1:xx) tu title block
  - phan loai sheet (mat bang / mat cat / chi tiet / thong ke ... + bo mon)
  - liet ke cac token so (ung vien kich thuoc mm)

Output:
  <out>/pages/<pdf>__p<NN>.png         anh tung trang
  <out>/<pdf>__p<NN>.json              du lieu chi tiet tung trang
  <out>/_summary.json                  danh muc tat ca trang

Dung:
  python scripts/pdf_extract.py <input_dir_or_pdf> -o <out_dir> [--dpi 170]
"""
import sys, os, re, json, argparse, glob

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("Thieu PyMuPDF. Cai: .venv\\Scripts\\python.exe -m pip install pymupdf")

SCALE_RE = re.compile(r"(?:TI\s*LE|TL|SCALE|TỈ\s*LỆ|TỶ\s*LỆ)\s*[:=]?\s*1\s*[:/]\s*(\d{1,4})", re.I)
NUM_RE = re.compile(r"^\d{2,5}(?:[.,]\d+)?$")  # token so: 2-5 chu so (mm tren ban ve)

# Loai sheet (xet theo thu tu, cu the truoc) -> loai
LOAI_KW = [
    ("thong_ke", r"THONG KE|SCHEDULE|BANG KE"),
    ("mat_cat",  r"MAT CAT|SECTION"),
    ("mat_dung", r"MAT DUNG|ELEVATION"),
    ("chi_tiet", r"CHI TIET|DETAIL"),
    ("mat_bang", r"MAT BANG|PLAN"),
]
# Bo mon: cham diem so tu khoa khop, chon diem cao nhat (dung \b cho tu ngan tranh nham)
BOMON_KW = {
    "XD":       r"KET CAU|STRUCTURE|KIEN TRUC|ARCHITECT|\bMONG\b|\bDAM\b|\bSAN\b|COT THEP|\bXAY\b",
    "ME":       r"\bDIEN\b|ELECTRIC|CHIEU SANG|O CAM|CAP NUOC|THOAT NUOC|PLUMBING|HVAC|DIEU HOA|THONG GIO|PCCC|CHUA CHAY|\bFIRE\b",
    "NOI-THAT": r"NOI THAT|INTERIOR",
}

# Bo dau tieng Viet de match tu khoa
def strip_vn(s):
    table = str.maketrans(
        "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
        "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
        "AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD")
    return s.translate(table)


def classify(text_upper_noaccent):
    loai = "khac"
    for l, pat in LOAI_KW:
        if re.search(pat, text_upper_noaccent):
            loai = l
            break
    scores = {b: len(re.findall(pat, text_upper_noaccent)) for b, pat in BOMON_KW.items()}
    best = max(scores, key=scores.get)
    bomon = best if scores[best] > 0 else None
    return loai, bomon


def detect_scale(text_noaccent):
    m = SCALE_RE.search(text_noaccent)
    return int(m.group(1)) if m else None


def process_pdf(pdf_path, out_dir, dpi):
    name = os.path.splitext(os.path.basename(pdf_path))[0]
    safe = re.sub(r"[^0-9A-Za-z_-]+", "_", strip_vn(name))
    pages_dir = os.path.join(out_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    summary = []
    for i, page in enumerate(doc, 1):
        tag = f"{safe}__p{i:02d}"
        # render anh
        pix = page.get_pixmap(matrix=mat)
        png_path = os.path.join(pages_dir, tag + ".png")
        pix.save(png_path)
        # text + bbox
        raw = page.get_text("dict")
        lines, nums = [], []
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                txt = "".join(span["text"] for span in line["spans"]).strip()
                if not txt:
                    continue
                bbox = [round(c, 1) for c in line["bbox"]]
                lines.append({"t": txt, "bbox": bbox})
                for tok in re.split(r"[\s,;x×X]+", txt):
                    tok = tok.strip()
                    if NUM_RE.match(tok):
                        nums.append(tok)
        full = " ".join(l["t"] for l in lines)
        full_na = strip_vn(full).upper()
        loai, bomon = classify(full_na)
        scale = detect_scale(full_na)
        page_data = {
            "pdf": os.path.basename(pdf_path),
            "page": i,
            "tag": tag,
            "png": os.path.relpath(png_path, out_dir).replace("\\", "/"),
            "size_pt": [round(page.rect.width, 1), round(page.rect.height, 1)],
            "scale_1_to": scale,
            "loai": loai,
            "bo_mon": bomon,
            "so_dong_text": len(lines),
            "dim_tokens": nums[:400],
            "lines": lines,
        }
        with open(os.path.join(out_dir, tag + ".json"), "w", encoding="utf-8") as f:
            json.dump(page_data, f, ensure_ascii=False, indent=1)
        summary.append({k: page_data[k] for k in
                        ("pdf", "page", "tag", "png", "scale_1_to", "loai", "bo_mon", "so_dong_text")})
        print(f"  p{i:02d}: {loai:9s} bo_mon={bomon or '-':8s} scale=1:{scale or '?'} "
              f"text={len(lines):4d} dims={len(nums)}")
    doc.close()
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="thu muc chua PDF hoac 1 file PDF")
    ap.add_argument("-o", "--out", required=True, help="thu muc output")
    ap.add_argument("--dpi", type=int, default=170)
    args = ap.parse_args()

    if os.path.isdir(args.input):
        pdfs = sorted(glob.glob(os.path.join(args.input, "*.pdf")))
    else:
        pdfs = [args.input]
    if not pdfs:
        sys.exit(f"Khong tim thay PDF trong: {args.input}")

    os.makedirs(args.out, exist_ok=True)
    all_summary = []
    for p in pdfs:
        print(f"[PDF] {os.path.basename(p)}")
        all_summary.extend(process_pdf(p, args.out, args.dpi))

    with open(os.path.join(args.out, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"so_pdf": len(pdfs), "so_trang": len(all_summary),
                   "pages": all_summary}, f, ensure_ascii=False, indent=1)
    print(f"\nXong: {len(pdfs)} PDF, {len(all_summary)} trang -> {args.out}\\_summary.json")


if __name__ == "__main__":
    main()
