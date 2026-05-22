"""add_uuid_to_payroll_reconciliation_issues

Revision ID: 8b688c22718e
Revises: a52b38ada3ba
Create Date: 2026-05-22 18:00:00.000000

"""
from typing import Sequence, Union
import uuid as _uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import CHAR


# revision identifiers, used by Alembic.
revision: str = '8b688c22718e'
down_revision: Union[str, Sequence[str], None] = 'a52b38ada3ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add nullable VARCHAR column with NO server_default
    op.add_column(
        'payroll_reconciliation_issues',
        sa.Column('uuid', CHAR(36), nullable=True)
    )

    # Step 2: Populate existing rows with Python-generated UUIDs via a batch UPDATE
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM payroll_reconciliation_issues WHERE uuid IS NULL")).fetchall()
    for (row_id,) in rows:
        new_uuid = str(_uuid.uuid4())
        conn.execute(
            sa.text("UPDATE payroll_reconciliation_issues SET uuid = :u WHERE id = :id"),
            {"u": new_uuid, "id": row_id}
        )

    # Step 3: Tighten to NOT NULL
    op.alter_column('payroll_reconciliation_issues', 'uuid', nullable=False, existing_type=CHAR(36))

    # Step 4: Add unique index
    op.create_index(op.f('ix_payroll_reconciliation_issues_uuid'), 'payroll_reconciliation_issues', ['uuid'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_payroll_reconciliation_issues_uuid'), table_name='payroll_reconciliation_issues')
    op.drop_column('payroll_reconciliation_issues', 'uuid')
