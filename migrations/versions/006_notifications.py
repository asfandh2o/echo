"""add notifications table

Revision ID: 006
Revises: 005
Create Date: 2026-02-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('type', sa.String(50), nullable=False, server_default='info'),
        sa.Column('source', sa.String(50), nullable=False, server_default='echo'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('meta', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_notification_user_read', 'notifications', ['user_id', 'read'])
    op.create_index('idx_notification_user_created', 'notifications', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('notifications')
