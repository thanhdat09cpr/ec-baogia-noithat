"""
app.py — Web app (Flask) cho quy trình báo giá fit-out nội thất.

Luồng wizard 4 bước:
  1. Tạo dự án + upload PDF bản vẽ từng loại phòng
  2. Bóc khối lượng TỰ ĐỘNG bằng Claude API (đọc PDF) -> bảng BOQ (xem & sửa)
  3. Xuất file mời thầu (đơn giá trống) để gửi nhà thầu phụ
  4. Nhập đơn giá NCC + profit -> xuất báo giá nội bộ (TH + VAT)

Chay:  python webapp/app.py   (mo http://127.0.0.1:5000)
"""
import base64
import contextlib
import csv
import io
import json
import math
import os
import re
import sys
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import build_baogia_xlsx, build_boq_xlsx  # noqa: E402

PROJECTS = os.path.join(ROOT, "projects")
BUILD_LOCK = threading.RLock()
CSV_COLS = ["nhom_ma", "nhom_ten", "hang_muc", "quy_cach", "don_vi",
            "kl_1phong", "don_gia_ncc", "do_tin_cay", "ghi_chu"]

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB PDF

MODELS = {
    "claude-opus-4-8": "Opus 4.8 — mạnh nhất ($5/$25 mỗi 1M token)",
    "claude-sonnet-4-6": "Sonnet 4.6 — nhanh & rẻ hơn ($3/$15 mỗi 1M token)",
}


# ---------------- helpers ----------------
def slug(s):
    s = re.sub(r"[^0-9A-Za-zÀ-ỹ _-]+", "", str(s)).strip()
    return re.sub(r"\s+", "-", s) or "du-an"


def pdir(name):
    return os.path.join(PROJECTS, slug(name))


def read_boq(project, ma):
    p = os.path.join(pdir(project), "02-boq", f"{ma}.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_boq(project, ma, rows):
    d = os.path.join(pdir(project), "02-boq")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{ma}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in CSV_COLS})


def load_catalog():
    p = os.path.join(ROOT, "data", "danh-muc-noi-that.csv")
    out = []
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out.append(r)
    return out


def run_builder(builder, *args, **kwargs):
    buf = io.StringIO()
    with BUILD_LOCK:
        # Builder scripts still print progress; stdout capture is process-global.
        with contextlib.redirect_stdout(buf):
            out_path, stats = builder(*args, **kwargs)
    log_output = buf.getvalue()
    if log_output:
        app.logger.info("Build output:\n%s", log_output.rstrip())
    return out_path, stats


# ---------------- takeoff (Claude API) ----------------
SYSTEM = """Bạn là kỹ sư bóc tách khối lượng fit-out nội thất khách sạn/căn hộ tại Việt Nam.
Bạn đọc bản vẽ PDF (mặt bằng bố trí, mặt bằng kích thước, hoàn thiện sàn/tường/trần,
len chân, mặt đứng, chi tiết đồ gỗ, cửa, bảng legend FF/LF/PF/SA) và bóc khối lượng
cho MỘT loại phòng đại diện.

Nguyên tắc:
- ĐẾM số lượng (cái/bộ) đồ rời/đồ cố định/phụ kiện từ legend + mặt bằng bố trí.
- ĐO m²/md cho vách (rộng×cao−khoét), len chân/nẹp (chu vi−cửa), thảm/giấy dán/vải.
- ƯU TIÊN số ghi kích thước trên bản vẽ; bản vẽ nội thất thường ghi "không theo tỉ lệ".
- ĐVT chuẩn: cai, bo, m2, md.
- do_tin_cay: 'cao' (đếm trực tiếp/bảng), 'trung_binh' (suy từ kích thước), 'thap' (ước lượng).
- TUYỆT ĐỐI KHÔNG bịa đơn giá — chỉ bóc khối lượng. Mục không chắc để do_tin_cay='thap' và ghi chú.
- quy_cach: ghi spec/vật liệu đọc được từ legend & chi tiết.
Trả về đúng JSON schema được yêu cầu."""

ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "nhom_ma": {"type": "string"},
        "nhom_ten": {"type": "string"},
        "hang_muc": {"type": "string"},
        "quy_cach": {"type": "string"},
        "don_vi": {"type": "string"},
        "kl_1phong": {"type": "number"},
        "do_tin_cay": {"type": "string", "enum": ["cao", "trung_binh", "thap"]},
        "ghi_chu": {"type": "string"},
    },
    "required": ["nhom_ma", "nhom_ten", "hang_muc", "quy_cach", "don_vi",
                 "kl_1phong", "do_tin_cay", "ghi_chu"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "items": ROW_SCHEMA}},
    "required": ["rows"],
    "additionalProperties": False,
}


