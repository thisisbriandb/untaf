"""La bonne alternance : plus d'envoi par l'API, les offres passent à l'extension

Revision ID: f4b8d2a6c3e1
Revises: e3a7c1f9b5d2
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f4b8d2a6c3e1'
down_revision: Union[str, None] = 'e3a7c1f9b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Les offres restent : le candidat postule sur le site avec l'extension.
    op.execute(
        "UPDATE job_postings SET apply_channel = 'WEB_FORM', apply_complexity = 'MEDIUM' "
        "WHERE external_id LIKE 'lba:%' AND apply_channel = 'LBA_API'"
    )


def downgrade() -> None:
    pass
