"""Kopplung von Uploadern (Gerätecode und Code fürs Spiel)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-06 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pairings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("user_code", sa.String(length=16), nullable=False),
        sa.Column("device_hash", sa.String(length=64), nullable=True),
        sa.Column("device_name", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("expires", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_hash"),
        sa.UniqueConstraint("user_code"),
    )
    with op.batch_alter_table("pairings") as batch:
        batch.create_index("ix_pairings_expires", ["expires"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("pairings") as batch:
        batch.drop_index("ix_pairings_expires")
    op.drop_table("pairings")
