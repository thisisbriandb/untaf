"""Relance des inactifs : dernière visite et type de notification

- candidates.last_seen_at : dernière ouverture de l'espace (mise à jour au
  plus toutes les 30 minutes), pour savoir qui ne revient plus.
- notificationkind.REENGAGEMENT : les e-mails de relance (J+2, J+7, J+14).

Revision ID: c4f2a9d7e1b3
Revises: b8e2f4a6c1d3
"""

from alembic import op
import sqlalchemy as sa

revision = "c4f2a9d7e1b3"
down_revision = "b8e2f4a6c1d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    # ADD VALUE ne peut pas tourner dans une transaction sur les anciens
    # Postgres : bloc autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notificationkind ADD VALUE IF NOT EXISTS 'REENGAGEMENT'")


def downgrade() -> None:
    op.drop_column("candidates", "last_seen_at")
    # Une valeur d'enum ne se retire pas sans recréer le type : on la laisse.
