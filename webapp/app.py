"""
app.py — Web app (Flask) cho quy trình báo giá fit-out nội thất (đa người dùng).

Luồng wizard: tạo dự án + upload PDF → bóc khối lượng bằng Claude API → file mời thầu
(đơn giá trống) → nhập đơn giá NCC + profit → báo giá nội bộ (TH + VAT).

Mỗi dự án có ID riêng (uuid) + chủ sở hữu (owner) trong DB → hết cảnh trùng tên ghi đè.
File Excel/CSV/PDF vẫn nằm trên đĩa (`projects/<dir_name>/`), DB chỉ index + giữ quyền sở hữu.

Chạy dev:  python webapp/app.py   (mở http://127.0.0.1:5000; DB = SQLite webapp/dev.db)
Prod:      gunicorn -c webapp/gunicorn.conf.py webapp.app:app  (DATABASE_URL = Postgres)
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
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import build_baogia_xlsx, build_boq_xlsx, check_boq  # noqa: E402
from scripts.lib_boq import CSV_COLS as BOQ_CSV_COLS  # noqa: E402
from webapp import jobs  # noqa: E402
from webapp.db import DATABASE_URL, db_session, init_db, shutdown_session  # noqa: E402
from webapp.models import Project, TakeoffJob, User  # noqa: E402

PROJECTS = os.path.join(ROOT, "projects")
BUILD_LOCK = threading.RLock()
# Schema BOQ = 13 cột chuẩn (lib_boq, dùng chung với skill) + profit_override (riêng web).
# F3: profit_override PHẢI nằm trong CSV_COLS, nếu không sẽ bị mất khi lưu BOQ.
CSV_COLS = BOQ_CSV_COLS + ["profit_override"]

# Pha 2 chưa có auth (pha 3 thêm Google OAuth). Tạm dùng 1 user hệ thống làm owner.
SYSTEM_USER_EMAIL = "system@eurostyle.com.vn"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64MB PDF
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-doi-o-prod")
# C2: chạy sau reverse proxy Caddy (tin X-Forwarded-Proto/Host) + cookie an toàn khi HTTPS.
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    PREFERRED_URL_SCHEME="https",
)
app.teardown_appcontext(shutdown_session)

MODELS = {
    "claude-opus-4-8": "Opus 4.8 — mạnh nhất ($5/$25 mỗi 1M token)",
    "claude-sonnet-4-6": "Sonnet 4.6 — nhanh & rẻ hơn ($3/$15 mỗi 1M token)",
}

# N3: model bóc đọc SERVER-SIDE (env, có allowlist) — client KHÔNG chọn/truyền được.
TAKEOFF_MODEL = os.environ.get("TAKEOFF_MODEL", "claude-opus-4-8")
if TAKEOFF_MODEL not in MODELS:
    TAKEOFF_MODEL = "claude-opus-4-8"


# ---------------- DB bootstrap ----------------
def ensure_system_user():
    """Seed 1 user hệ thống (owner tạm ở pha 2). Idempotent."""
    u = db_session.query(User).filter_by(email=SYSTEM_USER_EMAIL).one_or_none()
    if u is None:
        u = User(email=SYSTEM_USER_EMAIL, name="Hệ thống", role="admin", status="approved")
        db_session.add(u)
        db_session.commit()
    return u


def bootstrap():
    """Tạo bảng (SQLite dev) + seed + dọn job mồ côi. Prod chạy `alembic upgrade head` trước."""
    init_db()
    ensure_system_user()
    jobs.reap_orphans()  # O1: dọn job running mồ côi lúc boot


# SQLite dev: tự tạo bảng lúc import (kể cả khi chạy qua gunicorn). Postgres prod dùng Alembic.
if DATABASE_URL.startswith("sqlite"):
    init_db()


# ---------------- current user (pha 3 sẽ thay bằng flask_login.current_user) ----------------
def current_user():
    """Pha 2: trả user hệ thống (get-or-create). Pha 3 nối `flask_login.current_user` thật."""
    return ensure_system_user()


# ---------------- project helpers ----------------
def slug(s):
    s = re.sub(r"[^0-9A-Za-zÀ-ỹ _-]+", "", str(s)).strip()
    return re.sub(r"\s+", "-", s) or "du-an"


def project_dir(project):
    """F2: đọc đường dẫn từ cột dir_name (mới=uuid, legacy=tên thư mục cũ)."""
    return os.path.join(PROJECTS, project.dir_name)


def load_project_or_403(project_id):
    """N1: MỌI truy cập project đi qua đây. 404 nếu không có; 403 nếu không phải owner/admin."""
    p = db_session.get(Project, project_id)
    if p is None:
        abort(404)
    u = current_user()
    if p.owner_id != u.id and not u.is_admin:
        abort(403)
    return p


def read_boq(project, ma):
    p = os.path.join(project_dir(project), "02-boq", f"{ma}.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_boq(project, ma, rows):
    d = os.path.join(project_dir(project), "02-boq")
    os.makedirs(d, exist_ok=True)
    # Union: giữ mọi cột chuẩn + cột lạ đầu vào (không mất profit_override / cột mở rộng).
    extra = [c for r in rows for c in r.keys() if c not in CSV_COLS]
    cols = CSV_COLS + list(dict.fromkeys(extra))
    tmp = os.path.join(d, f".{ma}.csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    os.replace(tmp, os.path.join(d, f"{ma}.csv"))  # atomic (F7/C1 chuẩn bị cho pha 4)


def load_catalog():
    p = os.path.join(ROOT, "data", "danh-muc-noi-that.csv")
    if not os.path.exists(p):
        return []  # clone chưa có data/ → trả rỗng thay vì 500 (frontend dùng scope mặc định)
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
SYSTEM = """Bạn là kỹ sư QS bóc tách khối lượng fit-out nội thất khách sạn/căn hộ tại Việt Nam.
Bạn đọc bản vẽ PDF (mặt bằng bố trí, mặt bằng kích thước, hoàn thiện sàn/tường/trần,
len chân, MẶT ĐỨNG, chi tiết đồ gỗ, cửa, bảng legend FF/LF/PF/SA) và bóc khối lượng
cho MỘT loại phòng đại diện.

