"""add_uuid_to_bank_file_records

Revision ID: a52b38ada3ba
Revises: 30046b120e38
Create Date: 2026-05-22 01:34:22.327859

"""
from typing import Sequence, Union
import uuid as _uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import CHAR


# revision identifiers, used by Alembic.
revision: str = 'a52b38ada3ba'
down_revision: Union[str, Sequence[str], None] = '30046b120e38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add nullable VARCHAR column with NO server_default
    # (MySQL strict replication mode forbids UUID() as a DEFAULT expression)
    op.add_column(
        'bank_file_records',
        sa.Column('uuid', CHAR(36), nullable=True)
    )

    # Step 2: Populate existing rows with Python-generated UUIDs via a batch UPDATE
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM bank_file_records WHERE uuid IS NULL")).fetchall()
    for (row_id,) in rows:
        new_uuid = str(_uuid.uuid4())
        conn.execute(
            sa.text("UPDATE bank_file_records SET uuid = :u WHERE id = :id"),
            {"u": new_uuid, "id": row_id}
        )

    # Step 3: Tighten to NOT NULL
    op.alter_column('bank_file_records', 'uuid', nullable=False, existing_type=CHAR(36))

    # Step 4: Add unique index
    op.create_index(op.f('ix_bank_file_records_uuid'), 'bank_file_records', ['uuid'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bank_file_records_uuid'), table_name='bank_file_records')
    op.drop_column('bank_file_records', 'uuid')
