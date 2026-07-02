"""khởi tạo 3 bảng: users, projects, takeoff_jobs

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("google_sub", sa.String(255), nullable=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # Inline UNIQUE (SQLite không hỗ trợ ALTER thêm constraint); NULL google_sub cho phép trùng.
        sa.UniqueConstraint("google_sub", name="uq_users_google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ten", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, server_default=""),
        sa.Column("dir_name", sa.String(255), nullable=False),
        sa.Column("dia_diem", sa.String(255), nullable=False, server_default=""),
        sa.Column("hang_muc", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    op.create_table(
        "takeoff_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("room_ma", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("model", sa.String(64), nullable=False, server_default=""),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_takeoff_jobs_project_id", "takeoff_jobs", ["project_id"])
    op.create_index("ix_takeoff_jobs_user_id", "takeoff_jobs", ["user_id"])
    # F7/C1: chặn 2 job ACTIVE cùng phòng bằng partial-unique CHỈ trên Postgres (pending/running).
    # SQLite không hỗ trợ partial index qua Alembic op → dựa guard app jobs.active_job().
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_job_active_room", "takeoff_jobs", ["project_id", "room_ma"], unique=True,
            postgresql_where=sa.text("status IN ('pending','running')"))


def downgrade() -> None:
    op.drop_table("takeoff_jobs")
    op.drop_table("projects")
    op.drop_table("users")
