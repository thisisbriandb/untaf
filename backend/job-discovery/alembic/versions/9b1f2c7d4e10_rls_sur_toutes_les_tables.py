"""RLS sur toutes les tables

Supabase publie le schéma `public` par son API REST (PostgREST). Sans RLS,
quiconque détient la clé publique « anon » du projet lit toutes les tables :
CV, signatures, courriels. Activer le RLS sans aucune politique ferme cette
porte ; le backend n'est pas concerné, il se connecte avec un rôle qui
contourne le RLS (le propriétaire des tables, `postgres` sur Supabase).

Sur un Postgres ordinaire, c'est sans effet : le propriétaire lit toujours.

Toute nouvelle table doit suivre : `ALTER TABLE … ENABLE ROW LEVEL SECURITY`
dans la migration qui la crée.

Revision ID: 9b1f2c7d4e10
Revises: c3eae8fff71a
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9b1f2c7d4e10'
down_revision: Union[str, Sequence[str], None] = 'c3eae8fff71a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (
    "alembic_version",
    "application_dispatches",
    "applications",
    "candidates",
    "companies",
    "job_postings",
    "mission_events",
    "mission_runs",
    "missions",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
