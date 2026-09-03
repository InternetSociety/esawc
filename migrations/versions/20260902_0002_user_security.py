"""Add persistent-token and password-recovery constraints."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_0002"
down_revision: str | None = "20260902_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    user_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "idx_users_email" in user_indexes:
        op.drop_index("idx_users_email", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "email", existing_type=sa.Text(), type_=sa.String(length=320), nullable=False
        )
        batch_op.alter_column(
            "password_hash", existing_type=sa.Text(), type_=sa.String(), nullable=False
        )
        batch_op.alter_column(
            "bearer_token", existing_type=sa.Text(), type_=sa.String(), nullable=True
        )
        batch_op.add_column(sa.Column("reset_token_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_bearer_token", "users", ["bearer_token"], unique=True)
    op.create_index("ix_users_reset_token_hash", "users", ["reset_token_hash"])
    op.drop_index("idx_cached_tiles_expires_at", table_name="cached_tiles")
    with op.batch_alter_table("cached_tiles") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("tile_id", existing_type=sa.Text(), type_=sa.String(), nullable=False)
        batch_op.alter_column(
            "file_path", existing_type=sa.Text(), type_=sa.String(), nullable=False
        )
    op.create_index("ix_cached_tiles_expires_at", "cached_tiles", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_cached_tiles_expires_at", table_name="cached_tiles")
    with op.batch_alter_table("cached_tiles") as batch_op:
        batch_op.alter_column(
            "file_path", existing_type=sa.String(), type_=sa.Text(), nullable=False
        )
        batch_op.alter_column("tile_id", existing_type=sa.String(), type_=sa.Text(), nullable=False)
        batch_op.alter_column("id", existing_type=sa.Integer(), nullable=True)
    op.create_index("idx_cached_tiles_expires_at", "cached_tiles", ["expires_at"])
    op.drop_index("ix_users_reset_token_hash", table_name="users")
    op.drop_index("ix_users_bearer_token", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("reset_token_expires_at")
        batch_op.drop_column("reset_token_hash")
        batch_op.alter_column(
            "bearer_token", existing_type=sa.String(), type_=sa.Text(), nullable=True
        )
        batch_op.alter_column(
            "password_hash", existing_type=sa.String(), type_=sa.Text(), nullable=False
        )
        batch_op.alter_column(
            "email", existing_type=sa.String(length=320), type_=sa.Text(), nullable=False
        )
        batch_op.alter_column("id", existing_type=sa.Integer(), nullable=True)
    op.create_index("idx_users_email", "users", ["email"])
