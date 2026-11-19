"""Add indemnification flag to organisation

Revision ID: a1b2c3d4e5f6
Revises: fdeaea4481b8
Create Date: 2026-09-14 22:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fdeaea4481b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organisation", sa.Column("indemnification", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("organisation", "indemnification")
