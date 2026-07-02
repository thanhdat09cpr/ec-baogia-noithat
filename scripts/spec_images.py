"""
spec_images.py — Quet PDF spec / ban ve, TRICH anh san pham + danh chi muc.

Muc dich: tu dong tim anh minh hoa trong ho so (spec, ban ve chi tiet, legend)
de sau do chen vao cot MINH HOA cua bao gia. Moi anh duoc:
  - trich tu PDF (raster nhung), auto-crop vien trang (crop vua du),
  - gan MA (LA-06, CH-1.02, FF-03...) + text mo ta lay tu chu NAM CANH anh tren trang,
  - luu ra <out>/spec-img/<id>.png + <out>/spec-img/index.csv.

Dung:
  python scripts/spec_images.py <pdf_hoac_thu_muc> [pdf2 ...] -o <project_dir>
Vi du:
  python scripts/spec_images.py "data/NDA-...GR1.pdf" -o projects/68-Tho-Nhuom
"""
import sys, os, csv, re, io, glob, hashlib
import fitz  # PyMuPDF
from PIL import Image, ImageChops

CODE_RE = re.compile(r'\b(?:LA|LF|FF|FA|SA|PF|CH|CA|CUR|RUG|TB|TU|ART|BE|WD|CT|ST|PT|WC|GL|MT|WF|CP)-?\s?\d{1,2}(?:\.\d{1,2})?\b',
                     re.IGNORECASE)
MIN_PX = 40          # bo anh qua nho (icon/mask)
MIN_BBOX_PT = 24     # bo anh dat qua nho tren trang (pt)
MAX_PAGE_FRAC = 0.82 # bo anh phu gan het trang (background/anh ban ve lon)
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

# Cac cum "boilerplate" trong khung ghi chu ban ve -> loai khoi text mo ta
_BOILER = [
    "bản vẽ", "ban ve", "không được dùng", "khong duoc dung", "chứng nhận",
    "người thi công", "nguoi thi cong", "kích thước tại hiện trường",
    "kich thuoc tai hien truong", "khởi công", "khoi cong", "notes", "ghi chú",
    "ghi chu", "không theo tỉ lệ", "khong theo ti le", "certified", "contractor",
    "drawing", "scale", "site before", "shall not", "copyright", "sao chép",
    "sao chep", "thuyết minh", "thuyet minh", "hợp đồng", "hop dong", "master",
    "project", "development design", "khách sạn", "khach san", "hotel", "hanoi",
    "hà nội", "ha noi", "thợ nhuộm", "tho nhuom", "handwritten",
]


def clean_text(txt):
    """Bo cac cau/cum boilerplate trong khung ghi chu, giu lai mo ta san pham."""
    parts = re.split(r'[.\n]|  +', txt)
    keep = []
    for p in parts:
        pl = p.lower()
        if len(p.strip()) < 2:
            continue
        if any(b in pl for b in _BOILER):
            continue
        keep.append(p.strip())
    return re.sub(r'\s+', ' ', " ".join(keep)).strip()


def autocrop(im, bg=(255, 255, 255), tol=12, pad=6):
    """Cat bot vien don sac (trang) quanh anh, chua lai padding nho."""
    rgb = im.convert("RGB")
    bg_im = Image.new("RGB", rgb.size, bg)
    diff = ImageChops.difference(rgb, bg_im)
    # nguong hoa de bo nhieu jpeg nhat
    diff = diff.point(lambda p: 255 if p > tol else 0)
    bbox = diff.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad); t = max(0, t - pad)
    r = min(im.width, r + pad); b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def nearby_text(page, rect):
    """Lay chu nam SAT anh (uu tien ngay duoi/tren, vung legend hep)."""
    mx = min(rect.width * 0.35, 55.0)     # ngang: hep
    my = min(rect.height * 0.55, 90.0)    # doc: chu thich thuong o duoi
    zone = fitz.Rect(rect.x0 - mx, rect.y0 - my * 0.4, rect.x1 + mx, rect.y1 + my)
    words = page.get_text("words")  # x0,y0,x1,y1,word,block,line,wno
    got = []
    for w in words:
        wr = fitz.Rect(w[:4])
        if wr.intersects(zone):
            dy = abs(wr.y0 - rect.y1)
            got.append((dy, wr.y0, wr.x0, w[4]))
    got.sort(key=lambda g: (g[1], g[2]))
    txt = " ".join(g[3] for g in got[:40])
    return re.sub(r'\s+', ' ', txt).strip()


def classify(px_w, px_h):
    ar = px_w / px_h if px_h else 1
    if px_w >= 1500 or px_h >= 1500:
        return "render"          # phoi canh / trang raster lon
    if ar < 0.28 or ar > 3.6:
        return "swatch"          # dai mau / thanh vat lieu
    return "product"


