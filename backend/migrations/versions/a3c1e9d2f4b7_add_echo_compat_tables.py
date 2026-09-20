"""add echo compatibility tables

Revision ID: a3c1e9d2f4b7
Revises: d77696b64f84
Create Date: 2026-09-19 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3c1e9d2f4b7'
down_revision: Union[str, Sequence[str], None] = 'd77696b64f84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'echo_patient_meta',
        sa.Column('patient_id', sa.String(), nullable=False),
        sa.Column('sex', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('patient_id'),
    )
    op.create_table(
        'echo_referral_meta',
        sa.Column('referral_id', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('specialty', sa.String(), nullable=False),
        sa.Column('subspecialty', sa.String(), nullable=False),
        sa.Column('preferred_distance_miles', sa.Integer(), nullable=False),
        sa.Column('patient_location', sa.String(), nullable=False),
        sa.Column('insurance', sa.String(), nullable=False),
        sa.Column('selected_specialist_id', sa.String(), nullable=True),
        sa.Column('selected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('patient_status', sa.String(), nullable=False),
        sa.Column('patient_responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pipeline_started', sa.Integer(), nullable=False),
        sa.Column('analysis_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('referral_id'),
    )


def downgrade() -> None:
    op.drop_table('echo_referral_meta')
    op.drop_table('echo_patient_meta')
