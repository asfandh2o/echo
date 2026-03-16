"""add calendar_events table

Revision ID: 002
Revises: 001
Create Date: 2025-02-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'calendar_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_id', UUID(as_uuid=True), sa.ForeignKey('emails.id', ondelete='SET NULL'), nullable=True),
        sa.Column('google_event_id', sa.String(255), nullable=False),
        sa.Column('summary', sa.String(500), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attendees', JSONB, server_default='[]'),
        sa.Column('location', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='created'),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('llm_extraction', JSONB, server_default='{}'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_calendar_events_user_id', 'calendar_events', ['user_id'])
    op.create_index('idx_calendar_events_email_id', 'calendar_events', ['email_id'])
    op.create_index('idx_calendar_user_status', 'calendar_events', ['user_id', 'status'])
    op.create_index('idx_calendar_google_event', 'calendar_events', ['google_event_id'])


def downgrade() -> None:
    op.drop_table('calendar_events')
