"""add contact_profiles table

Revision ID: 003
Revises: 002
Create Date: 2026-02-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'contact_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_address', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('email_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_contacted', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_contacted', sa.DateTime(timezone=True), nullable=True),
        sa.Column('topics', JSONB, server_default='[]'),
        sa.Column('relationship_type', sa.String(100), nullable=True),
        sa.Column('interaction_summary', sa.Text(), nullable=True),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_contact_user_email', 'contact_profiles', ['user_id', 'email_address'], unique=True)
    op.create_index('idx_contact_user_domain', 'contact_profiles', ['user_id', 'domain'])


def downgrade() -> None:
    op.drop_table('contact_profiles')
