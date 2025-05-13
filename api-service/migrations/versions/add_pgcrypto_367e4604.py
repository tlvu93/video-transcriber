"""Add pgcrypto extension

Revision ID: add_pgcrypto_367e4604
Revises: add_users_table
Create Date: 2025-05-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_pgcrypto_367e4604'
down_revision = 'add_users_table'
branch_labels = None
depends_on = None


def upgrade():
    # Create pgcrypto extension
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')


def downgrade():
    # Drop pgcrypto extension
    op.execute('DROP EXTENSION IF EXISTS pgcrypto')
