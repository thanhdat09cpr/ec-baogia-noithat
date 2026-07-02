"""
models.py — Mô hình dữ liệu đa người dùng (SQLAlchemy 2.0).

DB chỉ giữ METADATA + quyền sở hữu. Cấu hình nghiệp vụ (profit/scope/phòng/preliminaries)
VẪN nằm ở `cau-hinh.json` trong thư mục dự án (tái dùng `lib_boq.load_config` không đổi).

- User        : người dùng (đăng nhập Google ở pha 3; pha 2 seed 1 user hệ thống).
- Project      : 1 dự án báo giá; `dir_name` = tên thư mục trên đĩa (mới=uuid, legacy=tên cũ).
- TakeoffJob  : vừa là job bóc AI (pha 4) vừa là usage-log token để ước tính chi phí.

Đường dẫn thư mục dự án đọc từ cột `dir_name` (F2 red-team) — KHÔNG suy thuần từ id →
tránh 2 dự án legacy (68-Tho-Nhuom, ROX2) báo FileNotFound.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Naive UTC ở MỌI nơi (cột DateTime không timezone) → so sánh SQLite/Postgres nhất quán,
    # tránh "can't compare offset-naive and offset-aware" trong reaper (pha 4).
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="user")       # user | admin
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | approved | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    ten: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), default="")
    # F2: tên thư mục thực trên đĩa. Dự án mới = uuid; legacy = tên thư mục cũ.
    dir_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dia_diem: Mapped[str] = mapped_column(String(255), default="")
    hang_muc: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|takeoff|awaiting_ncc|quoted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    owner: Mapped["User"] = relationship(back_populates="projects")
    jobs: Mapped[list["TakeoffJob"]] = relationship(back_populates="project")


class TakeoffJob(Base):
    __tablename__ = "takeoff_jobs"

    # N1: id = UUID (không int tuần tự → tránh đoán/IDOR).
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    room_ma: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|done|error
    model: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="jobs")

    # F7/C1: "không 2 job ACTIVE cùng phòng" được bảo đảm ở tầng app bằng jobs.active_job()
    # (chặn pending/running). KHÔNG dùng UNIQUE(project_id,room_ma,status) — vì done/error nhiều
    # lần cho cùng phòng (bóc lại) sẽ đụng ràng buộc. Postgres partial-unique là hardening sau.
