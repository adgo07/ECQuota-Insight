"""Add standard lifecycle metadata."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("standards", sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="active"))
    op.add_column("standards", sa.Column("obsolete_date", sa.Date(), nullable=True))
    op.add_column("standards", sa.Column("replaced_by_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("standards", sa.Column("supersedes_json", sa.Text(), nullable=False, server_default="[]"))

def downgrade() -> None:
    op.drop_column("standards", "supersedes_json")
    op.drop_column("standards", "replaced_by_json")
    op.drop_column("standards", "obsolete_date")
    op.drop_column("standards", "lifecycle_status")
