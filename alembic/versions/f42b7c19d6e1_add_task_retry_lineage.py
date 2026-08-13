"""add immutable retry lineage to tasks

Revision ID: f42b7c19d6e1
Revises: d92f5b71ac33
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f42b7c19d6e1"
down_revision: str | None = "d92f5b71ac33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("retry_of_task_id", sa.String(32), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_retry_of",
            "tasks",
            ["retry_of_task_id"],
            ["task_id"],
        )
        batch_op.create_index("ix_tasks_retry_of_task_id", ["retry_of_task_id"])


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("ix_tasks_retry_of_task_id")
        batch_op.drop_constraint("fk_tasks_retry_of", type_="foreignkey")
        batch_op.drop_column("retry_of_task_id")
