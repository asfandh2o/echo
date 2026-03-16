"""add tasks table and interactive notification columns

Revision ID: 007
Revises: 006
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email_id', UUID(as_uuid=True), sa.ForeignKey('emails.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, server_default='echo'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_task_user_status', 'tasks', ['user_id', 'status'])
    op.create_index('idx_task_user_created', 'tasks', ['user_id', 'created_at'])
    op.create_index('idx_task_source', 'tasks', ['user_id', 'source'])

    op.add_column('notifications', sa.Column('action_type', sa.String(50), nullable=True))
    op.add_column('notifications', sa.Column('action_status', sa.String(50), nullable=True))
    op.add_column('notifications', sa.Column('action_payload', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('notifications', 'action_payload')
    op.drop_column('notifications', 'action_status')
    op.drop_column('notifications', 'action_type')
    op.drop_index('idx_task_source', table_name='tasks')
    op.drop_index('idx_task_user_created', table_name='tasks')
    op.drop_index('idx_task_user_status', table_name='tasks')
    op.drop_table('tasks')
