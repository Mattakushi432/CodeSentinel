"""add password_hash, drop plan and stripe columns

Revision ID: a1b2c3d4e5f6
Revises: 6d9446e2d15b
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "6d9446e2d15b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("plan")
        batch_op.drop_column("stripe_customer_id")

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("plan")
        batch_op.drop_column("stripe_subscription_id")


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"))
        batch_op.drop_column("password_hash")
