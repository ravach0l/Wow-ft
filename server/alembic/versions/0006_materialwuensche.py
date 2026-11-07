"""Material-Wünsche je Gruppe

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_name", sa.String(length=150), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("expires", sa.Integer(), nullable=False),
        sa.Column("done", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("material_requests") as batch:
        batch.create_index("ix_material_requests_group_id", ["group_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("material_requests") as batch:
        batch.drop_index("ix_material_requests_group_id")
    op.drop_table("material_requests")
