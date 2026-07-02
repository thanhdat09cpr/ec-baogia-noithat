"""
db.py — Kết nối cơ sở dữ liệu (SQLAlchemy 2.0) cho web app báo giá nội thất.

- Prod: PostgreSQL qua `DATABASE_URL` (vd `postgresql+psycopg://user:pass@db:5432/baogia`).
- Dev:  không đặt `DATABASE_URL` → fallback SQLite file `webapp/dev.db` (chạy được ngay,
  không cần cài Postgres). Alembic vẫn quản migration cho prod.

Phiên (session) theo THREAD: gunicorn chạy 1 worker `gthread` nên mỗi request = 1 thread →
`scoped_session` tách phiên đúng theo request; `remove()` gọi ở teardown của Flask.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite dev cần đường dẫn tuyệt đối để tránh phụ thuộc CWD.
_DEFAULT_SQLITE = "sqlite:///" + os.path.join(WEBAPP_DIR, "dev.db").replace("\\", "/")
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

# SQLite + nhiều thread: cần check_same_thread=False; Postgres không cần cờ này.
_engine_kwargs = {"pool_pre_ping": True, "future": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# scoped_session mặc định dùng thread-local làm scope → đúng cho gthread worker.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
db_session = scoped_session(SessionLocal)


def init_db():
    """Tạo bảng cho DEV (SQLite) khi không chạy Alembic. Prod dùng `alembic upgrade head`."""
    from webapp import models  # noqa: F401  (đăng ký bảng vào Base.metadata)
    models.Base.metadata.create_all(bind=engine)


def shutdown_session(exception=None):
    """Đóng/nhả phiên cuối mỗi request (gắn vào teardown_appcontext của Flask)."""
    db_session.remove()
