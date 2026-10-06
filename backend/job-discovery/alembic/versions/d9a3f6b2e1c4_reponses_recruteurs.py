"""Réponses des recruteurs : adresse de réponse par candidat, e-mails reçus

Revision ID: d9a3f6b2e1c4
Revises: c4e8b1d5f2a7
Create Date: 2026-10-05 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'd9a3f6b2e1c4'
down_revision: Union[str, None] = 'c4e8b1d5f2a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('reply_token', sa.String(length=60), nullable=True))
    op.create_index('ix_candidates_reply_token', 'candidates', ['reply_token'], unique=True)
    op.create_table(
        'inbound_emails',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('application_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('applications.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider_id', sa.String(length=300), nullable=False, unique=True),
        sa.Column('from_email', sa.String(length=320), nullable=False),
        sa.Column('from_name', sa.String(length=300), nullable=True),
        sa.Column('to_email', sa.String(length=320), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('text', sa.Text(), nullable=False, server_default=''),
        sa.Column('html', sa.Text(), nullable=True),
        sa.Column('kind', sa.String(length=30), nullable=False, server_default='other'),
        sa.Column('summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('next_step', sa.Text(), nullable=True),
        sa.Column('forwarded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_inbound_emails_candidate_id', 'inbound_emails', ['candidate_id'])
    op.create_index('ix_inbound_emails_application_id', 'inbound_emails', ['application_id'])
    op.create_index('ix_inbound_emails_received_at', 'inbound_emails', ['received_at'])


def downgrade() -> None:
    op.drop_table('inbound_emails')
    op.drop_index('ix_candidates_reply_token', table_name='candidates')
    op.drop_column('candidates', 'reply_token')
