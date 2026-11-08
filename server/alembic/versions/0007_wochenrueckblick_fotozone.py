"""Wochenrückblick je Gruppe, Zone zu Fotos

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("groups") as batch:
        batch.add_column(sa.Column("weekly_report", sa.Boolean(), nullable=False, server_default="1"))
    with op.batch_alter_table("photos") as batch:
        batch.add_column(sa.Column("zone", sa.String(length=150), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("photos") as batch:
        batch.drop_column("zone")
    with op.batch_alter_table("groups") as batch:
        batch.drop_column("weekly_report")
