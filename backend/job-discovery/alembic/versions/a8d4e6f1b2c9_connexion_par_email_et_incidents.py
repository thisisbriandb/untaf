"""Connexion par e-mail, alertes d'incident, conversations liées à une offre

- login_tokens : liens et codes de connexion (empreintes seules) ;
- notificationkind.INCIDENT : alertes à l'équipe quand une promesse n'est pas
  tenue, distinctes des messages au candidat ;
- conversations.job_posting_id : une conversation peut porter sur une offre.

Revision ID: a8d4e6f1b2c9
Revises: f7c3d9e2a4b6
Create Date: 2026-10-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8d4e6f1b2c9'
down_revision: Union[str, Sequence[str], None] = 'f7c3d9e2a4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index(op.f('ix_login_tokens_email'), 'login_tokens', ['email'], unique=False)
    op.create_index(op.f('ix_login_tokens_created_at'), 'login_tokens', ['created_at'], unique=False)
    op.execute("ALTER TABLE login_tokens ENABLE ROW LEVEL SECURITY")

    # ADD VALUE ne peut pas tourner dans une transaction sur les anciens
    # Postgres : bloc autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notificationkind ADD VALUE IF NOT EXISTS 'INCIDENT'")

    op.add_column('conversations', sa.Column('job_posting_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_conversations_job_posting_id'), 'conversations', ['job_posting_id'], unique=False)
    op.create_foreign_key(
        'conversations_job_posting_id_fkey', 'conversations', 'job_postings',
        ['job_posting_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('conversations_job_posting_id_fkey', 'conversations', type_='foreignkey')
    op.drop_index(op.f('ix_conversations_job_posting_id'), table_name='conversations')
    op.drop_column('conversations', 'job_posting_id')
    # Une valeur d'enum ne se retire pas sans recréer le type : on la laisse.
    op.drop_index(op.f('ix_login_tokens_created_at'), table_name='login_tokens')
    op.drop_index(op.f('ix_login_tokens_email'), table_name='login_tokens')
    op.drop_table('login_tokens')
