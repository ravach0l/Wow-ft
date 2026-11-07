"""Icon-Namen je Zauber-ID (Talent-Icons)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spell_icons",
        sa.Column("spell_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("checked", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("spell_id"),
    )


def downgrade() -> None:
    op.drop_table("spell_icons")
