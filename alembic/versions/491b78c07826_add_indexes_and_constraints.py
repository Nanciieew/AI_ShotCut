"""add indexes and constraints

Revision ID: 491b78c07826
Revises: ced0365fbb3d
"""

from typing import Sequence, Union

from alembic import op

revision: str = "491b78c07826"
down_revision: Union[str, None] = "ced0365fbb3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_pg() -> bool:
    bind = op.get_bind()
    return bind is not None and bind.engine.name == "postgresql"


def upgrade() -> None:
    # ---- Indexes ----
    op.create_index("idx_tasks_video_status", "tasks", ["video_id", "created_at"])
    op.create_index("idx_tasks_status", "tasks", ["status", "created_at"])
    op.create_index("idx_model_runs_task", "model_runs", ["task_id", "model_name", "status"])
    op.create_index("idx_model_runs_cache", "model_runs", ["cache_key", "status"])
    op.create_index("idx_artifacts_video_type", "artifacts", ["video_id", "artifact_type", "created_at"])
    op.create_index("idx_artifacts_producer", "artifacts", ["producer_run_id"])
    op.create_index("idx_workflow_runs_task", "workflow_runs", ["task_id", "started_at"])

    if _is_pg():
        # ---- I/O unique constraints (PostgreSQL only) ----
        op.create_unique_constraint("uq_model_run_inputs", "model_run_inputs",
                                    ["run_id", "artifact_id", "input_role"])
        op.create_unique_constraint("uq_model_run_outputs", "model_run_outputs",
                                    ["run_id", "artifact_id", "output_role"])
        # ---- Partial unique index on cache_key ----
        op.execute(
            "CREATE UNIQUE INDEX uq_cache_key_active ON model_runs(cache_key) "
            "WHERE status IN ('RUNNING', 'SUCCEEDED') AND cache_key IS NOT NULL"
        )


def downgrade() -> None:
    if _is_pg():
        op.execute("DROP INDEX IF EXISTS uq_cache_key_active")
        op.drop_constraint("uq_model_run_outputs", "model_run_outputs", type_="unique")
        op.drop_constraint("uq_model_run_inputs", "model_run_inputs", type_="unique")

    op.drop_index("idx_workflow_runs_task", table_name="workflow_runs")
    op.drop_index("idx_artifacts_producer", table_name="artifacts")
    op.drop_index("idx_artifacts_video_type", table_name="artifacts")
    op.drop_index("idx_model_runs_cache", table_name="model_runs")
    op.drop_index("idx_model_runs_task", table_name="model_runs")
    op.drop_index("idx_tasks_status", table_name="tasks")
    op.drop_index("idx_tasks_video_status", table_name="tasks")