Nguyên tắc chung:
- ĐẾM số lượng (cái/bộ) đồ rời/đồ cố định/phụ kiện từ legend + mặt bằng bố trí.
- ĐO m²/md cho vách (rộng×cao−khoét), len chân/nẹp (chu vi−cửa), thảm/giấy dán/vải.
- ƯU TIÊN số ghi kích thước trên bản vẽ; bản vẽ nội thất thường ghi "không theo tỉ lệ".
- ĐVT chuẩn: cai, bo, m2, md, m3.
- do_tin_cay: 'cao' (đếm trực tiếp/bảng), 'trung_binh' (suy từ kích thước), 'thap' (ước lượng).
- TUYỆT ĐỐI KHÔNG bịa đơn giá — chỉ bóc khối lượng. Mục không chắc để do_tin_cay='thap' + ghi_chu.
- quy_cach: ghi spec/vật liệu đọc được từ legend & chi tiết.
- ky_hieu: mã bản vẽ/spec KHỚP legend (LF-07, CA-2.01, D03, WC-02…); không có thì để trống, KHÔNG bịa.

QUY TẮC ĐO BÓC CHUẨN (bắt buộc — chống lỗi QS thường gặp):
- MỌI dòng đo (m2/md/m3) PHẢI có `dien_giai` = phân tích phép tính:
  `số bộ phận × dài × rộng × cao − khoét` + nguồn kích thước (vd "2×(3.2×2.6) − 1.7 cửa").
  Kết quả diễn giải phải KHỚP kl_1phong. Không chấp nhận con số trơ không diễn giải.
- Cửa/vách kính tính cái/bộ nhưng BẮT BUỘC ghi kích thước R×C trong quy_cach (vd 800×2200).
- Khu ướt (WC/bếp/sân phơi): TÁCH RIÊNG lát sàn và ốp tường (ốp = chu vi×cao−cửa, đo từ mặt đứng),
  KHÔNG lấy ốp tường = diện tích sàn. Có dòng chống thấm riêng nếu thuộc scope.
