"""Signature par téléphone (QR code) : sessions de signature

Revision ID: b8e2f4a6c1d3
Revises: a3d7e9f1c2b5
Create Date: 2026-10-09 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'b8e2f4a6c1d3'
down_revision: Union[str, None] = 'a3d7e9f1c2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'signature_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('image', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_signature_sessions_token', 'signature_sessions', ['token'], unique=True)
    op.execute("ALTER TABLE signature_sessions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table('signature_sessions')
