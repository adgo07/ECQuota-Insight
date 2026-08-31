"""Add stable standard-family and rule-revision identity."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("standards", sa.Column("standard_family_id", sa.String(128), nullable=True))
    op.add_column("standards", sa.Column("rule_revision", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE standards SET standard_family_id = "
        "CASE WHEN instr(number, '-') > 0 THEN substr(number, 1, instr(number, '-') - 1) "
        "ELSE number END"
    )
    op.execute("UPDATE standards SET rule_revision = 1 WHERE rule_revision IS NULL")
    with op.batch_alter_table("standards") as batch:
        batch.alter_column(
            "standard_family_id",
            existing_type=sa.String(128),
            nullable=False,
        )
        batch.alter_column(
            "rule_revision",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.drop_index("ux_standards_id_version")
        batch.create_index(
            "ux_standards_id_version_revision",
            ["standard_id", "version", "rule_revision"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("standards") as batch:
        batch.drop_index("ux_standards_id_version_revision")
        batch.drop_column("rule_revision")
        batch.drop_column("standard_family_id")
        batch.create_index(
            "ux_standards_id_version",
            ["standard_id", "version"],
            unique=True,
        )
