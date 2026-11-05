"""Grundschema

Revision ID: 0001
Revises:
Create Date: 2026-11-05 08:48:36.071269
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("invite_code", sa.String(length=64), nullable=False),
        sa.Column("discord_webhook", sa.String(length=300), nullable=True),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auth_sub", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auth_sub"),
    )
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("guid", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("realm", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=8), nullable=True),
        sa.Column("class", sa.String(length=32), nullable=True),
        sa.Column("race", sa.String(length=32), nullable=True),
        sa.Column("faction", sa.String(length=16), nullable=True),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("gold_visible", sa.Boolean(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("last_upload", sa.Integer(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guid"),
    )
    with op.batch_alter_table("characters", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_characters_user_id"), ["user_id"], unique=False)

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("joined", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "user_id"),
    )
    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("last_used", sa.Integer(), nullable=True),
        sa.Column("revoked", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash"),
    )
    with op.batch_alter_table("tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tokens_user_id"), ["user_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "ts", "type", "key"),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_events_ts"), ["ts"], unique=False)

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "ts"),
    )
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_photos_character_id"), ["character_id"], unique=False)

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False),
        sa.Column("xp_max", sa.Integer(), nullable=False),
        sa.Column("rested", sa.Integer(), nullable=False),
        sa.Column("played_total", sa.Integer(), nullable=True),
        sa.Column("played_level", sa.Integer(), nullable=True),
        sa.Column("zone", sa.String(length=100), nullable=True),
        sa.Column("gold", sa.Integer(), nullable=True),
        sa.Column("extras", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "ts"),
    )


def downgrade() -> None:
    op.drop_table("snapshots")
    with op.batch_alter_table("photos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_photos_character_id"))

    op.drop_table("photos")
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_events_ts"))

    op.drop_table("events")
    with op.batch_alter_table("tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tokens_user_id"))

    op.drop_table("tokens")
    op.drop_table("group_members")
    with op.batch_alter_table("characters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_characters_user_id"))

    op.drop_table("characters")
    op.drop_table("users")
    op.drop_table("groups")
