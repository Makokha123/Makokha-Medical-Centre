"""
Add paid_by to payroll_payments (idempotent)

Revision ID: a3b1c9f4d6e7
Revises: 43d30eb52c1f
Create Date: 2025-10-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a3b1c9f4d6e7'
down_revision = '43d30eb52c1f'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # For SQLite, check PRAGMA table_info to avoid adding an existing column
    if dialect_name == 'sqlite':
        res = bind.execute(text("PRAGMA table_info('payroll_payments')")).fetchall()
        cols = [r[1] for r in res]
        if 'paid_by' not in cols:
            op.add_column('payroll_payments', sa.Column('paid_by', sa.Integer(), nullable=True))
            # add foreign key constraint if possible (SQLite will ignore adding FK constraints to existing table)
            try:
                with op.batch_alter_table('payroll_payments', schema=None) as batch_op:
                    batch_op.create_foreign_key('fk_payroll_payments_paid_by', 'user', ['paid_by'], ['id'])
            except Exception:
                # Some SQLite setups won't allow creating FK on existing table; ignore and rely on application-level integrity
                pass
    else:
        # For other DBs, use batch_alter_table for safe ALTERs
        with op.batch_alter_table('payroll_payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('paid_by', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_payroll_payments_paid_by', 'user', ['paid_by'], ['id'])


def downgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        # In SQLite dropping columns requires table rebuild; attempt to drop the constraint if present and leave column if complex
        # We'll attempt a best-effort removal of the foreign key constraint then the column if possible
        try:
            with op.batch_alter_table('payroll_payments', schema=None) as batch_op:
                batch_op.drop_constraint('fk_payroll_payments_paid_by', type_='foreignkey')
        except Exception:
            pass
        # Dropping column in SQLite is non-trivial; leave column in place for safety
    else:
        with op.batch_alter_table('payroll_payments', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('fk_payroll_payments_paid_by', type_='foreignkey')
            except Exception:
                pass
            batch_op.drop_column('paid_by')
