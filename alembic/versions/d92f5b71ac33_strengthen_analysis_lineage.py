"""strengthen analysis lineage and persist candidate boundaries

Revision ID: d92f5b71ac33
Revises: c71e42a9bd10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d92f5b71ac33"
down_revision: str | None = "c71e42a9bd10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.create_foreign_key(
            "fk_tasks_workflow_run",
            "workflow_runs",
            ["workflow_run_id"],
            ["workflow_run_id"],
        )

    with op.batch_alter_table("model_runs") as batch_op:
        batch_op.create_foreign_key(
            "fk_model_runs_video",
            "videos",
            ["video_id"],
            ["video_id"],
        )

    with op.batch_alter_table("shots") as batch_op:
        batch_op.add_column(sa.Column("producer_run_id", sa.String(32), nullable=True))
        batch_op.create_foreign_key(
            "fk_shots_producer_run",
            "model_runs",
            ["producer_run_id"],
            ["run_id"],
        )
        batch_op.create_unique_constraint(
            "uq_shots_run_index", ["producer_run_id", "index"]
        )
    op.create_index(
        "idx_shots_video_run_index",
        "shots",
        ["video_id", "producer_run_id", "index"],
    )

    op.create_table(
        "candidate_boundaries",
        sa.Column("candidate_id", sa.String(32), nullable=False),
        sa.Column("video_id", sa.String(32), nullable=False),
        sa.Column("producer_run_id", sa.String(32), nullable=False),
        sa.Column("shot_id", sa.String(32), nullable=False),
        sa.Column("scene_id", sa.String(32), nullable=True),
        sa.Column("boundary_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("scene_score", sa.Float(), nullable=False),
        sa.Column("location_continuity", sa.Float(), nullable=True),
        sa.Column("character_continuity", sa.Float(), nullable=True),
        sa.Column("subtitle_continuity", sa.Float(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("selection_rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["producer_run_id"], ["model_runs.run_id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.scene_id"]),
        sa.ForeignKeyConstraint(["shot_id"], ["shots.shot_id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.video_id"]),
        sa.PrimaryKeyConstraint("candidate_id"),
        sa.UniqueConstraint(
            "producer_run_id", "boundary_index", name="uq_boundary_run_index"
        ),
    )
    op.create_index(
        "idx_boundaries_video_run_selected",
        "candidate_boundaries",
        ["video_id", "producer_run_id", "selected", "boundary_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_boundaries_video_run_selected", table_name="candidate_boundaries"
    )
    op.drop_table("candidate_boundaries")

    op.drop_index("idx_shots_video_run_index", table_name="shots")
    with op.batch_alter_table("shots") as batch_op:
        batch_op.drop_constraint("uq_shots_run_index", type_="unique")
        batch_op.drop_constraint("fk_shots_producer_run", type_="foreignkey")
        batch_op.drop_column("producer_run_id")

    with op.batch_alter_table("model_runs") as batch_op:
        batch_op.drop_constraint("fk_model_runs_video", type_="foreignkey")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_workflow_run", type_="foreignkey")
