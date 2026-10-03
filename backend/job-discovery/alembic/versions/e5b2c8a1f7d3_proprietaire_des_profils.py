"""Propriétaire des profils (Supabase Auth)

Un profil n'est plus accessible qu'à l'utilisateur authentifié auquel il est
rattaché. Les profils existants restent sans propriétaire jusqu'à la première
connexion avec la même adresse e-mail.

Revision ID: e5b2c8a1f7d3
Revises: d41a7e2b9c05
Create Date: 2026-10-03 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5b2c8a1f7d3'
down_revision: Union[str, Sequence[str], None] = 'd41a7e2b9c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('auth_user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_candidates_auth_user_id'), 'candidates', ['auth_user_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_candidates_auth_user_id'), table_name='candidates')
    op.drop_column('candidates', 'auth_user_id')
