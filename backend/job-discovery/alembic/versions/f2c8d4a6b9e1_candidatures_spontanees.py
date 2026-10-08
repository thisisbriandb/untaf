"""Candidatures spontanées : contact publié des entreprises, désinscriptions

Revision ID: f2c8d4a6b9e1
Revises: e1b7c3d9f4a2
Create Date: 2026-10-08 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'f2c8d4a6b9e1'
down_revision: Union[str, None] = 'e1b7c3d9f4a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('website', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('careers_email', sa.String(length=320), nullable=True))
    op.add_column('companies', sa.Column('careers_email_source', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('careers_email_kind', sa.String(length=20), nullable=True))
    op.add_column('companies', sa.Column('about', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('contact_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_companies_siren', 'companies', ['siren'])
    op.create_table(
        'email_optouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('value', sa.String(length=320), nullable=False, unique=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_optouts_value', 'email_optouts', ['value'], unique=True)


def downgrade() -> None:
    op.drop_table('email_optouts')
    op.drop_index('ix_companies_siren', table_name='companies')
    for col in ('contact_checked_at', 'about', 'careers_email_kind', 'careers_email_source',
                'careers_email', 'website'):
        op.drop_column('companies', col)
