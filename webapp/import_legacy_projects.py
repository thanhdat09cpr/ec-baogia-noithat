"""
import_legacy_projects.py — Đưa các dự án CŨ (đã có thư mục trên đĩa) vào DB.

Dự án legacy giữ NGUYÊN tên thư mục (vd `68-Tho-Nhuom`, `ROX2-Z3SL4`); chỉ THÊM 1 bản ghi
Project trỏ `dir_name` = tên thư mục cũ (F2) → mở/ build lại đúng số cũ, không đổi đường dẫn.

Idempotent: chạy lại không tạo trùng (khóa theo `dir_name`).
Owner mặc định = user hệ thống/admin (email SYSTEM_USER_EMAIL), có thể override bằng --owner-email.

Chạy:  python -m webapp.import_legacy_projects [--owner-email a@b.com] [ten_thu_muc ...]
Không truyền tên thư mục → tự quét mọi thư mục con của projects/ có cau-hinh.json.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from webapp.db import db_session, init_db  # noqa: E402
from webapp.models import Project, User  # noqa: E402

PROJECTS = os.path.join(ROOT, "projects")
SYSTEM_USER_EMAIL = "system@eurostyle.com.vn"


def _slug(s):
    import re
    s = re.sub(r"[^0-9A-Za-zÀ-ỹ _-]+", "", str(s)).strip()
    return re.sub(r"\s+", "-", s) or "du-an"


def _owner(email):
    u = db_session.query(User).filter_by(email=email).one_or_none()
    if u is None:
        u = User(email=email, name="Hệ thống", role="admin", status="approved")
        db_session.add(u)
        db_session.commit()
    return u


def _discover():
    if not os.path.isdir(PROJECTS):
        return []
    return [d for d in sorted(os.listdir(PROJECTS))
            if os.path.isfile(os.path.join(PROJECTS, d, "cau-hinh.json"))]


def import_dir(dir_name, owner):
    exist = db_session.query(Project).filter_by(dir_name=dir_name).one_or_none()
    if exist is not None:
        return exist, False
    cfg_path = os.path.join(PROJECTS, dir_name, "cau-hinh.json")
    cfg = {}
    if os.path.isfile(cfg_path):
        with open(cfg_path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    ten = cfg.get("du_an") or dir_name
    p = Project(owner_id=owner.id, ten=ten, slug=_slug(ten), dir_name=dir_name,
                dia_diem=cfg.get("dia_diem", ""), hang_muc=cfg.get("hang_muc", ""),
                status="quoted")
    db_session.add(p)
    db_session.commit()
    return p, True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Import dự án legacy vào DB.")
    ap.add_argument("dirs", nargs="*", help="Tên thư mục dự án (mặc định: tự quét).")
    ap.add_argument("--owner-email", default=SYSTEM_USER_EMAIL)
    args = ap.parse_args(argv)

    init_db()
    owner = _owner(args.owner_email)
    dirs = args.dirs or _discover()
    if not dirs:
        print("Không tìm thấy dự án nào trong projects/.")
        return 0
    for d in dirs:
        _p, created = import_dir(d, owner)
        print(f"{'THÊM' if created else 'ĐÃ CÓ'}: {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
