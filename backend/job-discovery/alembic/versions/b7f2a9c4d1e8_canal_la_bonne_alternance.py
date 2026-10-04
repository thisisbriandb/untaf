"""canal de candidature La bonne alternance

Revision ID: b7f2a9c4d1e8
Revises: a8d4e6f1b2c9
Create Date: 2026-10-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b7f2a9c4d1e8'
down_revision: Union[str, None] = 'a8d4e6f1b2c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE ne peut pas tourner dans une transaction sur les anciens
    # Postgres : bloc autocommit.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE applychannel ADD VALUE IF NOT EXISTS 'LBA_API'")


def downgrade() -> None:
    # Postgres ne sait pas retirer une valeur d'un type énuméré ; elle reste,
    # inutilisée, sans gêner.
    pass
