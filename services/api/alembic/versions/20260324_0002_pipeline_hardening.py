"""pipeline hardening constraints and indexes

Revision ID: 20260324_0002
Revises: 20260307_0001
Create Date: 2026-03-24 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260324_0002"
down_revision: Union[str, None] = "20260307_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_video_segments_camera_segment_index",
        "video_segments",
        ["camera_id", "segment_index"],
        schema="mediahub",
    )
    op.create_index("ix_frame_metadata_segment_id", "frame_metadata", ["segment_id"], schema="mediahub")
    op.create_index("ix_frame_metadata_captured_at", "frame_metadata", ["captured_at"], schema="mediahub")
    op.create_index("ix_events_segment_created", "events", ["segment_id", "created_at"], schema="mediahub")

    op.alter_column(
        "frame_metadata",
        "attributes",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )
    op.alter_column(
        "detections",
        "attributes",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )
    op.alter_column(
        "events",
        "payload",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "events",
        "payload",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'"),
        existing_nullable=False,
    )
    op.alter_column(
        "detections",
        "attributes",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'"),
        existing_nullable=False,
    )
    op.alter_column(
        "frame_metadata",
        "attributes",
        schema="mediahub",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'"),
        existing_nullable=False,
    )

    op.drop_index("ix_events_segment_created", table_name="events", schema="mediahub")
    op.drop_index("ix_frame_metadata_captured_at", table_name="frame_metadata", schema="mediahub")
    op.drop_index("ix_frame_metadata_segment_id", table_name="frame_metadata", schema="mediahub")
    op.drop_constraint("uq_video_segments_camera_segment_index", "video_segments", schema="mediahub", type_="unique")
