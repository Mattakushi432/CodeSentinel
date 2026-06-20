"""add org llm provider config columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("llm_provider_override", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("llm_model_override", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("llm_api_key_enc", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("llm_api_key_enc")
        batch_op.drop_column("llm_model_override")
        batch_op.drop_column("llm_provider_override")
