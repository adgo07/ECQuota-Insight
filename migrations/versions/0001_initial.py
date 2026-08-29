"""Initial offline database schema.

Revision ID: 0001
Revises: None
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "standards",
        sa.Column("row_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("standard_id", sa.String(128), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_file", sa.String(512), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("package_id", sa.String(128), nullable=True),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ux_standards_id_version", "standards", ["standard_id", "version"], unique=True)
    op.create_index("ix_standards_number", "standards", ["number"])
    op.create_table(
        "evaluations",
        sa.Column("evaluation_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("standard_id", sa.String(128), nullable=False),
        sa.Column("standard_number", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("organization_name", sa.String(512), nullable=True),
        sa.Column("project_name", sa.String(512), nullable=True),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("rule_snapshot_json", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_evaluations_created", "evaluations", ["created_at"])
    op.create_index("ix_evaluations_standard", "evaluations", ["standard_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(128), nullable=False),
        sa.Column("entity_id", sa.String(256), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False),
    )
    op.create_table(
        "standard_packages",
        sa.Column("package_id", sa.String(128), primary_key=True),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("package_sha256", sa.String(64), nullable=False),
    )
    op.create_table(
        "import_batches",
        sa.Column("import_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_file", sa.String(1024), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("validation_json", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("import_batches")
    op.drop_table("standard_packages")
    op.drop_table("audit_log")
    op.drop_index("ix_evaluations_standard", table_name="evaluations")
    op.drop_index("ix_evaluations_created", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_standards_number", table_name="standards")
    op.drop_index("ux_standards_id_version", table_name="standards")
    op.drop_table("standards")
