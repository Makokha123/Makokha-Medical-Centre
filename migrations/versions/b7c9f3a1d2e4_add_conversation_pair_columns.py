"""Add first/second user columns to conversations and uniqueness for 1:1

Revision ID: b7c9f3a1d2e4
Revises: a3b1c9f4d6e7
Create Date: 2025-10-07 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c9f3a1d2e4'
down_revision = 'a3b1c9f4d6e7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Add nullable columns to conversations
    op.add_column('conversations', sa.Column('first_user_id', sa.Integer(), nullable=True))
    op.add_column('conversations', sa.Column('second_user_id', sa.Integer(), nullable=True))

    # Backfill existing non-group conversations that have exactly two members
    # For each conversation with COUNT(members)=2 set first_user_id=min(uid), second_user_id=max(uid)
    if dialect == 'sqlite' or True:
        # SQL compatible approach
        bind.execute(sa.text("""
            UPDATE conversations
            SET first_user_id = (
                SELECT MIN(user_id) FROM conversation_members WHERE conversation_members.conversation_id = conversations.id
            ),
            second_user_id = (
                SELECT MAX(user_id) FROM conversation_members WHERE conversation_members.conversation_id = conversations.id
            )
            WHERE is_group = 0
            AND (
                SELECT COUNT(*) FROM conversation_members WHERE conversation_members.conversation_id = conversations.id
            ) = 2
        """))

    # Create a unique index to prevent duplicate 1:1 conversations
    # This will enforce uniqueness for pairs where both columns are non-null.
    op.create_index('ux_conversations_pair', 'conversations', ['first_user_id', 'second_user_id'], unique=True)


def downgrade():
    # Drop index and columns
    op.drop_index('ux_conversations_pair', table_name='conversations')
    op.drop_column('conversations', 'second_user_id')
    op.drop_column('conversations', 'first_user_id')
