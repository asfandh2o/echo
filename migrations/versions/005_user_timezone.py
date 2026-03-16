"""add timezone column to users

Revision ID: 005
Revises: 004
Create Date: 2026-02-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Karachi'))


def downgrade() -> None:
    op.drop_column('users', 'timezone')
