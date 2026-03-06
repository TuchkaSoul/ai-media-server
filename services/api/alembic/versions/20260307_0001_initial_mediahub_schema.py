"""initial mediahub schema

Revision ID: 20260307_0001
Revises:
Create Date: 2026-03-07 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260307_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mediahub")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("email", sa.String(length=256), nullable=True, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="mediahub",
    )

    op.create_table(
        "cameras",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="mediahub",
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("camera_id", sa.BigInteger(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(10, 3), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["mediahub.cameras.id"], ondelete="SET NULL"),
        schema="mediahub",
    )

    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("video_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["video_id"], ["mediahub.videos.id"], ondelete="CASCADE"),
        schema="mediahub",
    )

    op.create_table(
        "detections",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("timestamp_seconds", sa.Numeric(10, 3), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["mediahub.analysis_tasks.id"], ondelete="CASCADE"),
        schema="mediahub",
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["task_id"], ["mediahub.analysis_tasks.id"], ondelete="CASCADE"),
        schema="mediahub",
    )


def downgrade() -> None:
    op.drop_table("alerts", schema="mediahub")
    op.drop_table("detections", schema="mediahub")
    op.drop_table("analysis_tasks", schema="mediahub")
    op.drop_table("videos", schema="mediahub")
    op.drop_table("cameras", schema="mediahub")
    op.drop_table("users", schema="mediahub")
