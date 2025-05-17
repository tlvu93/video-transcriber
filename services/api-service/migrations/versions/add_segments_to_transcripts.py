"""Add segments column to transcripts table

Revision ID: add_segments_to_transcripts
Revises: add_users_table
Create Date: 2025-05-17 19:34:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_segments_to_transcripts'
down_revision = 'add_users_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transcripts', sa.Column('segments', JSONB, nullable=True))


def downgrade():
    op.drop_column('transcripts', 'segments')
