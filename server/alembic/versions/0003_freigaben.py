"""Freigaben je Charakter und Kategorie

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05 12:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = alle Standardwerte (alles sichtbar außer Gold, wie bisher).
    op.add_column("characters", sa.Column("share", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("characters") as batch:
        batch.drop_column("share")