def extract_pdf(pdf_path, out_dir, rows, seen_hashes):
    doc = fitz.open(pdf_path)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    n = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        parea = page.rect.width * page.rect.height
        info = page.get_image_info(xrefs=True)
        for it in info:
            xref = it.get("xref", 0)
            bbox = fitz.Rect(it["bbox"])
            if bbox.width < MIN_BBOX_PT or bbox.height < MIN_BBOX_PT:
                continue
            if (bbox.width * bbox.height) / parea > MAX_PAGE_FRAC:
                continue  # anh nen / ban ve toan trang
            if xref <= 0:
                continue
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:      # CMYK/alpha -> RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                im = Image.open(io.BytesIO(pix.tobytes("png")))
            except Exception:
                continue
            if im.width < MIN_PX or im.height < MIN_PX:
                continue
            im = autocrop(im)
            if im.width < MIN_PX or im.height < MIN_PX:
                continue
            # chong trung (cung 1 anh dung nhieu cho)
            h = hashlib.md5(im.tobytes()).hexdigest()[:12]
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            raw = nearby_text(page, bbox)
            codes = sorted(set(m.group(0).upper().replace(" ", "")
                               for m in CODE_RE.finditer(raw)))
            desc = clean_text(raw)
            img_id = f"{base[:16]}_p{pno+1:02d}_{h}"
            img_id = re.sub(r'[^0-9A-Za-z_.-]', '_', img_id)
            rel = os.path.join("spec-img", img_id + ".png")
            im.save(os.path.join(out_dir, rel))
            rows.append({
                "id": img_id, "pdf": os.path.basename(pdf_path), "page": pno + 1,
                "kind": classify(im.width, im.height),
                "px_w": im.width, "px_h": im.height,
                "codes": " ".join(codes), "text": desc[:160],
                "img_path": rel.replace("\\", "/"),
            })
            n += 1
    return n


def ingest_folder(folder, out_dir, rows, seen_hashes):
    """Nhan thu muc anh dat san: ten file = ma/ten (vd LA-06.png, giuong-king.jpg)."""
    n = 0
    files = [f for f in glob.glob(os.path.join(folder, "**", "*"), recursive=True)
             if f.lower().endswith(IMG_EXT)]
    for fp in files:
        try:
            im = Image.open(fp); im.load()
        except Exception:
            continue
        im = autocrop(im)
        if im.width < MIN_PX or im.height < MIN_PX:
            continue
        h = hashlib.md5(im.tobytes()).hexdigest()[:12]
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        stem = os.path.splitext(os.path.basename(fp))[0]
        codes = sorted(set(m.group(0).upper().replace(" ", "")
                           for m in CODE_RE.finditer(stem)))
        img_id = re.sub(r'[^0-9A-Za-z_.-]', '_', stem)[:40] + "_" + h[:6]
        rel = os.path.join("spec-img", img_id + ".png")
        im.convert("RGB").save(os.path.join(out_dir, rel))
        rows.append({
            "id": img_id, "pdf": "(folder) " + os.path.basename(folder),
            "page": 0, "kind": classify(im.width, im.height),
            "px_w": im.width, "px_h": im.height,
            "codes": " ".join(codes), "text": stem[:160],
            "img_path": rel.replace("\\", "/"),
        })
        n += 1
    return n


def main():
    a = sys.argv[1:]
    if "-o" not in a:
        sys.exit("Dung: python scripts/spec_images.py <pdf|folder ...> -o <project_dir>")
    oi = a.index("-o")
    proj = a[oi + 1].rstrip("\\/")
    srcs = a[:oi]
    if not srcs:
        sys.exit("Thieu file/thu muc spec.")
    out_dir = os.path.join(proj, "01-extract")
    os.makedirs(os.path.join(out_dir, "spec-img"), exist_ok=True)
    rows, seen = [], set()
    for src in srcs:
        if os.path.isdir(src):
            # thu muc: uu tien anh dat san; con PDF trong do thi quet luon
            pdfs = glob.glob(os.path.join(src, "**", "*.pdf"), recursive=True)
            imgs = [f for f in glob.glob(os.path.join(src, "**", "*"), recursive=True)
                    if f.lower().endswith(IMG_EXT)]
            if imgs:
                n = ingest_folder(src, out_dir, rows, seen)
                print(f"  (folder) {os.path.basename(src)}: +{n} anh dat san")
            for pdf in pdfs:
                try:
                    n = extract_pdf(pdf, out_dir, rows, seen)
                    print(f"  {os.path.basename(pdf)}: +{n} anh")
                except Exception as e:
                    print(f"  [LOI] {pdf}: {e}")
        else:
            try:
                n = extract_pdf(src, out_dir, rows, seen)
                print(f"  {os.path.basename(src)}: +{n} anh")
            except Exception as e:
                print(f"  [LOI] {src}: {e}")
    idx = os.path.join(out_dir, "spec-img", "index.csv")
    with open(idx, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "pdf", "page", "kind", "px_w",
                                          "px_h", "codes", "text", "img_path"])
        w.writeheader(); w.writerows(rows)
    print(f"\nTong {len(rows)} anh -> {idx}")
    print("Buoc tiep: python scripts/match_images.py " + proj + " <room.csv>")


if __name__ == "__main__":
    main()
