"""Initial migration

Revision ID: initial_migration
Revises: 
Create Date: 2025-05-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'initial_migration'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create videos table
    op.create_table(
        'videos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('language', sa.String(), nullable=True),
        sa.Column('file_type', sa.String(), nullable=True),
        sa.Column('resolution_width', sa.Integer(), nullable=True),
        sa.Column('resolution_height', sa.Integer(), nullable=True)
    )
    
    # Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('video_id', UUID(as_uuid=True), sa.ForeignKey('videos.id'), nullable=True),
        sa.Column('source_type', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('format', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True)
    )
    
    # Create summaries table
    op.create_table(
        'summaries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('transcript_id', UUID(as_uuid=True), sa.ForeignKey('transcripts.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True)
    )
    
    # Create transcription_jobs table
    op.create_table(
        'transcription_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('video_id', UUID(as_uuid=True), sa.ForeignKey('videos.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_details', JSONB(), nullable=True)
    )
    
    # Create summarization_jobs table
    op.create_table(
        'summarization_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('transcript_id', UUID(as_uuid=True), sa.ForeignKey('transcripts.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_details', JSONB(), nullable=True)
    )


def downgrade():
    op.drop_table('summarization_jobs')
    op.drop_table('transcription_jobs')
    op.drop_table('summaries')
    op.drop_table('transcripts')
    op.drop_table('videos')
