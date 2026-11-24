"""revisions operateur (BF9) sur analyse

Revision ID: a41c22e90b17
Revises: 0fc6cff70574
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a41c22e90b17'
down_revision: Union[str, Sequence[str], None] = '0fc6cff70574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('analyse',
                  sa.Column('revisions', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyse', 'revisions')
