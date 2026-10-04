"""Conversations avec Alice conservées côté serveur

L'historique ne vit plus dans le navigateur : il suit l'utilisateur sur tous
ses appareils, et Alice relit le fil depuis la base.

Revision ID: f7c3d9e2a4b6
Revises: e5b2c8a1f7d3
Create Date: 2026-10-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f7c3d9e2a4b6'
down_revision: Union[str, Sequence[str], None] = 'e5b2c8a1f7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversations_candidate_id'), 'conversations', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_conversations_updated_at'), 'conversations', ['updated_at'], unique=False)
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('ui_blocks', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversation_messages_conversation_id'), 'conversation_messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_conversation_messages_created_at'), 'conversation_messages', ['created_at'], unique=False)
    # Règle du dépôt : toute nouvelle table ferme l'accès PostgREST.
    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f('ix_conversation_messages_created_at'), table_name='conversation_messages')
    op.drop_index(op.f('ix_conversation_messages_conversation_id'), table_name='conversation_messages')
    op.drop_table('conversation_messages')
    op.drop_index(op.f('ix_conversations_updated_at'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_candidate_id'), table_name='conversations')
    op.drop_table('conversations')
