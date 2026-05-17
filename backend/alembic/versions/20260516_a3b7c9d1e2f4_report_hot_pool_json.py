"""reports hot_pool_json snapshot

Revision ID: a3b7c9d1e2f4
Revises: f2a18c3d9012
Create Date: 2026-05-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b7c9d1e2f4"
down_revision: Union[str, None] = "f2a18c3d9012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("hot_pool_json", sa.Text(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_column("hot_pool_json")
