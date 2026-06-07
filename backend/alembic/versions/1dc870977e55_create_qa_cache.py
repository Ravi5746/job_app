"""create_qa_cache

Revision ID: 1dc870977e55
Revises: 
Create Date: 2026-06-07 15:45:36.320634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1dc870977e55'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'qa_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_embedding', sa.JSON(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('used_count', sa.Integer(), nullable=True, default=0),
        sa.Column('last_used', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_qa_cache_id'), 'qa_cache', ['id'], unique=False)
    op.create_index(op.f('ix_qa_cache_question_text'), 'qa_cache', ['question_text'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_qa_cache_question_text'), table_name='qa_cache')
    op.drop_index(op.f('ix_qa_cache_id'), table_name='qa_cache')
    op.drop_table('qa_cache')
