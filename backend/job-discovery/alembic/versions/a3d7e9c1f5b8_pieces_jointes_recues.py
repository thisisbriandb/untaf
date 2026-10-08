"""Pièces jointes des réponses des recruteurs

Revision ID: a3d7e9c1f5b8
Revises: f2c8d4a6b9e1
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'a3d7e9c1f5b8'
down_revision: Union[str, None] = 'f2c8d4a6b9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'inbound_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('inbound_email_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('inbound_emails.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(length=300), nullable=False),
        sa.Column('mime', sa.String(length=150), nullable=False, server_default='application/octet-stream'),
        sa.Column('size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_inbound_attachments_inbound_email_id', 'inbound_attachments', ['inbound_email_id'])
    # Comme toutes les tables : fermée à l'API publique de Supabase.
    op.execute("ALTER TABLE inbound_attachments ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index('ix_inbound_attachments_inbound_email_id', table_name='inbound_attachments')
    op.drop_table('inbound_attachments')