- Đồ gỗ may đo (tủ bếp/tủ áo/tủ lavabo/vách gỗ): đo md hoặc m², KHÔNG "bộ/cái ×1" trừ khi spec trọn gói.
- Rèm: đo m² (rộng×cao) hoặc md, KHÔNG tính "bộ".
- Đọc MẶT ĐỨNG từng phòng để bóc vách trang trí; phòng chỉ có "sàn + trần" là THIẾU.
- MEP (HVAC/cấp thoát nước) ngoài scope nội thất → ghi ghi_chu "do gói M&E riêng", không im lặng bỏ.
Trả về đúng JSON schema được yêu cầu."""

ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "nhom_ma": {"type": "string"},
        "nhom_ten": {"type": "string"},
        "ky_hieu": {"type": "string"},
        "hang_muc": {"type": "string"},
        "quy_cach": {"type": "string"},
        "don_vi": {"type": "string"},
        "dien_giai": {"type": "string"},
        "kl_1phong": {"type": "number"},
        "do_tin_cay": {"type": "string", "enum": ["cao", "trung_binh", "thap"]},
        "ghi_chu": {"type": "string"},
    },
    "required": ["nhom_ma", "nhom_ten", "ky_hieu", "hang_muc", "quy_cach", "don_vi",
                 "dien_giai", "kl_1phong", "do_tin_cay", "ghi_chu"],
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
- Mỗi phần tử: nhom_ma, nhom_ten, ky_hieu, hang_muc, quy_cach, don_vi, dien_giai,
  kl_1phong (số), do_tin_cay ('cao'|'trung_binh'|'thap'), ghi_chu.
- `ky_hieu`: mã bản vẽ/spec khớp legend (để trống nếu không có, không bịa).
- `dien_giai`: BẮT BUỘC với mọi dòng m2/md/m3 — `số bộ phận × dài × rộng × cao − khoét`
  + nguồn kích thước, khớp kl_1phong. Dòng đếm cái/bộ để trống dien_giai.
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
        # GĐ1: 3 cột giá luôn trống (NCC chào ở GĐ2 — VL+NC hoặc trọn gói).
        r["don_gia_vl"] = ""
        r["don_gia_nc"] = ""
        r["don_gia_ncc"] = ""
        r.setdefault("ky_hieu", "")
        r.setdefault("quy_cach", "")
        r.setdefault("dien_giai", "")
        r.setdefault("ghi_chu", "")
    usage = resp.usage
    return rows, {"input": usage.input_tokens, "output": usage.output_tokens}


# ---------------- routes ----------------
@app.route("/")
def index():
    return render_template("index.html", models=MODELS)


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/catalog")
def api_catalog():
    cat = load_catalog()
    groups = {}
    for c in cat:
        groups.setdefault(c["nhom_ma"], c["nhom_ten"])
    return jsonify({"groups": [{"ma": k, "ten": v} for k, v in groups.items()]})


@app.route("/api/projects", methods=["GET"])
def api_projects():
    """Danh sách dự án của owner (admin thấy tất) — chuẩn bị dashboard pha 5."""
    u = current_user()
    q = db_session.query(Project)
    if not u.is_admin:
        q = q.filter_by(owner_id=u.id)
    items = q.order_by(Project.updated_at.desc()).all()
    return jsonify({"projects": [
        {"id": p.id, "ten": p.ten, "dia_diem": p.dia_diem, "hang_muc": p.hang_muc,
         "status": p.status, "updated_at": p.updated_at.isoformat() if p.updated_at else None}
        for p in items]})


@app.route("/api/project/<project_id>", methods=["GET"])
def api_project_get(project_id):
    """Mở lại 1 dự án: trả cấu hình (cau-hinh.json) để frontend rehydrate wizard."""
    p = load_project_or_403(project_id)
    cfgp = os.path.join(project_dir(p), "cau-hinh.json")
    cfg = {}
    if os.path.exists(cfgp):
        with open(cfgp, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    return jsonify({"ok": True, "id": p.id, "ten": p.ten, "status": p.status, "config": cfg})


@app.route("/api/project", methods=["POST"])
def api_project():
    d = request.get_json(silent=True) or {}
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
    u = current_user()
    pid = str(uuid.uuid4())
    # F2: dự án mới → thư mục = uuid (đặt id + dir_name cùng lúc, không cần flush lấy id).
    p = Project(id=pid, dir_name=pid, owner_id=u.id, ten=cfg["du_an"], slug=slug(cfg["du_an"]),
                dia_diem=cfg["dia_diem"], hang_muc=cfg["hang_muc"], status="draft")
    db_session.add(p)
    P = project_dir(p)
    os.makedirs(P, exist_ok=True)
    with open(os.path.join(P, "cau-hinh.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    db_session.commit()
    return jsonify({"ok": True, "project_id": p.id})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    project_id = request.form.get("project_id")
    ma = request.form.get("ma")
    f = request.files.get("pdf")
    if not project_id or not ma or f is None:
        return jsonify({"ok": False, "error": "Thiếu project_id / ma / pdf."}), 400
    p = load_project_or_403(project_id)
    d = os.path.join(project_dir(p), "input")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{slug(ma)}.pdf")
    f.save(path)
    return jsonify({"ok": True, "size": os.path.getsize(path)})


@app.route("/api/pdf/<project_id>/<ma>")
def api_pdf(project_id, ma):
    p = load_project_or_403(project_id)
    return send_from_directory(os.path.join(project_dir(p), "input"), f"{slug(ma)}.pdf")


@app.route("/api/takeoff", methods=["POST"])
def api_takeoff():
    """Tạo JOB NỀN bóc khối lượng, trả job_id ngay (không block). N3: không nhận api_key/model."""
    d = request.get_json(silent=True) or {}
    room = d.get("room")
    if not d.get("project_id") or not isinstance(room, dict) or not room.get("ma"):
        return jsonify({"ok": False, "error": "Thiếu project_id / room.ma."}), 400
    p = load_project_or_403(d["project_id"])
    scope = d.get("scope", ["I.1", "I.2", "I.3", "I.4", "I.5"])
    pdf_path = os.path.join(project_dir(p), "input", f"{slug(room['ma'])}.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"ok": False, "error": "Chưa upload PDF cho phòng này."}), 400
    u = current_user()
    job, created = jobs.submit_takeoff(p.id, u.id, room, scope)
    return jsonify({"ok": True, "job_id": job.id, "status": job.status, "created": created})


@app.route("/api/takeoff/status/<job_id>")
def api_takeoff_status(job_id):
    """Trạng thái job. N1: chỉ chủ job (hoặc admin) xem được."""
    u = current_user()
    job = db_session.get(TakeoffJob, job_id)
    if job is None:
        abort(404)
    if job.user_id != u.id and not u.is_admin:
        abort(403)
    resp = {"ok": True, "status": job.status}
    if job.status == "error":
        resp["error"] = job.error
    elif job.status == "done":
        p = db_session.get(Project, job.project_id)
        resp["rows"] = read_boq(p, job.room_ma)
        resp["usage"] = {"input": job.input_tokens, "output": job.output_tokens}
        # Soát lỗi BOQ bằng luật (AI-free) — chỉ trả cảnh báo của phòng vừa bóc.
        try:
            findings, _ = check_boq.check(project_dir(p))
            resp["warnings"] = [
                {"level": f["level"], "code": f["code"], "msg": f["msg"]}
                for f in findings if f["room"] == job.room_ma
            ]
        except Exception:
            app.logger.exception("check_boq lỗi (project=%s, room=%s)", p.id, job.room_ma)
            resp["warnings"] = []
    return jsonify(resp)


@app.route("/api/boq", methods=["GET", "POST"])
def api_boq():
    if request.method == "GET":
        pid = request.args.get("project_id")
        ma = request.args.get("ma")
        if not pid or not ma:
            return jsonify({"ok": False, "error": "Thiếu project_id / ma."}), 400
        p = load_project_or_403(pid)
        return jsonify({"rows": read_boq(p, ma)})
    d = request.get_json(silent=True) or {}
    if not d.get("project_id") or not d.get("ma") or "rows" not in d:
        return jsonify({"ok": False, "error": "Thiếu project_id / ma / rows."}), 400
    p = load_project_or_403(d["project_id"])
    write_boq(p, d["ma"], d["rows"])
    return jsonify({"ok": True})


@app.route("/api/moi-thau", methods=["POST"])
def api_moi_thau():
    d = request.get_json(silent=True) or {}
    if not d.get("project_id"):
        return jsonify({"ok": False, "error": "Thiếu mã dự án."}), 400
    p = load_project_or_403(d["project_id"])
    try:
        _out_path, stats = run_builder(build_boq_xlsx.build, project_dir(p))
    except Exception:
        app.logger.exception("Không xuất được file mời thầu cho project=%s", p.id)
        return jsonify({"ok": False, "error":
                        "Không xuất được file mời thầu. Kiểm tra cấu hình dự án và BOQ."}), 500
    return jsonify({"ok": True, "stats": stats,
                    "download": f"/api/download/{p.id}/moi-thau.xlsx"})


@app.route("/api/bao-gia", methods=["POST"])
def api_bao_gia():
    d = request.get_json(silent=True) or {}
    if not d.get("project_id"):
        return jsonify({"ok": False, "error": "Thiếu mã dự án."}), 400
    p = load_project_or_403(d["project_id"])
    try:
        # Config update and build must be atomic for one-process threaded gunicorn.
        with BUILD_LOCK:
            P = project_dir(p)
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
        app.logger.exception("Dữ liệu báo giá không hợp lệ cho project=%s", p.id)
        return jsonify({"ok": False, "error":
                        "Không xuất được báo giá nội bộ. Kiểm tra dữ liệu dự án và số nhập."}), 400
    except Exception:
        app.logger.exception("Không xuất được báo giá nội bộ cho project=%s", p.id)
        return jsonify({"ok": False, "error":
                        "Không xuất được báo giá nội bộ. Kiểm tra đơn giá NCC, profit và cấu hình."}), 500
    return jsonify({"ok": True, "stats": stats,
                    "download": f"/api/download/{p.id}/bao-gia-noi-bo.xlsx"})


@app.route("/api/download/<project_id>/<fname>")
def api_download(project_id, fname):
    p = load_project_or_403(project_id)
    return send_from_directory(os.path.join(project_dir(p), "03-baogia"), fname,
                               as_attachment=True)


if __name__ == "__main__":
    bootstrap()
    print("E&C báo giá nội thất — http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
