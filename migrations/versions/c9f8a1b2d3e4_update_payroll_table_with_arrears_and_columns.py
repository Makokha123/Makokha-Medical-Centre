"""Update payroll table with arrears and additional columns

Revision ID: c9f8a1b2d3e4
Revises: b7c9f3a1d2e4
Create Date: 2025-12-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9f8a1b2d3e4'
down_revision = 'b7c9f3a1d2e4'
branch_labels = None
depends_on = None


def upgrade():
    # Make this migration idempotent and safe across SQLite and other DBs.
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        # Check existing columns via PRAGMA and add only missing ones
        # If a previous failed attempt left a temporary table behind, remove it
        try:
            bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_payrolls"))
        except Exception:
            pass

        res = bind.execute(sa.text("PRAGMA table_info('payrolls')")).fetchall()
        cols = [r[1] for r in res]
        with op.batch_alter_table('payrolls', schema=None) as batch_op:
            # Rename 'amount' to 'salary' if amount exists
            if 'amount' in cols and 'salary' not in cols:
                batch_op.alter_column('amount', new_column_name='salary')
            # Add new columns if they don't exist
            if 'arrears' not in cols:
                batch_op.add_column(sa.Column('arrears', sa.Float(), nullable=False, server_default='0.0'))
            if 'hired_date' not in cols:
                batch_op.add_column(sa.Column('hired_date', sa.Date(), nullable=True))
            if 'amount_paid' not in cols:
                batch_op.add_column(sa.Column('amount_paid', sa.Float(), nullable=False, server_default='0.0'))
    else:
        # For other DBs (PostgreSQL, MySQL, etc)
        with op.batch_alter_table('payrolls', schema=None) as batch_op:
            try:
                # Try to rename amount to salary
                batch_op.alter_column('amount', new_column_name='salary')
            except Exception:
                pass
            
            try:
                batch_op.add_column(sa.Column('arrears', sa.Float(), nullable=False, server_default='0.0'))
            except Exception:
                pass
            
            try:
                batch_op.add_column(sa.Column('hired_date', sa.Date(), nullable=True))
            except Exception:
                pass
            
            try:
                batch_op.add_column(sa.Column('amount_paid', sa.Float(), nullable=False, server_default='0.0'))
            except Exception:
                pass


def downgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        try:
            bind.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_payrolls"))
        except Exception:
            pass

        res = bind.execute(sa.text("PRAGMA table_info('payrolls')")).fetchall()
        cols = [r[1] for r in res]
        with op.batch_alter_table('payrolls', schema=None) as batch_op:
            # Rename 'salary' back to 'amount' if salary exists
            if 'salary' in cols and 'amount' not in cols:
                batch_op.alter_column('salary', new_column_name='amount')
            # Drop new columns
            if 'arrears' in cols:
                batch_op.drop_column('arrears')
            if 'hired_date' in cols:
                batch_op.drop_column('hired_date')
            if 'amount_paid' in cols:
                batch_op.drop_column('amount_paid')
    else:
        # For other DBs
        with op.batch_alter_table('payrolls', schema=None) as batch_op:
            try:
                batch_op.alter_column('salary', new_column_name='amount')
            except Exception:
                pass
            
            try:
                batch_op.drop_column('arrears')
            except Exception:
                pass
            
            try:
                batch_op.drop_column('hired_date')
            except Exception:
                pass
            
            try:
                batch_op.drop_column('amount_paid')
            except Exception:
                pass
