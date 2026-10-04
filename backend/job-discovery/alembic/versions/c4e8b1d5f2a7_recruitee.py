"""Recruitee : type d'ATS et canal de candidature

Revision ID: c4e8b1d5f2a7
Revises: b7f2a9c4d1e8
Create Date: 2026-10-04 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4e8b1d5f2a7'
down_revision: Union[str, None] = 'b7f2a9c4d1e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE atstype ADD VALUE IF NOT EXISTS 'RECRUITEE'")
        op.execute("ALTER TYPE applychannel ADD VALUE IF NOT EXISTS 'RECRUITEE_API'")


def downgrade() -> None:
    # Une valeur d'énumération Postgres ne se retire pas ; inutilisée, elle ne gêne pas.
    pass
