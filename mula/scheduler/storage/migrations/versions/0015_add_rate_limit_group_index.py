"""Add index on rate_limit_group JSONB path for pop query performance

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-03 09:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_tasks_rate_limit_group",
        "tasks",
        [
            "scheduler_id",
            sa.literal_column("(data -> 'boefje' ->> 'rate_limit_group')"),
        ],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_tasks_rate_limit_group", table_name="tasks")
