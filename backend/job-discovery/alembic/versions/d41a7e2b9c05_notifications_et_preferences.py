"""Notifications au candidat et préférences d'envoi

Alice rend compte par e-mail : fin de mission, candidature partie, file de
validation, relances, rapport périodique. La table `notifications` en garde
l'historique et sert de verrou anti-doublon (`dedupe_key` unique).

Revision ID: d41a7e2b9c05
Revises: 9b1f2c7d4e10
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd41a7e2b9c05'
down_revision: Union[str, Sequence[str], None] = '9b1f2c7d4e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS : le pont de `main.py` a pu créer la colonne avant.
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS notification_prefs JSONB")
    op.execute(
        "COMMENT ON COLUMN candidates.notification_prefs IS "
        "'{\"enabled\": bool, \"mission_report\": bool, \"application_sent\": bool, "
        "\"awaiting_approval\": bool, \"followups\": bool, "
        "\"digest\": \"off\"|\"daily\"|\"weekly\"}'"
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('kind', sa.Enum(
            'MISSION_REPORT', 'APPLICATION_SENT', 'AWAITING_APPROVAL',
            'FOLLOWUP_DUE', 'DIGEST', 'TEST', name='notificationkind',
        ), nullable=False),
        sa.Column('status', sa.Enum(
            'SENT', 'SIMULATED', 'FAILED', name='notificationstatus',
        ), nullable=False),
        sa.Column('dedupe_key', sa.String(length=200), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedupe_key'),
    )
    op.create_index(op.f('ix_notifications_candidate_id'), 'notifications', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    # Règle du dépôt : toute nouvelle table ferme l'accès PostgREST.
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_candidate_id'), table_name='notifications')
    op.drop_table('notifications')
    op.execute("DROP TYPE IF EXISTS notificationstatus")
    op.execute("DROP TYPE IF EXISTS notificationkind")
    op.drop_column('candidates', 'notification_prefs')