def _extract_rows(text):
    """Lay 'rows' tu text JSON; chiu duoc code-fence / text thua."""
    text = text.strip()
    if "```" in text:
        text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text).get("rows", [])
    except Exception:
        m = re.search(r'"rows"\s*:\s*(\[.*\])', text, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    raise ValueError("Không phân tích được JSON từ phản hồi AI.")


def do_takeoff(pdf_path, room, scope, model, api_key):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    cat = [c for c in load_catalog() if c["nhom_ma"] in scope]
    cat_txt = "\n".join(
        f"- [{c['nhom_ma']} {c['nhom_ten']}] {c['hang_muc']} (ĐVT {c['don_vi']})"
        for c in cat)
    prompt = f"""Bóc khối lượng cho loại phòng: {room['ten']} (mã {room['ma']}).
Chỉ bóc các NHÓM trong phạm vi: {', '.join(scope)}.

Danh mục hạng mục tham chiếu (dùng đúng nhom_ma/nhom_ten và tên hạng mục gần nhất;
được thêm hạng mục mới nếu bản vẽ có):
{cat_txt}

YÊU CẦU:
- Trả về JSON object có khóa 'rows' = danh sách cho 1 phòng (kl_1phong = khối lượng 1 phòng).
- Mỗi phần tử: nhom_ma, nhom_ten, hang_muc, quy_cach, don_vi, kl_1phong (số),
  do_tin_cay ('cao'|'trung_binh'|'thap'), ghi_chu.
- KHÔNG điền đơn giá (nhà thầu phụ sẽ chào). Chỉ khối lượng + quy cách + ĐVT.
- Chỉ trả về JSON, không kèm văn bản khác."""

    kwargs = dict(
        model=model, max_tokens=16000, thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": [
            {"type": "document",
             "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    try:
        resp = client.messages.create(
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}}, **kwargs)
    except TypeError:                       # SDK cũ không có output_config
        resp = client.messages.create(**kwargs)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    rows = _extract_rows(text)
    for r in rows:
        r["don_gia_ncc"] = ""
        r.setdefault("quy_cach", "")
        r.setdefault("ghi_chu", "")
    usage = resp.usage
    return rows, {"input": usage.input_tokens, "output": usage.output_tokens}


# ---------------- routes ----------------
@app.route("/")
def index():
    return render_template("index.html", models=MODELS)


@app.route("/api/catalog")
def api_catalog():
    cat = load_catalog()
    groups = {}
    for c in cat:
        groups.setdefault(c["nhom_ma"], c["nhom_ten"])
    return jsonify({"groups": [{"ma": k, "ten": v} for k, v in groups.items()]})


@app.route("/api/project", methods=["POST"])
def api_project():
    d = request.json
    cfg = {
        "du_an": d.get("du_an", "Dự án nội thất"),
        "dia_diem": d.get("dia_diem", ""),
        "hang_muc": d.get("hang_muc", "THI CÔNG HOÀN THIỆN NỘI THẤT"),
        "profit_percent": float(d.get("profit_percent", 10)),
        "vat_percent": float(d.get("vat_percent", 8)),
        "preliminaries_lumpsum": float(d.get("preliminaries_lumpsum", 0)),
        "scope": d.get("scope", ["I.1", "I.2", "I.3", "I.4", "I.5"]),
        "phong": d.get("phong", []),
    }
    P = pdir(cfg["du_an"])
    os.makedirs(P, exist_ok=True)
    with open(os.path.join(P, "cau-hinh.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "project": slug(cfg["du_an"])})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    project = request.form["project"]
    ma = request.form["ma"]
    f = request.files["pdf"]
    d = os.path.join(pdir(project), "input")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{slug(ma)}.pdf")
    f.save(path)
    return jsonify({"ok": True, "size": os.path.getsize(path)})


@app.route("/api/pdf/<project>/<ma>")
def api_pdf(project, ma):
    return send_from_directory(os.path.join(pdir(project), "input"), f"{slug(ma)}.pdf")


@app.route("/api/takeoff", methods=["POST"])
def api_takeoff():
    d = request.json
    project, room = d["project"], d["room"]
    scope = d.get("scope", ["I.1", "I.2", "I.3", "I.4", "I.5"])
    model = d.get("model", "claude-opus-4-8")
    api_key = (d.get("api_key") or "").strip() or None
    pdf_path = os.path.join(pdir(project), "input", f"{slug(room['ma'])}.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"ok": False, "error": "Chưa upload PDF cho phòng này."}), 400
    try:
        rows, usage = do_takeoff(pdf_path, room, scope, model, api_key)
    except Exception as e:
        import anthropic
        if isinstance(e, anthropic.AuthenticationError):
            return jsonify({"ok": False, "error":
                "Lỗi xác thực Anthropic API. Nhập API key hoặc đặt ANTHROPIC_API_KEY / "
                "đăng nhập 'ant auth login'."}), 401
        app.logger.exception("Bóc khối lượng lỗi cho project=%s room=%s",
                             project, room.get("ma"))
        return jsonify({"ok": False, "error":
                        "Không bóc được khối lượng. Kiểm tra PDF, model và cấu hình API."}), 500
    write_boq(project, room["ma"], rows)
    return jsonify({"ok": True, "rows": rows, "usage": usage})


@app.route("/api/boq", methods=["GET", "POST"])
def api_boq():
    if request.method == "GET":
        return jsonify({"rows": read_boq(request.args["project"], request.args["ma"])})
    d = request.json
    write_boq(d["project"], d["ma"], d["rows"])
    return jsonify({"ok": True})


@app.route("/api/moi-thau", methods=["POST"])
def api_moi_thau():
    d = request.get_json(silent=True) or {}
    project = d.get("project")
    if not project:
        return jsonify({"ok": False, "error": "Thiếu mã dự án."}), 400
    try:
        _out_path, stats = run_builder(build_boq_xlsx.build, pdir(project))
    except Exception:
        app.logger.exception("Không xuất được file mời thầu cho project=%s", project)
        return jsonify({"ok": False, "error":
                        "Không xuất được file mời thầu. Kiểm tra cấu hình dự án và BOQ."}), 500
    return jsonify({"ok": True, "stats": stats,
                    "download": f"/api/download/{project}/moi-thau.xlsx"})


@app.route("/api/bao-gia", methods=["POST"])
def api_bao_gia():
    d = request.get_json(silent=True) or {}
    project = d.get("project")
    if not project:
        return jsonify({"ok": False, "error": "Thiếu mã dự án."}), 400
    try:
        # Config update and build must be atomic for one-process threaded gunicorn.
        with BUILD_LOCK:
            P = pdir(project)
            cfgp = os.path.join(P, "cau-hinh.json")
            with open(cfgp, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            for k in ("profit_percent", "vat_percent", "preliminaries_lumpsum"):
                if k in d:
                    value = float(d[k])
                    if not math.isfinite(value):
                        raise ValueError(f"{k} must be finite")
                    cfg[k] = value
            with open(cfgp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            _out_path, stats = run_builder(build_baogia_xlsx.build, P)
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        app.logger.exception("Dữ liệu báo giá không hợp lệ cho project=%s", project)
        return jsonify({"ok": False, "error":
                        "Không xuất được báo giá nội bộ. Kiểm tra dữ liệu dự án và số nhập."}), 400
    except Exception:
        app.logger.exception("Không xuất được báo giá nội bộ cho project=%s", project)
        return jsonify({"ok": False, "error":
                        "Không xuất được báo giá nội bộ. Kiểm tra đơn giá NCC, profit và cấu hình."}), 500
    return jsonify({"ok": True, "stats": stats,
                    "download": f"/api/download/{project}/bao-gia-noi-bo.xlsx"})


@app.route("/api/download/<project>/<fname>")
def api_download(project, fname):
    return send_from_directory(os.path.join(pdir(project), "03-baogia"), fname,
                               as_attachment=True)


if __name__ == "__main__":
    print("E&C báo giá nội thất — http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
