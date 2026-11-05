"""Add employee tax elections, declarations, and audit history."""
from alembic import op
import sqlalchemy as sa

revision = "m8f41c2b7e90"
down_revision = "l7e4a2c9d610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_tax_elections",
        sa.Column("election_id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("financial_year", sa.String(12), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("election_date", sa.Date(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.CheckConstraint("approval_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_tax_election_status"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_tax_election_dates"),
    )
    op.create_index("ix_employee_tax_elections_employee_id", "employee_tax_elections", ["employee_id"])
    op.create_index("ix_employee_tax_elections_financial_year", "employee_tax_elections", ["financial_year"])
    op.create_index("ix_employee_tax_elections_effective_from", "employee_tax_elections", ["effective_from"])
    op.create_index("ix_employee_tax_elections_approval_status", "employee_tax_elections", ["approval_status"])
    op.create_index("ix_tax_elections_employee_period", "employee_tax_elections",
                    ["employee_id", "financial_year", "effective_from"])

    op.create_table(
        "employee_tax_declarations",
        sa.Column("declaration_id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("financial_year", sa.String(12), nullable=False),
        sa.Column("deduction_code", sa.String(60), nullable=False),
        sa.Column("declared_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("supporting_document_reference", sa.String(500), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.CheckConstraint("declared_amount >= 0", name="ck_tax_declaration_amount"),
        sa.CheckConstraint("approval_status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_tax_declaration_status"),
    )
    op.create_index("ix_employee_tax_declarations_employee_id", "employee_tax_declarations", ["employee_id"])
    op.create_index("ix_employee_tax_declarations_financial_year", "employee_tax_declarations", ["financial_year"])
    op.create_index("ix_employee_tax_declarations_approval_status", "employee_tax_declarations", ["approval_status"])
    op.create_index("ix_tax_declarations_employee_fy", "employee_tax_declarations", ["employee_id", "financial_year"])

    op.create_table(
        "employee_tax_audit_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("employee_id", sa.String(20), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_employee_tax_audit_events_employee_id", "employee_tax_audit_events", ["employee_id"])
    op.create_index("ix_employee_tax_audit_events_actor_user_id", "employee_tax_audit_events", ["actor_user_id"])
    op.create_index("ix_employee_tax_audit_events_entity_id", "employee_tax_audit_events", ["entity_id"])


def downgrade() -> None:
    op.drop_table("employee_tax_audit_events")
    op.drop_table("employee_tax_declarations")
    op.drop_table("employee_tax_elections")
