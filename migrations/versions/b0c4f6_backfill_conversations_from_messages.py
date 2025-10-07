"""
Backfill conversations and members from existing messages

Revision ID: b0c4f6_backfill_conversations_from_messages
Revises: a3b1c9f4d6e7
Create Date: 2025-10-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid

# revision identifiers, used by Alembic.
revision = 'b0c4f6_backfill_conversations_from_messages'
down_revision = 'a3b1c9f4d6e7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # This migration is idempotent: it will create conversations for unordered
    # user pairs found in messages if no conversation exists yet, and will set
    # conversation_id on existing messages that lack it.

    # Find distinct unordered pairs
    pairs = bind.execute(text("""
        SELECT DISTINCT
          CASE WHEN sender_id < recipient_id THEN sender_id ELSE recipient_id END AS user_a,
          CASE WHEN sender_id < recipient_id THEN recipient_id ELSE sender_id END AS user_b
        FROM messages
        WHERE sender_id IS NOT NULL AND recipient_id IS NOT NULL
    """)).fetchall()

    for row in pairs:
        a = row[0]; b = row[1]
        # check existing conversation
        existing = bind.execute(text("""
            SELECT cm1.conversation_id FROM conversation_members cm1
            JOIN conversation_members cm2 ON cm1.conversation_id = cm2.conversation_id
            WHERE cm1.user_id = :a AND cm2.user_id = :b LIMIT 1
        """), {'a': a, 'b': b}).fetchone()
        if existing:
            conv_id = existing[0]
            # attach messages if missing
            bind.execute(text("""
                UPDATE messages SET conversation_id = :conv
                WHERE ((sender_id = :a AND recipient_id = :b) OR (sender_id = :b AND recipient_id = :a))
                  AND (conversation_id IS NULL)
            """), {'conv': conv_id, 'a': a, 'b': b})
            continue

        # create conversation row (include normalized pair columns)
        fu = min(a, b)
        su = max(a, b)
        u_val = str(uuid.uuid4())
        res = bind.execute(text("INSERT INTO conversations (uuid, title, is_group, created_at, updated_at, first_user_id, second_user_id) VALUES (:u, NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :fu, :su)"), {'u': u_val, 'fu': fu, 'su': su})
        # Note: above UUID expression may not work across DBs; obtain last_insert_rowid
        conv_id = bind.execute(text('SELECT last_insert_rowid()')).scalar()

        # insert members
        bind.execute(text("INSERT INTO conversation_members (conversation_id, user_id, last_read_at, created_at) VALUES (:conv, :u1, NULL, CURRENT_TIMESTAMP)"), {'conv': conv_id, 'u1': a})
        bind.execute(text("INSERT INTO conversation_members (conversation_id, user_id, last_read_at, created_at) VALUES (:conv, :u2, NULL, CURRENT_TIMESTAMP)"), {'conv': conv_id, 'u2': b})

        # attach existing messages
        bind.execute(text("""
            UPDATE messages SET conversation_id = :conv
            WHERE (sender_id = :a AND recipient_id = :b) OR (sender_id = :b AND recipient_id = :a)
        """), {'conv': conv_id, 'a': a, 'b': b})


def downgrade():
    # no-op: do not remove conversations in downgrade
    pass
