"""Abonnement Lemon Squeezy et compteurs d'usage

Revision ID: a3d7e9f1c2b5
Revises: a3d7e9c1f5b8
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'a3d7e9f1c2b5'
down_revision: Union[str, None] = 'a3d7e9c1f5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='lemonsqueezy'),
        sa.Column('provider_id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=True),
        sa.Column('variant_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('renews_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('test_mode', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_subscriptions_candidate_id', 'subscriptions', ['candidate_id'])
    op.create_index('ix_subscriptions_provider_id', 'subscriptions', ['provider_id'], unique=True)

    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('candidates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_usage_events_candidate_kind_at', 'usage_events',
                    ['candidate_id', 'kind', 'created_at'])
    # Règle du projet : toute table derrière RLS (l'API passe par le rôle
    # propriétaire ; l'API REST de Supabase, elle, ne voit rien). email_optouts
    # l'avait oubliée.
    for table in ('subscriptions', 'usage_events', 'email_optouts'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE email_optouts DISABLE ROW LEVEL SECURITY")
    op.drop_table('usage_events')
    op.drop_table('subscriptions')
