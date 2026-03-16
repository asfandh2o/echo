"""add digests table

Revision ID: 004
Revises: 003
Create Date: 2026-02-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'digests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('digest_date', sa.Date(), nullable=False),
        sa.Column('content', JSONB, nullable=False),
        sa.Column('llm_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_digest_user_date', 'digests', ['user_id', 'digest_date'], unique=True)
    op.create_index('idx_digest_user_id', 'digests', ['user_id'])


def downgrade() -> None:
    op.drop_table('digests')
