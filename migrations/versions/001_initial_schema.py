"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('encrypted_oauth_tokens', sa.Text(), nullable=False),
        sa.Column('autonomy_level', sa.String(50), nullable=False, server_default='supervised'),
        sa.Column('token_budget', sa.Integer(), nullable=False, server_default='100000'),
        sa.Column('tokens_used_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_users_email', 'users', ['email'])

    op.create_table(
        'emails',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gmail_message_id', sa.String(255), nullable=False),
        sa.Column('thread_id', sa.String(255), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('sender', sa.String(255), nullable=False),
        sa.Column('recipients', JSONB, nullable=False),
        sa.Column('cc', JSONB, server_default='[]'),
        sa.Column('bcc', JSONB, server_default='[]'),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('html_body', sa.Text()),
        sa.Column('classification', JSONB),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_emails_user_id', 'emails', ['user_id'])
    op.create_index('idx_emails_gmail_message_id', 'emails', ['gmail_message_id'])
    op.create_index('idx_emails_thread_id', 'emails', ['thread_id'])
    op.create_index('idx_user_received', 'emails', ['user_id', 'received_at'])
    op.create_index('idx_user_thread', 'emails', ['user_id', 'thread_id'])

    op.create_table(
        'embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email_id', UUID(as_uuid=True), sa.ForeignKey('emails.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vector', Vector(1536), nullable=False),
        sa.Column('embedding_model', sa.String(100), nullable=False, server_default='text-embedding-3-small'),
        sa.Column('text_content', sa.Text(), nullable=False),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_embeddings_user_id', 'embeddings', ['user_id'])
    op.create_index('idx_embeddings_email_id', 'embeddings', ['email_id'])

    op.create_table(
        'suggestions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email_id', UUID(as_uuid=True), sa.ForeignKey('emails.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_text', sa.Text(), nullable=False),
        sa.Column('final_text', sa.Text()),
        sa.Column('feedback_type', sa.String(50)),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('reasoning', sa.Text()),
        sa.Column('context_used', JSONB, server_default='{}'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_suggestions_email_id', 'suggestions', ['email_id'])
    op.create_index('idx_suggestions_user_id', 'suggestions', ['user_id'])
    op.create_index('idx_user_status', 'suggestions', ['user_id', 'status'])
    op.create_index('idx_email_created', 'suggestions', ['email_id', 'created_at'])

    op.create_table(
        'style_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('profile_json', JSONB, nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_style_profiles_user_id', 'style_profiles', ['user_id'])

    op.create_table(
        'feedback_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_id', UUID(as_uuid=True), sa.ForeignKey('suggestions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feedback_type', sa.Text(), nullable=False),
        sa.Column('diff_score', sa.Float()),
        sa.Column('original_text', sa.Text(), nullable=False),
        sa.Column('final_text', sa.Text(), nullable=False),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('idx_feedback_logs_user_id', 'feedback_logs', ['user_id'])
    op.create_index('idx_feedback_logs_suggestion_id', 'feedback_logs', ['suggestion_id'])
    op.create_index('idx_feedback_logs_timestamp', 'feedback_logs', ['timestamp'])


def downgrade() -> None:
    op.drop_table('feedback_logs')
    op.drop_table('style_profiles')
    op.drop_table('suggestions')
    op.drop_table('embeddings')
    op.drop_table('emails')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS vector')
