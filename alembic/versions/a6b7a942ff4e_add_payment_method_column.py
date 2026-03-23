"""add payment_method column

Revision ID: a6b7a942ff4e
Revises: 
Create Date: 2026-03-19 20:21:17.927146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b7a942ff4e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. We tell Alembic to add a column named 'payment_method' to the 'transactions' table
    # We set server_default="Unknown" so our 1,000 existing rows don't crash from empty data!
    op.add_column(
        'transactions',
        sa.Column('payment_method', sa.String(), server_default='Unknown', nullable=False)
    )

def downgrade() -> None:
    # 2. The Undo Button: We tell Alembic how to delete the column
    op.drop_column('transactions', 'payment_method')
