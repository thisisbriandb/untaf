"""Alice Community : offres relayées par les agrégateurs (Adzuna, Jooble)

Table à part des job_postings : Alice n'y postule pas elle-même, et
l'agrégateur peut exiger le retrait de ses données en fin de partenariat.

Revision ID: d7a3e5c9b2f4
Revises: c4f2a9d7e1b3
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d7a3e5c9b2f4"
down_revision = "c4f2a9d7e1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(300), nullable=False),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "external_id", name="uq_external_listing_source_id"),
    )
    op.create_index("ix_external_listings_source", "external_listings", ["source"])
    op.create_index("ix_external_listings_last_seen_at", "external_listings", ["last_seen_at"])


def downgrade() -> None:
    op.drop_table("external_listings")
