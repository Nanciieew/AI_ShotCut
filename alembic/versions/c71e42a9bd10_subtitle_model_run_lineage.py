"""add subtitle ModelRun lineage

Revision ID: c71e42a9bd10
Revises: a83f7c1d2e40
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c71e42a9bd10"
down_revision: str | None = "a83f7c1d2e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subtitle_segments") as batch_op:
        batch_op.add_column(sa.Column("producer_run_id", sa.String(32), nullable=True))
        batch_op.create_foreign_key(
            "fk_subtitles_producer_run",
            "model_runs",
            ["producer_run_id"],
            ["run_id"],
        )
    op.create_index(
        "idx_subtitles_video_run_time",
        "subtitle_segments",
        ["video_id", "producer_run_id", "start_ms"],
    )


def downgrade() -> None:
    op.drop_index("idx_subtitles_video_run_time", table_name="subtitle_segments")
    with op.batch_alter_table("subtitle_segments") as batch_op:
        batch_op.drop_constraint("fk_subtitles_producer_run", type_="foreignkey")
        batch_op.drop_column("producer_run_id")
