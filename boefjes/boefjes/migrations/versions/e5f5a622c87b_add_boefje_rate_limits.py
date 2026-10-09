"""Add boefje rate limits.

Revision ID: e5f5a622c87b
Revises: fdeaea4481b8
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f5a622c87b"
down_revision = "fdeaea4481b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("boefje", sa.Column("rate_limit_interval", sa.Float(), nullable=True))
    op.add_column("boefje", sa.Column("rate_limit_group", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("boefje", "rate_limit_group")
    op.drop_column("boefje", "rate_limit_interval")
