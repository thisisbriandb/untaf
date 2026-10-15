"""La bonne alternance : offres fermées (ni reprise ni envoi autorisés)

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
    op.execute(
        "UPDATE job_postings SET status = 'CLOSED' "
        "WHERE external_id LIKE 'lba:%' AND status = 'ACTIVE'"
    )


def downgrade() -> None:
    # Fermées volontairement : on ne les rouvre pas.
    pass
