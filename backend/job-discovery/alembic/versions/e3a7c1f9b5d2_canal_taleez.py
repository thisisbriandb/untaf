"""Taleez : canal de candidature

Revision ID: e3a7c1f9b5d2
Revises: d7a3e5c9b2f4
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e3a7c1f9b5d2'
down_revision: Union[str, None] = 'd7a3e5c9b2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE applychannel ADD VALUE IF NOT EXISTS 'TALEEZ_API'")


def downgrade() -> None:
    # Une valeur d'énumération Postgres ne se retire pas ; inutilisée, elle ne gêne pas.
    pass
