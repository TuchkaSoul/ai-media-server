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
        "cameras",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="idle"),
        sa.Column("fps", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("frame_width", sa.Integer(), nullable=False, server_default="1280"),
        sa.Column("frame_height", sa.Integer(), nullable=False, server_default="720"),
        sa.Column("segment_duration_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="mediahub",
    )

    op.create_table(
        "video_segments",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("camera_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("metadata_path", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["mediahub.cameras.id"], ondelete="CASCADE"),
        schema="mediahub",
    )
    op.create_index("ix_video_segments_camera_started", "video_segments", ["camera_id", "started_at"], schema="mediahub")

    op.create_table(
        "frame_metadata",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("camera_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_id", sa.BigInteger(), nullable=False),
        sa.Column("frame_number", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("ingest_latency_ms", sa.Numeric(10, 3), nullable=True),
        sa.Column("has_detections", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["mediahub.cameras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["mediahub.video_segments.id"], ondelete="CASCADE"),
        schema="mediahub",
    )
    op.create_index("ix_frame_metadata_segment_captured", "frame_metadata", ["segment_id", "captured_at"], schema="mediahub")
    op.create_index("ix_frame_metadata_camera_captured", "frame_metadata", ["camera_id", "captured_at"], schema="mediahub")

    op.create_table(
        "detections",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("frame_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("track_id", sa.String(length=128), nullable=True),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["frame_id"], ["mediahub.frame_metadata.id"], ondelete="CASCADE"),
        schema="mediahub",
    )
    op.create_index("ix_detections_frame_label", "detections", ["frame_id", "label"], schema="mediahub")

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("camera_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_id", sa.BigInteger(), nullable=True),
        sa.Column("frame_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("importance_score", sa.Numeric(6, 5), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["camera_id"], ["mediahub.cameras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["mediahub.video_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["frame_id"], ["mediahub.frame_metadata.id"], ondelete="SET NULL"),
        schema="mediahub",
    )
    op.create_index("ix_events_camera_created", "events", ["camera_id", "created_at"], schema="mediahub")
    op.create_index("ix_events_type_created", "events", ["event_type", "created_at"], schema="mediahub")


def downgrade() -> None:
    op.drop_index("ix_events_type_created", table_name="events", schema="mediahub")
    op.drop_index("ix_events_camera_created", table_name="events", schema="mediahub")
    op.drop_table("events", schema="mediahub")
    op.drop_index("ix_detections_frame_label", table_name="detections", schema="mediahub")
    op.drop_table("detections", schema="mediahub")
    op.drop_index("ix_frame_metadata_camera_captured", table_name="frame_metadata", schema="mediahub")
    op.drop_index("ix_frame_metadata_segment_captured", table_name="frame_metadata", schema="mediahub")
    op.drop_table("frame_metadata", schema="mediahub")
    op.drop_index("ix_video_segments_camera_started", table_name="video_segments", schema="mediahub")
    op.drop_table("video_segments", schema="mediahub")
    op.drop_table("cameras", schema="mediahub")
