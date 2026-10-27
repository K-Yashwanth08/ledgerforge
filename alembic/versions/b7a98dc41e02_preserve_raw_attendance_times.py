"""Preserve source attendance time strings, including extended hours.

Revision ID: b7a98dc41e02
Revises: a6d31c42f901
"""
from alembic import op
import sqlalchemy as sa

revision = "b7a98dc41e02"
down_revision = "a6d31c42f901"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.batch_alter_table("attendance_records") as batch:
        batch.alter_column("check_in", existing_type=sa.Time(), type_=sa.String(12), existing_nullable=True)
        batch.alter_column("check_out", existing_type=sa.Time(), type_=sa.String(12), existing_nullable=True)

def downgrade() -> None:
    raise RuntimeError("Downgrade would lose valid extended-hour attendance values such as 24:25")
