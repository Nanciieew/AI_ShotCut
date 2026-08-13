"""add Scene producer lineage and evidence uniqueness

Revision ID: a83f7c1d2e40
Revises: 491b78c07826
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a83f7c1d2e40"
down_revision: str | None = "491b78c07826"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable preserves any legacy Scene rows that predate ModelRun lineage.
    # Every newly generated Scene supplies producer_run_id.
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.add_column(
            sa.Column("producer_run_id", sa.String(32), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_scenes_producer_run",
            "model_runs",
            ["producer_run_id"],
            ["run_id"],
        )
        batch_op.create_unique_constraint(
            "uq_scenes_run_index", ["producer_run_id", "index"]
        )
    op.create_index(
        "idx_scenes_video_run_index",
        "scenes",
        ["video_id", "producer_run_id", "index"],
    )
    with op.batch_alter_table("scene_evidence") as batch_op:
        batch_op.create_unique_constraint("uq_scene_evidence_scene", ["scene_id"])


def downgrade() -> None:
    with op.batch_alter_table("scene_evidence") as batch_op:
        batch_op.drop_constraint("uq_scene_evidence_scene", type_="unique")
    op.drop_index("idx_scenes_video_run_index", table_name="scenes")
    with op.batch_alter_table("scenes") as batch_op:
        batch_op.drop_constraint("uq_scenes_run_index", type_="unique")
        batch_op.drop_constraint("fk_scenes_producer_run", type_="foreignkey")
        batch_op.drop_column("producer_run_id")
