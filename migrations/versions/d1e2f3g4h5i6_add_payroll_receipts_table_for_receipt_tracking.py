"""Add payroll_receipts table for receipt tracking

Revision ID: d1e2f3g4h5i6
Revises: c9f8a1b2d3e4
Create Date: 2025-12-31 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3g4h5i6'
down_revision = 'c9f8a1b2d3e4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        # Check if table already exists
        try:
            res = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='payroll_receipts'")).fetchall()
            if not res:
                # Create the payroll_receipts table
                op.create_table(
                    'payroll_receipts',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('payroll_id', sa.Integer(), nullable=False),
                    sa.Column('receipt_number', sa.String(100), nullable=False),
                    sa.Column('amount', sa.Float(), nullable=False),
                    sa.Column('salary', sa.Float(), nullable=False),
                    sa.Column('previous_amount_paid', sa.Float(), nullable=False),
                    sa.Column('current_amount_paid', sa.Float(), nullable=False),
                    sa.Column('arrears', sa.Float(), nullable=False),
                    sa.Column('payment_date', sa.DateTime(), nullable=False),
                    sa.Column('issued_by', sa.Integer(), nullable=True),
                    sa.Column('notes', sa.Text(), nullable=True),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.ForeignKeyConstraint(['payroll_id'], ['payrolls.id']),
                    sa.ForeignKeyConstraint(['issued_by'], ['user.id']),
                    sa.UniqueConstraint('receipt_number')
                )
        except Exception as e:
            pass
    else:
        # For other databases
        try:
            op.create_table(
                'payroll_receipts',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('payroll_id', sa.Integer(), nullable=False),
                sa.Column('receipt_number', sa.String(100), nullable=False),
                sa.Column('amount', sa.Float(), nullable=False),
                sa.Column('salary', sa.Float(), nullable=False),
                sa.Column('previous_amount_paid', sa.Float(), nullable=False),
                sa.Column('current_amount_paid', sa.Float(), nullable=False),
                sa.Column('arrears', sa.Float(), nullable=False),
                sa.Column('payment_date', sa.DateTime(), nullable=False),
                sa.Column('issued_by', sa.Integer(), nullable=True),
                sa.Column('notes', sa.Text(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=False),
                sa.PrimaryKeyConstraint('id'),
                sa.ForeignKeyConstraint(['payroll_id'], ['payrolls.id']),
                sa.ForeignKeyConstraint(['issued_by'], ['user.id']),
                sa.UniqueConstraint('receipt_number')
            )
        except Exception as e:
            pass


def downgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'sqlite':
        try:
            op.drop_table('payroll_receipts')
        except Exception:
            pass
    else:
        try:
            op.drop_table('payroll_receipts')
        except Exception:
            pass
