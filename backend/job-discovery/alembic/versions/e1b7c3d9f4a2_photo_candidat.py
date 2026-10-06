"""Photo du candidat, pour ses CV

Revision ID: e1b7c3d9f4a2
Revises: d9a3f6b2e1c4
Create Date: 2026-10-06 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e1b7c3d9f4a2'
down_revision: Union[str, None] = 'd9a3f6b2e1c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('photo', sa.LargeBinary(), nullable=True))
    op.add_column('candidates', sa.Column('photo_mime', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'photo_mime')
    op.drop_column('candidates', 'photo')
