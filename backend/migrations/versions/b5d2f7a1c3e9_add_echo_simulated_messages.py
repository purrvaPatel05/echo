"""add echo simulated messages

Revision ID: b5d2f7a1c3e9
Revises: a3c1e9d2f4b7
Create Date: 2026-09-20 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5d2f7a1c3e9'
down_revision: Union[str, Sequence[str], None] = 'a3c1e9d2f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'echo_simulated_messages',
        sa.Column('message_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('message_id'),
    )


def downgrade() -> None:
    op.drop_table('echo_simulated_messages')
