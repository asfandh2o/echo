"""add drive_documents and document_chunks tables for Google Drive RAG

Revision ID: 008
Revises: 007
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'drive_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('drive_file_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(255), nullable=False),
        sa.Column('drive_link', sa.String(1000), nullable=True),
        sa.Column('owner_email', sa.String(255), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('drive_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('drive_modified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extra_data', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint('uq_user_drive_file', 'drive_documents', ['user_id', 'drive_file_id'])
    op.create_index('idx_drive_doc_user_status', 'drive_documents', ['user_id', 'status'])

    op.create_table(
        'document_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('drive_documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('search_vector', TSVECTOR),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extra_data', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('idx_chunk_search_vector', 'document_chunks', ['search_vector'], postgresql_using='gin')
    op.create_index('idx_chunk_user_document', 'document_chunks', ['user_id', 'document_id'])

    # Create tsvector trigger to auto-populate search_vector from content
    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER document_chunks_search_vector_trigger
        BEFORE INSERT OR UPDATE ON document_chunks
        FOR EACH ROW EXECUTE FUNCTION document_chunks_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS document_chunks_search_vector_trigger ON document_chunks;")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_search_vector_update();")
    op.drop_index('idx_chunk_user_document', table_name='document_chunks')
    op.drop_index('idx_chunk_search_vector', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index('idx_drive_doc_user_status', table_name='drive_documents')
    op.drop_constraint('uq_user_drive_file', 'drive_documents', type_='unique')
    op.drop_table('drive_documents')
